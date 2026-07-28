"""Acquisition-session artifact writing."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
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


def run_recording_session(
    *,
    task_id: str,
    tracker: TrackerName,
    output_dir: str | Path,
    present: PresenterRunner,
    tracker_address: str | None = None,
    check_eyetracker: EyeTrackerCheck = default_check_eyetracker,
    recorder_factory: RecorderFactory = create_tobii_gaze_recorder,
    error_sink: StatusSink | None = None,
) -> int:
    error = error_sink or (lambda message: print(message, file=sys.stderr))

    output_path = Path(output_dir)
    if output_path.exists():
        error(f"Output directory already exists: {output_path}")
        return 5

    if tracker == "tobii":
        check_exit_code = check_eyetracker(address=tracker_address)
        if check_exit_code != 0:
            return check_exit_code

    output_path.mkdir(parents=True)
    _write_session_metadata(output_path / "session.json", task_id, tracker)
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


def _write_session_metadata(path: Path, task_id: str, tracker: TrackerName) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_id": task_id,
                "tracker": tracker,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
