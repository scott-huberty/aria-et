"""Acquisition-session artifact writing."""

from __future__ import annotations

import json
import sys
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

    output_path = Path(output_dir)
    if output_path.exists():
        error(f"Output directory already exists: {output_path}")
        return 5

    if tracker == "tobii":
        check_exit_code = check_eyetracker(address=tracker_address)
        if check_exit_code != 0:
            return check_exit_code

    output_path.mkdir(parents=True)
    _write_session_metadata(
        output_path / "session.json",
        task_id,
        tracker,
        bids=bids,
        stimulus_display=stimulus_display,
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


def _write_session_metadata(
    path: Path,
    task_id: str,
    tracker: TrackerName,
    *,
    bids: BidsSessionMetadata | None = None,
    stimulus_display: StimulusDisplayMetadata | None = None,
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

    path.write_text(
        json.dumps(
            metadata,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
