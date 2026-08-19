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
from typing import Literal

from aria_et.eyetracker import check_eyetracker as default_check_eyetracker
from aria_et.eyetracker import create_tobii_gaze_recorder
from aria_et.eyetracker import TobiiSdkUnavailableError, TobiiTrackerUnavailableError
from aria_et.runtime import EventSink, RuntimeEvent


TrackerName = Literal["none", "tobii"]
StatusSink = Callable[[str], None]
PresenterRunner = Callable[[EventSink], None]
EyeTrackerCheck = Callable[..., int]
RecorderFactory = Callable[..., object]


@dataclass(frozen=True)
class BidsSessionMetadata:
    subject: str
    session: str | None = None
    run: str | None = None


@dataclass(frozen=True)
class StimulusDisplayMetadata:
    screen_distance_meters: float = 0.65
    screen_origin: tuple[str, str] = ("top", "left")
    screen_resolution_pixels: tuple[int, int] = (1920, 1080)
    screen_size_meters: tuple[float, float] = (0.527, 0.296)
    psychopy_screen: int = 1
    fullscreen: bool = True
    window_size_pixels: tuple[int, int] = (1024, 768)


class JsonLinesEventSink:
    def __init__(self, path: Path):
        self._file = path.open("w", encoding="utf-8")

    def emit(self, event: RuntimeEvent) -> None:
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
        self._file.close()


class _TeeStream:
    def __init__(self, terminal_stream, log_stream):
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
    def __init__(self, stream):
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

    def __enter__(self):
        self._file = self.path.open("w", encoding="utf-8")
        self._log_stream = _TimestampedLogStream(self._file)
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = _TeeStream(sys.stdout, self._log_stream)
        sys.stderr = _TeeStream(sys.stderr, self._log_stream)
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> bool:
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
    check_eyetracker: EyeTrackerCheck = default_check_eyetracker,
    recorder_factory: RecorderFactory = create_tobii_gaze_recorder,
    error_sink: StatusSink | None = None,
) -> int:
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
        if tracker == "tobii":
            check_exit_code = check_eyetracker(address=tracker_address)
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
                        address=tracker_address,
                    )
                except TobiiSdkUnavailableError as error_message:
                    error(str(error_message))
                    return 2
                except TobiiTrackerUnavailableError as error_message:
                    error(str(error_message))
                    return 3

                with recorder:
                    present(event_sink)
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
    stripped = value[len(prefix) :] if value.startswith(prefix) else value
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
            "screen_resolution_pixels": list(
                stimulus_display.screen_resolution_pixels
            ),
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
