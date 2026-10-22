"""Tobii eye tracker access: find, check, record gaze and save calibrations."""

from __future__ import annotations

import importlib
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from types import ModuleType, TracebackType

from typing_extensions import Self

from aria_et.protocols import (
    CalibratedTracker,
    GazeSample,
    GazeTracker,
    ImportModule,
    StatusSink,
    TobiiEyeTracker,
    TrackerIdentity,
)

MACOS_EYETRACKER_MANAGER_PATH = (
    "/Applications/TobiiProEyeTrackerManager.app/Contents/MacOS/"
    "TobiiProEyeTrackerManager"
)
LINUX_EYETRACKER_MANAGER_PATH = (
    "/opt/TobiiProEyeTrackerManager/TobiiProEyeTrackerManager"
)
__all__ = [
    "TobiiGazeRecorder",
    "TobiiSdkUnavailableError",
    "TobiiTrackerUnavailableError",
    "check_eyetracker",
    "create_tobii_gaze_recorder",
    "default_eyetracker_manager_path",
    "find_eyetracker",
    "load_tobii_research",
    "open_eyetracker",
    "run_eyetracker_manager_calibration",
    "save_current_calibration",
]

DEFAULT_CALIBRATION_DIR = "calibrations"
# Retries when replacing gaze_writer.json is refused (Windows, GUI reading it).
HEALTH_REPLACE_ATTEMPTS = 3
HEALTH_REPLACE_RETRY_SECONDS = 0.01


def default_eyetracker_manager_path(
    platform: str = sys.platform,
    environ: Mapping[str, str] = os.environ,
) -> str:
    """Return where Tobii Pro Eye Tracker Manager is installed by default.

    On Windows, ETM installs per user under ``%LOCALAPPDATA%\\Programs``, or
    for all users under ``%ProgramFiles%``. The function returns the first
    of these paths that exists. If neither exists, it returns the per-user
    path, so that a "not found" message shows a useful path.

    Parameters
    ----------
    platform : str
        The value of ``sys.platform``. For tests.
    environ : Mapping of str to str
        The environment variables. For tests.

    Returns
    -------
    str
        The path of the ETM executable.
    """
    if platform.startswith("win"):
        install_dirs = (
            ("LOCALAPPDATA", "Programs"),
            ("ProgramFiles", ""),
        )
        candidates = [
            str(
                PureWindowsPath(
                    environ[root],
                    subdir,
                    "TobiiProEyeTrackerManager",
                    "TobiiProEyeTrackerManager.exe",
                )
            )
            for root, subdir in install_dirs
            if environ.get(root)
        ]
        for candidate in candidates:
            if Path(candidate).exists():
                return candidate
        if candidates:
            return candidates[0]
        return "TobiiProEyeTrackerManager.exe"
    if platform == "darwin":
        return MACOS_EYETRACKER_MANAGER_PATH
    return LINUX_EYETRACKER_MANAGER_PATH


class TobiiSdkUnavailableError(RuntimeError):
    """Raised when the Tobii SDK cannot be imported."""


class TobiiTrackerUnavailableError(RuntimeError):
    """Raised when a Tobii tracker cannot be discovered or opened."""


def load_tobii_research(
    *,
    import_module: ImportModule = importlib.import_module,
) -> ModuleType:
    """Import the Tobii Pro SDK.

    Parameters
    ----------
    import_module : ImportModule
        Imports ``tobii_research``. For tests.

    Returns
    -------
    ModuleType
        The ``tobii_research`` module.

    Raises
    ------
    TobiiSdkUnavailableError
        If the SDK is not installed.
    """
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
    serial_number: str | None = None,
    import_module: ImportModule = importlib.import_module,
    error_sink: StatusSink | None = None,
) -> TobiiEyeTracker:
    """Open a tracker by address. If that fails, find it by serial number.

    Link-local tracker addresses can change. If ``address`` cannot be opened
    and ``serial_number`` is known, discovery finds the tracker with that
    serial number. Without an address, the function uses discovery.

    Parameters
    ----------
    address : str or None
        The tracker address. None uses discovery.
    serial_number : str or None
        The serial number of the tracker.
    import_module : ImportModule
        Imports ``tobii_research``. For tests.
    error_sink : StatusSink or None
        Receives a warning when discovery finds the tracker at a new address.
        None prints it to standard error.

    Returns
    -------
    TobiiEyeTracker
        The open tracker.

    Raises
    ------
    TobiiTrackerUnavailableError
        If no tracker can be opened.
    """
    tobii_research = load_tobii_research(import_module=import_module)
    if address is not None:
        try:
            return tobii_research.EyeTracker(address)
        except Exception as error:
            if serial_number is None:
                raise TobiiTrackerUnavailableError(
                    f"No Tobii eye tracker could be opened at {address}: {error}"
                ) from error
            eyetracker = _find_by_serial_number(tobii_research, serial_number)
            if eyetracker is None:
                raise TobiiTrackerUnavailableError(
                    f"No Tobii eye tracker could be opened at {address} "
                    f"({error}), and no tracker with serial number "
                    f"{serial_number} was found by discovery."
                ) from error
            warn = error_sink or (lambda message: print(message, file=sys.stderr))
            warn(
                f"Warning: tracker {serial_number} was not reachable at {address} "
                f"but was found at {eyetracker.address}. Run "
                "`aria-et find-eyetracker --save` to update the saved address."
            )
            return eyetracker

    eyetrackers = tobii_research.find_all_eyetrackers()
    if not eyetrackers:
        raise TobiiTrackerUnavailableError(
            "No Tobii eye tracker was found. Connect and power on the tracker."
        )

    if serial_number is not None:
        for eyetracker in eyetrackers:
            if eyetracker.serial_number == serial_number:
                return eyetracker
        raise TobiiTrackerUnavailableError(
            f"No Tobii eye tracker with serial number {serial_number} was found."
        )

    return eyetrackers[0]


def _find_by_serial_number(
    tobii_research: ModuleType, serial_number: str
) -> TobiiEyeTracker | None:
    for eyetracker in tobii_research.find_all_eyetrackers():
        if eyetracker.serial_number == serial_number:
            return eyetracker
    return None


def check_eyetracker(
    *,
    address: str | None = None,
    serial_number: str | None = None,
    import_module: ImportModule = importlib.import_module,
    output_sink: StatusSink | None = None,
    error_sink: StatusSink | None = None,
) -> int:
    """Check that the SDK works and that a tracker is connected.

    Parameters
    ----------
    address : str or None
        The tracker address. None uses discovery.
    serial_number : str or None
        The serial number of the tracker.
    import_module : ImportModule
        Imports ``tobii_research``. For tests.
    output_sink : StatusSink or None
        Receives status messages. None prints them.
    error_sink : StatusSink or None
        Receives error messages. None prints them to standard error.

    Returns
    -------
    int
        The exit code: 0 if a tracker is connected, 2 if the SDK is not
        available, 3 if no tracker is found.
    """
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
                serial_number=serial_number,
                import_module=import_module,
                error_sink=error,
            )
        except TobiiTrackerUnavailableError as error_message:
            error(str(error_message))
            return 3

        output(f"Connected to Tobii eye tracker at {eyetracker.address}.")
        _report_eyetrackers((eyetracker,), output)
        _warn_on_serial_mismatch(eyetracker, serial_number, error)
        return 0

    eyetrackers = tobii_research.find_all_eyetrackers()
    if not eyetrackers:
        error("No Tobii eye tracker was found. Connect and power on the tracker.")
        return 3

    _report_eyetrackers(eyetrackers, output)
    return 0


def find_eyetracker(
    *,
    save: bool = False,
    serial_number: str | None = None,
    config_path: str | Path | None = None,
    import_module: ImportModule = importlib.import_module,
    output_sink: StatusSink | None = None,
    error_sink: StatusSink | None = None,
) -> int:
    """List the connected trackers, and save one to the user config if asked.

    Parameters
    ----------
    save : bool
        True saves the address and serial number of the tracker to the config.
    serial_number : str or None
        The tracker to save if more than one is connected.
    config_path : str or Path or None
        The config file. None uses the default path.
    import_module : ImportModule
        Imports ``tobii_research``. For tests.
    output_sink : StatusSink or None
        Receives status messages. None prints them.
    error_sink : StatusSink or None
        Receives error messages. None prints them to standard error.

    Returns
    -------
    int
        The exit code: 0 for success, 2 if the SDK is not available, 3 if no
        tracker (or no tracker with ``serial_number``) is found, 4 if more
        than one tracker is found and ``serial_number`` is not given.
    """
    from aria_et.config import load_config, set_config

    output = output_sink or print
    error = error_sink or (lambda message: print(message, file=sys.stderr))

    try:
        tobii_research = load_tobii_research(import_module=import_module)
    except TobiiSdkUnavailableError as error_message:
        error(str(error_message))
        return 2

    output(f"Tobii Pro SDK {tobii_research.__version__} is available.")
    eyetrackers = tuple(tobii_research.find_all_eyetrackers())
    if not eyetrackers:
        error("No Tobii eye tracker was found. Connect and power on the tracker.")
        return 3
    _report_eyetrackers(eyetrackers, output)

    config = load_config(config_path)
    if config.tracker_address or config.tracker_serial_number:
        output(
            "Saved tracker for this laptop: "
            f"serial={config.tracker_serial_number or 'unset'} "
            f"address={config.tracker_address or 'unset'}"
        )
    else:
        output("No tracker is saved for this laptop yet.")

    if not save:
        if not config.tracker_address:
            output("Run `aria-et find-eyetracker --save` to save it.")
        return 0

    if serial_number is not None:
        selected = [e for e in eyetrackers if e.serial_number == serial_number]
        if not selected:
            error(f"No Tobii eye tracker with serial number {serial_number} was found.")
            return 3
    elif len(eyetrackers) > 1:
        error(
            "More than one Tobii eye tracker was found. Pass --serial-number "
            "to choose which one to save."
        )
        return 4
    else:
        selected = list(eyetrackers)

    eyetracker = selected[0]
    set_config("tobii.address", eyetracker.address, config_path)
    set_config("tobii.serial_number", eyetracker.serial_number, config_path)
    output(
        f"Saved tracker {eyetracker.serial_number} at {eyetracker.address} "
        "to the ARIA-ET config."
    )
    return 0


def _warn_on_serial_mismatch(
    eyetracker: TrackerIdentity,
    serial_number: str | None,
    error: StatusSink,
) -> None:
    if serial_number is not None and eyetracker.serial_number != serial_number:
        error(
            f"Warning: connected tracker has serial number "
            f"{eyetracker.serial_number}, but {serial_number} is saved for this "
            "laptop. Run `aria-et find-eyetracker --save` if the tracker changed."
        )


def _report_eyetrackers(
    eyetrackers: tuple[TrackerIdentity, ...],
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
            f"address={eyetracker.address} "
            f"firmware={getattr(eyetracker, 'firmware_version', 'unknown')}"
        )


class TobiiGazeRecorder:
    """Records Tobii gaze samples to ``gaze.jsonl`` on a writer thread.

    The Tobii callback only puts each sample in a bounded queue. A writer
    thread writes one JSON line per sample and flushes the file at a fixed
    number of samples or seconds. If the queue is full, the sample is
    dropped and counted. Use the recorder as a context manager.

    Parameters
    ----------
    eyetracker : GazeTracker
        The open tracker.
    tobii_research : ModuleType
        The ``tobii_research`` module, for its stream names.
    gaze_path : str or Path
        The ``gaze.jsonl`` file. An existing file is replaced.
    tracker_metadata_path : str or Path
        The ``tracker.json`` file: address, model, serial and firmware.
    writer_health_path : str or Path or None
        The ``gaze_writer.json`` file with the writer counters. None writes no
        health file.
    clock : callable
        Gives the time in seconds when a sample is received.
    flush_every_samples : int
        The writer flushes the file after this number of samples.
    flush_every_seconds : float
        The writer flushes the file after this number of seconds.
    max_queue_samples : int
        The size of the queue. More samples than this are dropped.
    """

    def __init__(
        self,
        *,
        eyetracker: GazeTracker,
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
        # None asks the writer thread to flush and stop.
        self._queue: queue.Queue[tuple[float, GazeSample] | None] = queue.Queue(
            maxsize=max_queue_samples
        )
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
        self.health_snapshot_failures = 0

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()

    def start(self) -> None:
        """Write ``tracker.json``, start the writer thread, and subscribe."""
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
        self.health_snapshot_failures = 0
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
        """Unsubscribe, write the remaining samples, and close the file.

        Raises
        ------
        RuntimeError
            If the writer thread failed during the recording.
        """
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

    def _record_gaze_sample(self, gaze_data: GazeSample) -> None:
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
                    if item is None:
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
        gaze_data: GazeSample,
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
            self._queue.put(None)
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
        """Return the counters of the gaze writer.

        Returns
        -------
        dict of str to object
            The content of ``gaze_writer.json``: received, written and
            dropped samples, flushes, and the state of the writer thread.
        """
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
            "health_snapshot_failures": self.health_snapshot_failures,
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
        """Publish writer health; best effort, it must never stop gaze writing.

        The GUI reads this file during a run. On Windows, replacing a file
        fails with "Access is denied" while another process has it open, so a
        refused replace is retried briefly and otherwise skipped: the next
        flush writes a fresh snapshot. Skipped snapshots are counted.
        """
        if self.writer_health_path is None:
            return

        try:
            self.writer_health_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.writer_health_path.with_suffix(
                self.writer_health_path.suffix + ".tmp"
            )
            tmp_path.write_text(
                json.dumps(self.writer_health(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            for attempt in range(HEALTH_REPLACE_ATTEMPTS):
                try:
                    self._replace_health_file(tmp_path, self.writer_health_path)
                    return
                except PermissionError:
                    if attempt + 1 == HEALTH_REPLACE_ATTEMPTS:
                        raise
                    time.sleep(HEALTH_REPLACE_RETRY_SECONDS)
        except OSError:
            self.health_snapshot_failures += 1

    def _replace_health_file(self, tmp_path: Path, health_path: Path) -> None:
        tmp_path.replace(health_path)


def create_tobii_gaze_recorder(
    *,
    gaze_path: str | Path,
    tracker_metadata_path: str | Path,
    writer_health_path: str | Path | None = None,
    address: str | None = None,
    serial_number: str | None = None,
    import_module: ImportModule = importlib.import_module,
) -> TobiiGazeRecorder:
    """Open a tracker and make a ``TobiiGazeRecorder`` for it.

    Parameters
    ----------
    gaze_path : str or Path
        The ``gaze.jsonl`` file.
    tracker_metadata_path : str or Path
        The ``tracker.json`` file.
    writer_health_path : str or Path or None
        The ``gaze_writer.json`` file. None puts it next to ``gaze_path``.
    address : str or None
        The tracker address. None uses discovery.
    serial_number : str or None
        The serial number of the tracker.
    import_module : ImportModule
        Imports ``tobii_research``. For tests.

    Returns
    -------
    TobiiGazeRecorder
        The recorder. It does not record until it starts.
    """
    tobii_research = load_tobii_research(import_module=import_module)
    eyetracker = open_eyetracker(
        address=address,
        serial_number=serial_number,
        import_module=import_module,
    )
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


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _tracker_metadata(eyetracker: TrackerIdentity) -> dict[str, str]:
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
    *,
    sys_info_collector: Callable[..., dict] | None = None,
) -> Path:
    calibration_id = f"calibration-{_timestamp_for_path(created_at)}"
    artifact_dir = Path(output_dir) / calibration_id
    suffix = 1
    while artifact_dir.exists():
        suffix += 1
        artifact_dir = Path(output_dir) / f"{calibration_id}-{suffix}"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    from aria_et.sysinfo import write_sys_info_snapshot

    write_sys_info_snapshot(artifact_dir, collector=sys_info_collector)
    return artifact_dir


def _open_tracker_after_calibration(
    *,
    address: str | None,
    serial_number: str | None,
    import_module: ImportModule,
) -> TobiiEyeTracker:
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
    eyetracker: CalibratedTracker,
    output_dir: str | Path = DEFAULT_CALIBRATION_DIR,
    artifact_dir: str | Path | None = None,
    method: str,
    screen: int,
    manager_executable: str | None = None,
    manager_return_code: int | None = None,
    now: datetime | None = None,
    extra_metadata: dict[str, object] | None = None,
    sys_info_collector: Callable[..., dict] | None = None,
) -> Path:
    """Save the active calibration of the tracker, with ``calibration.json``.

    The function writes ``calibration.bin`` (the calibration data),
    ``calibration.json`` (the metadata) and ``sys_info.json``.

    Parameters
    ----------
    eyetracker : CalibratedTracker
        The tracker with the calibration to save.
    output_dir : str or Path
        The ``calibrations`` folder. Used when ``artifact_dir`` is None.
    artifact_dir : str or Path or None
        The folder of this calibration. None makes a new
        ``calibration-<time>`` folder in ``output_dir``.
    method : str
        The calibration method, for example ``"child-friendly-detox"``.
    screen : int
        The screen that showed the calibration.
    manager_executable : str or None
        The ETM executable, for an ETM calibration.
    manager_return_code : int or None
        The exit code of ETM, for an ETM calibration.
    now : datetime or None
        The time of the calibration. None uses the current time.
    extra_metadata : dict of str to object or None
        More data for ``calibration.json``, for example the calibration
        points and the validation results.
    sys_info_collector : callable or None
        Collects the ``sys_info.json`` data. For tests.

    Returns
    -------
    Path
        The folder of the saved calibration.

    Raises
    ------
    TobiiTrackerUnavailableError
        If the tracker has no active calibration.
    """
    created_at = now or datetime.now(timezone.utc)
    if artifact_dir is None:
        artifact_dir = _allocate_calibration_artifact_dir(
            output_dir, created_at, sys_info_collector=sys_info_collector
        )
    else:
        artifact_dir = Path(artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        if not (artifact_dir / "sys_info.json").exists():
            from aria_et.sysinfo import write_sys_info_snapshot

            write_sys_info_snapshot(artifact_dir, collector=sys_info_collector)

    calibration_data = eyetracker.retrieve_calibration_data()
    if calibration_data is None:
        raise TobiiTrackerUnavailableError(
            "The tracker has no active calibration to save."
        )
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
        "sys_info_file": "sys_info.json",
    }
    if manager_executable is not None:
        metadata["manager_executable"] = manager_executable
    if manager_return_code is not None:
        metadata["manager_return_code"] = manager_return_code
    if etm_log_file.exists():
        metadata["etm_log_file"] = etm_log_file.name
    if extra_metadata:
        metadata.update(extra_metadata)
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
    executable: str | Path | None = None,
    calibration_output_dir: str | Path | None = DEFAULT_CALIBRATION_DIR,
    import_module: ImportModule = importlib.import_module,
    run_command: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    output_sink: StatusSink | None = None,
    error_sink: StatusSink | None = None,
) -> int:
    """Run a calibration in Tobii Pro Eye Tracker Manager, then save it.

    Parameters
    ----------
    address : str or None
        The tracker address. Use ``address`` or ``serial_number``, not both.
    serial_number : str or None
        The tracker serial number. Use ``address`` or ``serial_number``, not
        both. If both are None, discovery finds the tracker.
    screen : int
        The screen where ETM shows the calibration.
    executable : str or Path or None
        The ETM executable. None uses ``default_eyetracker_manager_path()``.
    calibration_output_dir : str or Path or None
        The ``calibrations`` folder. None does not save the calibration.
    import_module : ImportModule
        Imports ``tobii_research``. For tests.
    run_command : callable
        Runs ETM. For tests.
    now : callable
        Gives the time of the calibration. For tests.
    output_sink : StatusSink or None
        Receives status messages. None prints them.
    error_sink : StatusSink or None
        Receives error messages. None prints them to standard error.

    Returns
    -------
    int
        The exit code: the exit code of ETM, 2 if the SDK is not available,
        3 if no tracker is found, 4 if saving the calibration failed, 44 if
        ETM is not found, 51 if both ``address`` and ``serial_number`` are
        given.
    """
    output = output_sink or print
    error = error_sink or (lambda message: print(message, file=sys.stderr))
    manager = str(
        executable if executable is not None else default_eyetracker_manager_path()
    )
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
        manager,
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
        error(f"Tobii Pro Eye Tracker Manager was not found: {manager}")
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
                    manager_executable=manager,
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
