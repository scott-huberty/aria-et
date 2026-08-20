"""Eye tracker availability checks."""

from __future__ import annotations

import importlib
import json
import math
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

from typing_extensions import Self

ImportModule = Callable[[str], ModuleType]
StatusSink = Callable[[str], None]
_QUEUE_STOP = object()
DEFAULT_EYETRACKER_MANAGER_PATH = (
    "/Applications/TobiiProEyeTrackerManager.app/Contents/MacOS/"
    "TobiiProEyeTrackerManager"
)
DEFAULT_CALIBRATION_DIR = "calibrations"


class TobiiSdkUnavailableError(RuntimeError):
    """Raised when the Tobii SDK cannot be imported."""


class TobiiTrackerUnavailableError(RuntimeError):
    """Raised when a Tobii tracker cannot be discovered or opened."""


def load_tobii_research(
    *,
    import_module: ImportModule = importlib.import_module,
) -> ModuleType:
    try:
        return import_module("tobii_research")
    except ImportError as error:
        raise TobiiSdkUnavailableError(
            "Tobii Pro SDK is not available. Install it with "
            "`pip install tobii-research`."
        ) from error


def open_eyetracker(
    *,
    address: str | None = None,
    import_module: ImportModule = importlib.import_module,
) -> object:
    tobii_research = load_tobii_research(import_module=import_module)
    if address is not None:
        try:
            return tobii_research.EyeTracker(address)
        except Exception as error:
            raise TobiiTrackerUnavailableError(
                f"No Tobii eye tracker could be opened at {address}: {error}"
            ) from error

    eyetrackers = tobii_research.find_all_eyetrackers()
    if not eyetrackers:
        raise TobiiTrackerUnavailableError(
            "No Tobii eye tracker was found. Connect and power on the tracker."
        )

    return eyetrackers[0]


def check_eyetracker(
    *,
    address: str | None = None,
    import_module: ImportModule = importlib.import_module,
    output_sink: StatusSink | None = None,
    error_sink: StatusSink | None = None,
) -> int:
    output = output_sink or print
    error = error_sink or (lambda message: print(message, file=sys.stderr))

    try:
        tobii_research = load_tobii_research(import_module=import_module)
    except TobiiSdkUnavailableError as error_message:
        error(str(error_message))
        return 2

    output(f"Tobii Pro SDK {tobii_research.__version__} is available.")
    if address is not None:
        try:
            eyetracker = open_eyetracker(
                address=address,
                import_module=import_module,
            )
        except TobiiTrackerUnavailableError as error_message:
            error(str(error_message))
            return 3

        output(f"Connected to Tobii eye tracker at {address}.")
        _report_eyetrackers((eyetracker,), output)
        return 0

    eyetrackers = tobii_research.find_all_eyetrackers()
    if not eyetrackers:
        error("No Tobii eye tracker was found. Connect and power on the tracker.")
        return 3

    _report_eyetrackers(eyetrackers, output)
    return 0


def _report_eyetrackers(
    eyetrackers: tuple[object, ...],
    output: StatusSink,
) -> None:
    tracker_count = len(eyetrackers)
    suffix = "" if tracker_count == 1 else "s"
    output(f"Found {tracker_count} Tobii eye tracker{suffix}.")
    for index, eyetracker in enumerate(eyetrackers, start=1):
        output(
            f"{index}. {getattr(eyetracker, 'device_name', eyetracker.model)} "
            f"model={eyetracker.model} "
            f"serial={eyetracker.serial_number} "
            f"address={eyetracker.address}"
        )


class TobiiGazeRecorder:
    def __init__(
        self,
        *,
        eyetracker: object,
        tobii_research: ModuleType,
        gaze_path: str | Path,
        tracker_metadata_path: str | Path,
        writer_health_path: str | Path | None = None,
        clock: Callable[[], float] = time.time,
        flush_every_samples: int = 250,
        flush_every_seconds: float = 0.5,
        max_queue_samples: int = 6000,
    ) -> None:
        if flush_every_samples < 1:
            raise ValueError("flush_every_samples must be at least 1.")
        if flush_every_seconds <= 0:
            raise ValueError("flush_every_seconds must be positive.")
        if max_queue_samples < 1:
            raise ValueError("max_queue_samples must be at least 1.")

        self.eyetracker = eyetracker
        self.tobii_research = tobii_research
        self.gaze_path = Path(gaze_path)
        self.tracker_metadata_path = Path(tracker_metadata_path)
        self.writer_health_path = (
            Path(writer_health_path) if writer_health_path is not None else None
        )
        self.clock = clock
        self.flush_every_samples = flush_every_samples
        self.flush_every_seconds = flush_every_seconds
        self.max_queue_samples = max_queue_samples
        self._file = None
        self._queue: queue.Queue[object] = queue.Queue(maxsize=max_queue_samples)
        self._writer_thread: threading.Thread | None = None
        self._writer_error: Exception | None = None
        self._started = False
        self._samples_since_flush = 0
        self._last_flush_at = 0.0
        self._started_at: float | None = None
        self._stopped_at: float | None = None
        self.received_queue_samples = 0
        self.written_queue_samples = 0
        self.dropped_queue_samples = 0
        self.gaze_file_flush_count = 0

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()

    def start(self) -> None:
        if self._started:
            return

        self.tracker_metadata_path.write_text(
            json.dumps(
                {
                    "address": self.eyetracker.address,
                    "model": self.eyetracker.model,
                    "serial_number": self.eyetracker.serial_number,
                    "firmware_version": self.eyetracker.firmware_version,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        self._file = self.gaze_path.open("w", encoding="utf-8")
        self._queue = queue.Queue(maxsize=self.max_queue_samples)
        self._writer_error = None
        self._samples_since_flush = 0
        self._last_flush_at = self.clock()
        self._started_at = self._last_flush_at
        self._stopped_at = None
        self.received_queue_samples = 0
        self.written_queue_samples = 0
        self.dropped_queue_samples = 0
        self.gaze_file_flush_count = 0
        self._write_writer_health_snapshot()
        self._writer_thread = threading.Thread(
            target=self._write_gaze_samples,
            name="TobiiGazeJsonlWriter",
            daemon=False,
        )
        self._writer_thread.start()
        self._started = True
        try:
            self.eyetracker.subscribe_to(
                self.tobii_research.EYETRACKER_GAZE_DATA,
                self._record_gaze_sample,
                as_dictionary=True,
            )
        except Exception:
            self._stop_writer()
            self._started = False
            if self._file is not None:
                self._file.close()
                self._file = None
            raise

    def stop(self) -> None:
        if not self._started:
            return

        try:
            self.eyetracker.unsubscribe_from(
                self.tobii_research.EYETRACKER_GAZE_DATA,
                self._record_gaze_sample,
            )
        finally:
            self._started = False
            self._stop_writer()
            if self._file is not None:
                self._file.close()
                self._file = None
            self._stopped_at = self.clock()
            self._write_writer_health_snapshot()
            if self._writer_error is not None:
                raise RuntimeError(
                    "Tobii gaze writer thread failed."
                ) from self._writer_error

    def _record_gaze_sample(self, gaze_data: dict[str, object]) -> None:
        if not self._started:
            return

        try:
            self.received_queue_samples += 1
            self._queue.put_nowait((self.clock(), gaze_data))
        except queue.Full:
            self.dropped_queue_samples += 1

    def _write_gaze_samples(self) -> None:
        try:
            while True:
                try:
                    item = self._queue.get(timeout=self.flush_every_seconds)
                except queue.Empty:
                    if self._should_flush(self.clock()):
                        self._flush_gaze_file()
                    continue

                try:
                    if item is _QUEUE_STOP:
                        self._flush_gaze_file()
                        return

                    received_at, gaze_data = item
                    self._write_gaze_sample(received_at, gaze_data)
                finally:
                    self._queue.task_done()
        except (OSError, TypeError, ValueError) as error:
            self._writer_error = error

    def _write_gaze_sample(
        self,
        received_at: float,
        gaze_data: dict[str, object],
    ) -> None:
        if self._file is None:
            return

        record = {
            "received_at": received_at,
            "sample": _json_safe(gaze_data),
        }
        line = json.dumps(record, sort_keys=True) + "\n"
        self._file.write(line)
        self.written_queue_samples += 1
        self._samples_since_flush += 1
        if self._should_flush(received_at):
            self._flush_gaze_file()

    def _stop_writer(self) -> None:
        if self._writer_thread is None:
            return

        if self._writer_thread.is_alive():
            self._queue.put(_QUEUE_STOP)
            self._writer_thread.join()
        self._writer_thread = None

    def _should_flush(self, now: float) -> bool:
        return self._samples_since_flush > 0 and (
            self._samples_since_flush >= self.flush_every_samples
            or now - self._last_flush_at >= self.flush_every_seconds
        )

    def _flush_gaze_file(self) -> None:
        if self._file is None:
            return

        self._file.flush()
        self._samples_since_flush = 0
        self._last_flush_at = self.clock()
        self.gaze_file_flush_count += 1
        self._write_writer_health_snapshot()

    def writer_health(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "started_at": self._started_at,
            "stopped_at": self._stopped_at,
            "received_queue_samples": self.received_queue_samples,
            "written_queue_samples": self.written_queue_samples,
            "dropped_queue_samples": self.dropped_queue_samples,
            "max_queue_samples": self.max_queue_samples,
            "queued_samples": self._queue.qsize(),
            "flush_count": self.gaze_file_flush_count,
            "flush_every_samples": self.flush_every_samples,
            "flush_every_seconds": self.flush_every_seconds,
            "last_flush_at": self._last_flush_at,
            "writer_thread_alive": (
                self._writer_thread.is_alive()
                if self._writer_thread is not None
                else False
            ),
            "writer_error": (
                repr(self._writer_error) if self._writer_error is not None else None
            ),
        }

    def _write_writer_health_snapshot(self) -> None:
        if self.writer_health_path is None:
            return

        self.writer_health_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.writer_health_path.with_suffix(
            self.writer_health_path.suffix + ".tmp"
        )
        tmp_path.write_text(
            json.dumps(self.writer_health(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(self.writer_health_path)


def create_tobii_gaze_recorder(
    *,
    gaze_path: str | Path,
    tracker_metadata_path: str | Path,
    writer_health_path: str | Path | None = None,
    address: str | None = None,
    import_module: ImportModule = importlib.import_module,
) -> TobiiGazeRecorder:
    tobii_research = load_tobii_research(import_module=import_module)
    eyetracker = open_eyetracker(address=address, import_module=import_module)
    return TobiiGazeRecorder(
        eyetracker=eyetracker,
        tobii_research=tobii_research,
        gaze_path=gaze_path,
        tracker_metadata_path=tracker_metadata_path,
        writer_health_path=(
            Path(writer_health_path)
            if writer_health_path is not None
            else Path(gaze_path).with_name("gaze_writer.json")
        ),
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _tracker_metadata(eyetracker: object) -> dict[str, str]:
    return {
        "address": eyetracker.address,
        "model": eyetracker.model,
        "serial_number": eyetracker.serial_number,
        "firmware_version": eyetracker.firmware_version,
    }


def _timestamp_for_path(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _timestamp_for_metadata(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _allocate_calibration_artifact_dir(
    output_dir: str | Path,
    created_at: datetime,
) -> Path:
    calibration_id = f"calibration-{_timestamp_for_path(created_at)}"
    artifact_dir = Path(output_dir) / calibration_id
    suffix = 1
    while artifact_dir.exists():
        suffix += 1
        artifact_dir = Path(output_dir) / f"{calibration_id}-{suffix}"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    return artifact_dir


def _open_tracker_after_calibration(
    *,
    address: str | None,
    serial_number: str | None,
    import_module: ImportModule,
) -> object:
    if address is not None:
        return open_eyetracker(address=address, import_module=import_module)

    tobii_research = load_tobii_research(import_module=import_module)
    eyetrackers = tobii_research.find_all_eyetrackers()
    if not eyetrackers:
        raise TobiiTrackerUnavailableError(
            "No Tobii eye tracker was found. Connect and power on the tracker."
        )
    if serial_number is None:
        return eyetrackers[0]

    for eyetracker in eyetrackers:
        if eyetracker.serial_number == serial_number:
            return eyetracker
    raise TobiiTrackerUnavailableError(
        f"No Tobii eye tracker with serial number {serial_number} was found."
    )


def save_current_calibration(
    *,
    eyetracker: object,
    output_dir: str | Path = DEFAULT_CALIBRATION_DIR,
    artifact_dir: str | Path | None = None,
    method: str,
    screen: int,
    manager_executable: str | None = None,
    manager_return_code: int | None = None,
    now: datetime | None = None,
) -> Path:
    created_at = now or datetime.now(timezone.utc)
    if artifact_dir is None:
        artifact_dir = _allocate_calibration_artifact_dir(output_dir, created_at)
    else:
        artifact_dir = Path(artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

    calibration_data = eyetracker.retrieve_calibration_data()
    calibration_data_file = artifact_dir / "calibration.bin"
    calibration_data_file.write_bytes(bytes(calibration_data))

    etm_log_file = artifact_dir / "etm.log"
    metadata = {
        "schema_version": 1,
        "calibration_id": artifact_dir.name,
        "created_at": _timestamp_for_metadata(created_at),
        "method": method,
        "screen": screen,
        "tracker": _tracker_metadata(eyetracker),
        "calibration_data_file": calibration_data_file.name,
    }
    if manager_executable is not None:
        metadata["manager_executable"] = manager_executable
    if manager_return_code is not None:
        metadata["manager_return_code"] = manager_return_code
    if etm_log_file.exists():
        metadata["etm_log_file"] = etm_log_file.name
    (artifact_dir / "calibration.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact_dir


def _run_command_with_tee(
    command: list[str],
    *,
    log_path: Path | None,
) -> subprocess.CompletedProcess:
    if log_path is None:
        return subprocess.run(command, check=False)

    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if process.stdout is not None:
            for line in process.stdout:
                print(line, end="")
                log_file.write(line)
        return_code = process.wait()

    return subprocess.CompletedProcess(command, return_code)


def run_eyetracker_manager_calibration(
    *,
    address: str | None = None,
    serial_number: str | None = None,
    screen: int = 1,
    executable: str = DEFAULT_EYETRACKER_MANAGER_PATH,
    calibration_output_dir: str | Path | None = DEFAULT_CALIBRATION_DIR,
    import_module: ImportModule = importlib.import_module,
    run_command: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    output_sink: StatusSink | None = None,
    error_sink: StatusSink | None = None,
) -> int:
    output = output_sink or print
    error = error_sink or (lambda message: print(message, file=sys.stderr))
    artifact_dir = None

    if address is not None and serial_number is not None:
        error("Use either --address or --serial-number, not both.")
        return 51

    try:
        if address is None and serial_number is None:
            tracker = open_eyetracker(import_module=import_module)
            address = tracker.address
    except TobiiSdkUnavailableError as error_message:
        error(str(error_message))
        return 2
    except TobiiTrackerUnavailableError as error_message:
        error(str(error_message))
        return 3

    command = [
        executable,
        "--mode=usercalibration",
        f"--screen={screen}",
    ]
    if serial_number is not None:
        command.append(f"--device-sn={serial_number}")
        target = serial_number
    else:
        command.append(f"--device-address={address}")
        target = address

    calibration_started_at = now()
    if calibration_output_dir is not None:
        artifact_dir = _allocate_calibration_artifact_dir(
            calibration_output_dir,
            calibration_started_at,
        )

    output(
        "Launching Tobii Pro Eye Tracker Manager calibration "
        f"for {target} on screen {screen}."
    )
    try:
        if run_command is subprocess.run:
            log_path = artifact_dir / "etm.log" if artifact_dir is not None else None
            result = _run_command_with_tee(command, log_path=log_path)
        else:
            result = run_command(command, check=False)
    except FileNotFoundError:
        error(f"Tobii Pro Eye Tracker Manager was not found: {executable}")
        return 44

    if result.returncode == 0:
        output("Tobii Pro Eye Tracker Manager calibration completed.")
        if calibration_output_dir is not None:
            try:
                calibrated_tracker = _open_tracker_after_calibration(
                    address=address,
                    serial_number=serial_number,
                    import_module=import_module,
                )
                artifact_dir = save_current_calibration(
                    eyetracker=calibrated_tracker,
                    output_dir=calibration_output_dir,
                    artifact_dir=artifact_dir,
                    method="tobii-pro-eye-tracker-manager",
                    screen=screen,
                    manager_executable=executable,
                    manager_return_code=result.returncode,
                    now=calibration_started_at,
                )
            except (
                OSError,
                TobiiSdkUnavailableError,
                TobiiTrackerUnavailableError,
            ) as error_message:
                error(
                    "Calibration completed, but saving calibration data failed: "
                    f"{error_message}"
                )
                return 4
            output(f"Saved calibration data to {artifact_dir}.")
    else:
        error(
            "Tobii Pro Eye Tracker Manager calibration exited with "
            f"status {result.returncode}."
        )
    return result.returncode
