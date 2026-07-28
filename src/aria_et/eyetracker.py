"""Eye tracker availability checks."""

from __future__ import annotations

import importlib
import json
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any


ImportModule = Callable[[str], ModuleType]
StatusSink = Callable[[str], None]


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
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.eyetracker = eyetracker
        self.tobii_research = tobii_research
        self.gaze_path = Path(gaze_path)
        self.tracker_metadata_path = Path(tracker_metadata_path)
        self.clock = clock
        self._file = None
        self._lock = threading.Lock()
        self._started = False

    def __enter__(self) -> "TobiiGazeRecorder":
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
        self.eyetracker.subscribe_to(
            self.tobii_research.EYETRACKER_GAZE_DATA,
            self._record_gaze_sample,
            as_dictionary=True,
        )
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return

        try:
            self.eyetracker.unsubscribe_from(
                self.tobii_research.EYETRACKER_GAZE_DATA,
                self._record_gaze_sample,
            )
        finally:
            if self._file is not None:
                self._file.close()
                self._file = None
            self._started = False

    def _record_gaze_sample(self, gaze_data: dict[str, object]) -> None:
        if self._file is None:
            return

        record = {
            "received_at": self.clock(),
            "sample": _json_safe(gaze_data),
        }
        line = json.dumps(record, sort_keys=True) + "\n"
        with self._lock:
            self._file.write(line)
            self._file.flush()


def create_tobii_gaze_recorder(
    *,
    gaze_path: str | Path,
    tracker_metadata_path: str | Path,
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
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
