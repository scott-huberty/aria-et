"""Acquisition-session artifact writing."""

from __future__ import annotations

import json
import os
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Literal, Protocol, TextIO

from typing_extensions import Self

from aria_et.eyetracker import (
    TobiiSdkUnavailableError,
    TobiiTrackerUnavailableError,
    create_tobii_gaze_recorder,
)
from aria_et.eyetracker import check_eyetracker as default_check_eyetracker
from aria_et.runtime import EventSink, RuntimeEvent

__all__ = [
    "BidsSessionMetadata",
    "GazeRecorder",
    "JsonLinesEventSink",
    "RecorderFactory",
    "StimulusDisplayMetadata",
    "TrackerName",
    "bids_subject_session_dir",
    "run_recording_session",
]

TrackerName = Literal["none", "tobii"]
StatusSink = Callable[[str], None]
PresenterRunner = Callable[[EventSink], None]
EyeTrackerCheck = Callable[..., int]


class GazeRecorder(Protocol):
    """Structural interface for e.g. TobiiGazeRecorder."""

    def __enter__(self) -> object:
        """Start recording.

        Returns
        -------
        object
            The recorder.
        """
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    def writer_health(self) -> dict[str, object]:
        """Return the counters of the gaze writer.

        Returns
        -------
        dict of str to object
            For example the number of samples received, written and dropped.
        """
        ...


class RecorderFactory(Protocol):
    """Makes the ``GazeRecorder`` of one run, e.g. ``create_tobii_gaze_recorder``."""

    def __call__(
        self,
        *,
        gaze_path: str | Path,
        tracker_metadata_path: str | Path,
        writer_health_path: str | Path | None = None,
        address: str | None = None,
        serial_number: str | None = None,
    ) -> GazeRecorder: ...


@dataclass(frozen=True)
class BidsSessionMetadata:
    """The BIDS labels of one run.

    Attributes
    ----------
    subject : str
        The subject label, with or without ``"sub-"``.
    session : str or None
        The session label, with or without ``"ses-"``. None for no session.
    run : str or None
        The run label, with or without ``"run-"``. None gives the next free
        run number.
    """

    subject: str
    session: str | None = None
    run: str | None = None


@dataclass(frozen=True)
class StimulusDisplayMetadata:
    """The stimulus display of one run, as written to ``session.json``.

    Attributes
    ----------
    screen_distance_meters : float
        The distance from the eyes of the participant to the screen.
    screen_origin : tuple of (str, str)
        The corner where the pixel coordinates start.
    screen_resolution_pixels : tuple of (int, int)
        The width and height of the screen in pixels.
    screen_size_meters : tuple of (float, float)
        The width and height of the screen in meters.
    psychopy_screen : int
        The PsychoPy screen number.
    fullscreen : bool
        True if the PsychoPy window filled the screen.
    window_size_pixels : tuple of (int, int)
        The size of the PsychoPy window in pixels.
    """

    screen_distance_meters: float = 0.65
    screen_origin: tuple[str, str] = ("top", "left")
    screen_resolution_pixels: tuple[int, int] = (1920, 1080)
    screen_size_meters: tuple[float, float] = (0.527, 0.296)
    psychopy_screen: int = 1
    fullscreen: bool = True
    window_size_pixels: tuple[int, int] = (1024, 768)


class JsonLinesEventSink:
    """An ``EventSink`` that writes one JSON line per event and flushes it.

    Parameters
    ----------
    path : Path
        The ``events.jsonl`` file. An existing file is replaced.
    """

    def __init__(self, path: Path):
        self._file = path.open("w", encoding="utf-8")

    def emit(self, event: RuntimeEvent) -> None:
        """Write one event to the file.

        Parameters
        ----------
        event : RuntimeEvent
            The event to write.
        """
        self._file.write(
            json.dumps(
                {
                    "name": event.name,
                    "timestamp": event.timestamp,
                    "payload": event.payload,
                },
                sort_keys=True,
            )
            + "\n"
        )
        self._file.flush()

    def close(self) -> None:
        """Close the file."""
        self._file.close()


class _TeeStream:
    def __init__(self, terminal_stream: TextIO, log_stream: _TimestampedLogStream):
        self._terminal_stream = terminal_stream
        self._log_stream = log_stream

    def write(self, text: str) -> int:
        self._terminal_stream.write(text)
        self._log_stream.write(text)
        return len(text)

    def flush(self) -> None:
        self._terminal_stream.flush()
        self._log_stream.flush()

    def isatty(self) -> bool:
        return self._terminal_stream.isatty()


class _TimestampedLogStream:
    def __init__(self, stream: TextIO):
        self._stream = stream
        self._at_line_start = True

    def write(self, text: str) -> int:
        for character in text:
            if self._at_line_start:
                self._stream.write(f"{_wall_clock_timestamp()} ")
                self._at_line_start = False
            self._stream.write(character)
            if character == "\n":
                self._at_line_start = True
        return len(text)

    def flush(self) -> None:
        self._stream.flush()


class _SessionLog:
    def __init__(self, path: Path):
        self.path = path
        self._file = None
        self._log_stream = None
        self._stdout = None
        self._stderr = None

    def __enter__(self) -> Self:
        self._file = self.path.open("w", encoding="utf-8")
        self._log_stream = _TimestampedLogStream(self._file)
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = _TeeStream(sys.stdout, self._log_stream)
        sys.stderr = _TeeStream(sys.stderr, self._log_stream)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> bool:
        assert self._file is not None
        assert self._log_stream is not None
        assert self._stdout is not None
        assert self._stderr is not None
        if exc_type is not None:
            self._log_stream.write("\n")
            traceback.print_exception(
                exc_type,
                exc_value,
                exc_traceback,
                file=self._log_stream,
            )
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        self._file.close()
        return False


def _wall_clock_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def run_recording_session(
    *,
    task_id: str,
    tracker: TrackerName,
    output_dir: str | Path,
    present: PresenterRunner,
    bids: BidsSessionMetadata | None = None,
    stimulus_display: StimulusDisplayMetadata | None = None,
    tracker_address: str | None = None,
    tracker_serial_number: str | None = None,
    check_eyetracker: EyeTrackerCheck = default_check_eyetracker,
    recorder_factory: RecorderFactory = create_tobii_gaze_recorder,
    error_sink: StatusSink | None = None,
    sys_info_collector: Callable[..., dict] | None = None,
) -> int:
    """Record one run of a task: the run folder, gaze, events and metadata.

    The function makes the run folder, writes ``sys_info.json`` and
    ``session.json``, checks the tracker, records gaze while ``present``
    runs, and writes the final gaze writer health. ``session.log`` receives
    all console output of the run.

    Parameters
    ----------
    task_id : str
        The task id, for example ``"activity-monitoring"``.
    tracker : TrackerName
        ``"tobii"`` records gaze. ``"none"`` is a dry run without gaze.
    output_dir : str or Path
        The ``sourcedata`` folder.
    present : PresenterRunner
        Shows the task. It receives the event sink of the run.
    bids : BidsSessionMetadata or None
        The subject, session and run labels. None writes the run to
        ``output_dir`` directly.
    stimulus_display : StimulusDisplayMetadata or None
        The display settings to write to ``session.json``.
    tracker_address : str or None
        The tracker address. None uses discovery.
    tracker_serial_number : str or None
        The tracker serial number, used if the address is not reachable.
    check_eyetracker : EyeTrackerCheck
        Checks the tracker before the run. For tests.
    recorder_factory : RecorderFactory
        Makes the gaze recorder. For tests.
    error_sink : StatusSink or None
        Receives error messages. None prints them to standard error.
    sys_info_collector : callable or None
        Collects the ``sys_info.json`` data. For tests.

    Returns
    -------
    int
        The exit code: 0 for a complete run, 2 if the Tobii SDK is not
        available, 3 if the tracker is not available, 5 if the run folder
        exists, or the exit code of ``check_eyetracker``.
    """
    error = error_sink or (lambda message: print(message, file=sys.stderr))

    try:
        output_path, resolved_bids = _resolve_output_path(
            output_dir=Path(output_dir),
            task_id=task_id,
            bids=bids,
        )
    except FileExistsError as error_message:
        error(str(error_message))
        return 5

    if output_path.exists():
        error(f"Output directory already exists: {output_path}")
        return 5

    output_path.mkdir(parents=True)

    with _SessionLog(output_path / "session.log"):
        from aria_et.sysinfo import write_sys_info_snapshot

        write_sys_info_snapshot(
            output_path, collector=sys_info_collector, error_sink=print
        )
        if tracker == "tobii":
            check_exit_code = check_eyetracker(
                address=tracker_address,
                serial_number=tracker_serial_number,
            )
            if check_exit_code != 0:
                return check_exit_code

        _write_session_metadata(
            output_path / "session.json",
            task_id,
            tracker,
            bids=resolved_bids,
            stimulus_display=stimulus_display,
            calibration=(
                _resolve_calibration_provenance(output_path, resolved_bids)
                if tracker == "tobii"
                else None
            ),
        )
        event_sink = JsonLinesEventSink(output_path / "events.jsonl")
        try:
            if tracker == "tobii":
                try:
                    recorder = recorder_factory(
                        gaze_path=output_path / "gaze.jsonl",
                        tracker_metadata_path=output_path / "tracker.json",
                        writer_health_path=output_path / "gaze_writer.json",
                        address=tracker_address,
                        serial_number=tracker_serial_number,
                    )
                except TobiiSdkUnavailableError as error_message:
                    error(str(error_message))
                    return 2
                except TobiiTrackerUnavailableError as error_message:
                    error(str(error_message))
                    return 3

                try:
                    with recorder:
                        present(event_sink)
                finally:
                    _record_gaze_writer_health(output_path, recorder)
            else:
                present(event_sink)
        finally:
            event_sink.close()

    return 0


def _resolve_output_path(
    *,
    output_dir: Path,
    task_id: str,
    bids: BidsSessionMetadata | None,
) -> tuple[Path, BidsSessionMetadata | None]:
    if bids is None:
        return output_dir, None

    normalized_bids = _normalize_bids_metadata(bids)
    if normalized_bids.run is None:
        normalized_bids = BidsSessionMetadata(
            subject=normalized_bids.subject,
            session=normalized_bids.session,
            run=_next_run_label(output_dir, task_id, normalized_bids),
        )
    output_path = _bids_run_dir(output_dir, task_id, normalized_bids)
    if output_path.exists():
        raise FileExistsError(f"Output directory already exists: {output_path}")
    return output_path, normalized_bids


def bids_subject_session_dir(
    output_dir: str | Path,
    *,
    subject: str,
    session: str | None,
) -> Path:
    """Return the folder of one subject and session in the BIDS layout.

    Parameters
    ----------
    output_dir : str or Path
        The ``sourcedata`` or BIDS root folder.
    subject : str
        The subject label, with or without ``"sub-"``.
    session : str or None
        The session label, with or without ``"ses-"``. None for no session.

    Returns
    -------
    Path
        ``<output_dir>/sub-<subject>/ses-<session>``, or
        ``<output_dir>/sub-<subject>`` if there is no session.
    """
    normalized = _normalize_bids_metadata(
        BidsSessionMetadata(subject=subject, session=session)
    )
    path = Path(output_dir) / f"sub-{normalized.subject}"
    if normalized.session is not None:
        path = path / f"ses-{normalized.session}"
    return path


def _normalize_bids_metadata(bids: BidsSessionMetadata) -> BidsSessionMetadata:
    return BidsSessionMetadata(
        subject=_normalize_bids_label(bids.subject, "sub-"),
        session=_normalize_optional_bids_label(bids.session, "ses-"),
        run=_normalize_optional_bids_label(bids.run, "run-"),
    )


def _normalize_optional_bids_label(value: str | None, prefix: str) -> str | None:
    if value is None:
        return None
    return _normalize_bids_label(value, prefix)


def _normalize_bids_label(value: str, prefix: str) -> str:
    stripped = value.removeprefix(prefix)
    return stripped.zfill(2) if stripped.isdecimal() else stripped


def _next_run_label(
    output_dir: Path,
    task_id: str,
    bids: BidsSessionMetadata,
) -> str:
    run_number = 1
    while True:
        candidate = f"{run_number:02d}"
        candidate_path = _bids_run_dir(
            output_dir,
            task_id,
            BidsSessionMetadata(
                subject=bids.subject,
                session=bids.session,
                run=candidate,
            ),
        )
        if not candidate_path.exists():
            return candidate
        run_number += 1


def _bids_run_dir(output_dir: Path, task_id: str, bids: BidsSessionMetadata) -> Path:
    path = output_dir / f"sub-{bids.subject}"
    if bids.session is not None:
        path = path / f"ses-{bids.session}"
    return path / f"task-{task_id}_run-{bids.run}"


def _write_session_metadata(
    path: Path,
    task_id: str,
    tracker: TrackerName,
    *,
    bids: BidsSessionMetadata | None = None,
    stimulus_display: StimulusDisplayMetadata | None = None,
    calibration: dict[str, object] | None = None,
) -> None:
    metadata = {
        "schema_version": 1,
        "task_id": task_id,
        "tracker": tracker,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "sys_info_file": "sys_info.json",
    }
    if bids is not None:
        metadata["bids"] = {
            "subject": bids.subject,
            "session": bids.session,
            "run": bids.run,
        }
    if stimulus_display is not None:
        metadata["stimulus_display"] = {
            "screen_distance_meters": stimulus_display.screen_distance_meters,
            "screen_origin": list(stimulus_display.screen_origin),
            "screen_resolution_pixels": list(stimulus_display.screen_resolution_pixels),
            "screen_size_meters": list(stimulus_display.screen_size_meters),
            "psychopy_screen": stimulus_display.psychopy_screen,
            "fullscreen": stimulus_display.fullscreen,
            "window_size_pixels": list(stimulus_display.window_size_pixels),
        }
    if calibration is not None:
        metadata["calibration"] = calibration

    path.write_text(
        json.dumps(
            metadata,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _record_gaze_writer_health(output_path: Path, recorder: GazeRecorder) -> None:
    health = recorder.writer_health()

    writer_health_path = output_path / "gaze_writer.json"
    if not writer_health_path.exists():
        writer_health_path.write_text(
            json.dumps(health, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    _update_session_metadata(
        output_path / "session.json",
        gaze_writer={
            "health_file": writer_health_path.name,
            "final_health": health,
        },
    )
    print(
        "Tobii gaze writer summary: "
        f"received={health.get('received_queue_samples')} "
        f"written={health.get('written_queue_samples')} "
        f"dropped={health.get('dropped_queue_samples')} "
        f"flushes={health.get('flush_count')} "
        f"queued={health.get('queued_samples')}"
    )


def _update_session_metadata(path: Path, **updates: object) -> None:
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    metadata.update(updates)
    path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _resolve_calibration_provenance(
    run_dir: Path,
    bids: BidsSessionMetadata | None,
) -> dict[str, object] | None:
    if bids is None:
        return None

    calibrations_dir = run_dir.parent / "calibrations"
    if not calibrations_dir.exists():
        return None

    candidates = [
        metadata_file
        for metadata_file in calibrations_dir.glob("calibration-*/calibration.json")
        if metadata_file.is_file()
    ]
    if not candidates:
        return None

    metadata_file = max(candidates, key=_calibration_sort_key)
    artifact_dir = metadata_file.parent
    calibration_metadata = _read_calibration_metadata(metadata_file)

    return {
        "artifact_dir": _relative_path(artifact_dir, run_dir),
        "metadata_file": _relative_path(metadata_file, run_dir),
        "calibration_id": calibration_metadata.get("calibration_id", artifact_dir.name),
        "created_at": calibration_metadata.get("created_at"),
        "method": calibration_metadata.get("method"),
        "tracker": calibration_metadata.get("tracker"),
        "metadata": calibration_metadata,
    }


def _calibration_sort_key(metadata_file: Path) -> tuple[str, float, str]:
    metadata = _read_calibration_metadata(metadata_file)
    created_at = metadata.get("created_at")
    if not isinstance(created_at, str):
        created_at = ""
    return (created_at, metadata_file.stat().st_mtime, metadata_file.parent.name)


def _read_calibration_metadata(metadata_file: Path) -> dict[str, object]:
    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(metadata, dict):
        return {}
    return metadata


def _relative_path(path: Path, start: Path) -> str:
    return Path(os.path.relpath(path.resolve(), start.resolve())).as_posix()
