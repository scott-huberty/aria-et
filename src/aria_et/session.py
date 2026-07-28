"""Acquisition-session artifact writing."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from aria_et.eyetracker import check_eyetracker as default_check_eyetracker
from aria_et.runtime import EventSink, RuntimeEvent


TrackerName = Literal["none", "tobii"]
StatusSink = Callable[[str], None]
PresenterRunner = Callable[[EventSink], None]
EyeTrackerCheck = Callable[..., int]


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
    error_sink: StatusSink | None = None,
) -> int:
    error = error_sink or (lambda message: print(message, file=sys.stderr))

    if tracker == "tobii":
        check_exit_code = check_eyetracker(address=tracker_address)
        if check_exit_code != 0:
            return check_exit_code
        error("Tobii-backed run sessions are not implemented yet.")
        return 4

    output_path = Path(output_dir)
    if output_path.exists():
        error(f"Output directory already exists: {output_path}")
        return 5

    output_path.mkdir(parents=True)
    _write_session_metadata(output_path / "session.json", task_id, tracker)
    event_sink = JsonLinesEventSink(output_path / "events.jsonl")
    try:
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
