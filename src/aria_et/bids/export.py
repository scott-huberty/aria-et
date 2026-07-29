"""Export ARIA JSONL acquisition artifacts to BIDS eyetracking files."""

from __future__ import annotations

import csv
import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TASK_BIDS_LABELS = {
    "activity-monitoring": "ActivityMonitoring",
    "static-social-scenes": "StaticSocialScenes",
    "pupillary-light-reflex": "PupillaryLightReflex",
}


@dataclass(frozen=True)
class BidsExportResult:
    bids_root: Path
    written_files: tuple[Path, ...]


def export_run_to_bids(
    *,
    run_dir: str | Path,
    bids_root: str | Path,
) -> BidsExportResult:
    run_path = Path(run_dir)
    root = Path(bids_root)
    session = _read_json(run_path / "session.json")
    tracker = _read_json(run_path / "tracker.json")
    task_label = _task_label(session["task_id"])
    entities = _bids_entities(session, task_label)
    beh_dir = _beh_dir(root, entities)
    beh_dir.mkdir(parents=True, exist_ok=True)

    base_name = _base_name(entities)
    display = _stimulus_display(session)
    gaze_rows = list(_iter_jsonl(run_path / "gaze.jsonl"))
    events = list(_iter_jsonl(run_path / "events.jsonl"))

    written: list[Path] = []
    written.append(_write_events_tsv(beh_dir / f"{base_name}_events.tsv", events))
    written.append(
        _write_events_json(root / f"task-{task_label}_events.json", task_label, display)
    )

    for recording, eye in (("eye1", "left"), ("eye2", "right")):
        physio_path = beh_dir / f"{base_name}_recording-{recording}_physio.tsv.gz"
        written.append(_write_physio_tsv(physio_path, gaze_rows, eye, display))
        written.append(
            _write_physio_json(
                beh_dir / f"{base_name}_recording-{recording}_physio.json",
                gaze_rows,
                eye,
                tracker,
            )
        )

    dataset_description = root / "dataset_description.json"
    if not dataset_description.exists():
        written.append(_write_dataset_description(dataset_description))

    return BidsExportResult(bids_root=root, written_files=tuple(written))


def _task_label(task_id: str) -> str:
    try:
        return TASK_BIDS_LABELS[task_id]
    except KeyError as error:
        raise ValueError(f"No BIDS task label configured for task_id={task_id!r}") from error


def _bids_entities(session: dict[str, Any], task_label: str) -> dict[str, str | None]:
    bids = session.get("bids") or {}
    subject = bids.get("subject")
    if not subject:
        raise ValueError("Run session.json is missing bids.subject.")
    return {
        "subject": _strip_entity_prefix(subject, "sub-"),
        "session": _strip_entity_prefix(bids.get("session"), "ses-"),
        "task": task_label,
        "run": bids.get("run"),
    }


def _stimulus_display(session: dict[str, Any]) -> dict[str, Any]:
    display = session.get("stimulus_display") or {}
    missing = [
        key
        for key in (
            "screen_distance_meters",
            "screen_origin",
            "screen_resolution_pixels",
            "screen_size_meters",
        )
        if key not in display
    ]
    if missing:
        raise ValueError(
            "Run session.json is missing BIDS stimulus display metadata: "
            + ", ".join(missing)
        )
    return display


def _strip_entity_prefix(value: str | None, prefix: str) -> str | None:
    if value is None:
        return None
    return value[len(prefix) :] if value.startswith(prefix) else value


def _beh_dir(root: Path, entities: dict[str, str | None]) -> Path:
    directory = root / f"sub-{entities['subject']}"
    if entities["session"]:
        directory = directory / f"ses-{entities['session']}"
    return directory / "beh"


def _base_name(entities: dict[str, str | None]) -> str:
    parts = [f"sub-{entities['subject']}"]
    if entities["session"]:
        parts.append(f"ses-{entities['session']}")
    parts.append(f"task-{entities['task']}")
    if entities["run"]:
        parts.append(f"run-{entities['run']}")
    return "_".join(parts)


def _write_events_tsv(path: Path, events: list[dict[str, Any]]) -> Path:
    first_timestamp = events[0]["timestamp"] if events else 0.0
    trial_end_by_id = {
        event["payload"].get("trial_id"): event["timestamp"]
        for event in events
        if event["name"].endswith(".trial.ended")
    }
    rows = []
    for event in events:
        name = event["name"]
        if name.endswith(".trial.ended") or name.endswith(".ended"):
            continue
        payload = event.get("payload", {})
        trial_id = payload.get("trial_id")
        duration = "n/a"
        if name.endswith(".trial.started") and trial_id in trial_end_by_id:
            duration = _format_number(trial_end_by_id[trial_id] - event["timestamp"])
        rows.append(
            {
                "onset": _format_number(event["timestamp"] - first_timestamp),
                "duration": duration,
                "trial_type": name,
                "value": _event_value(payload),
            }
        )

    return _write_tsv(path, ("onset", "duration", "trial_type", "value"), rows)


def _event_value(payload: dict[str, Any]) -> str:
    for key in ("stimulus_id", "sequence_id", "trial_id"):
        value = payload.get(key)
        if value is not None:
            return str(value)
    return "n/a"


def _write_events_json(path: Path, task_label: str, display: dict[str, Any]) -> Path:
    return _write_json(
        path,
        {
            "TaskName": task_label,
            "Columns": ["onset", "duration", "trial_type", "value"],
            "Description": "ARIA task events exported from acquisition JSONL.",
            "OnsetSource": "timestamp",
            "onset": {
                "Description": (
                    "Onset in seconds, measured from the first exported ARIA event."
                )
            },
            "duration": {"Description": "Duration in seconds, or n/a if unknown."},
            "trial_type": {"Description": "ARIA runtime event name."},
            "value": {"Description": "Primary sequence, stimulus, or trial identifier."},
            "StimulusPresentation": {
                "ScreenDistance": display["screen_distance_meters"],
                "ScreenOrigin": display["screen_origin"],
                "ScreenResolution": display["screen_resolution_pixels"],
                "ScreenSize": display["screen_size_meters"],
            },
        },
    )


def _write_physio_tsv(
    path: Path,
    gaze_rows: list[dict[str, Any]],
    eye: str,
    display: dict[str, Any],
) -> Path:
    first_timestamp = _system_timestamp_seconds(gaze_rows[0]) if gaze_rows else 0.0
    rows = []
    for row in gaze_rows:
        sample = row["sample"]
        rows.append(
            {
                "timestamp": _format_number(
                    _system_timestamp_seconds(row) - first_timestamp
                ),
                "x_coordinate": _format_optional_number(
                    _pixel_coordinate(sample, eye, "x", display)
                ),
                "y_coordinate": _format_optional_number(
                    _pixel_coordinate(sample, eye, "y", display)
                ),
                "pupil_size": _format_optional_number(
                    _valid_pupil_diameter(sample, eye)
                ),
            }
        )

    with gzip.open(path, "wt", encoding="utf-8", newline="") as fid:
        writer = csv.DictWriter(
            fid,
            fieldnames=("timestamp", "x_coordinate", "y_coordinate", "pupil_size"),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_physio_json(
    path: Path,
    gaze_rows: list[dict[str, Any]],
    eye: str,
    tracker: dict[str, Any],
) -> Path:
    return _write_json(
        path,
        {
            "Manufacturer": "Tobii",
            "ManufacturersModelName": tracker.get("model", "n/a"),
            "DeviceSerialNumber": tracker.get("serial_number", "n/a"),
            "SoftwareVersions": tracker.get("firmware_version", "n/a"),
            "PhysioType": "eyetrack",
            "RecordedEye": eye,
            "SampleCoordinateSystem": "gaze-on-screen",
            "SamplingFrequency": _sampling_frequency(gaze_rows),
            "StartTime": 0,
            "Columns": ["timestamp", "x_coordinate", "y_coordinate", "pupil_size"],
            "timestamp": {
                "Description": "Timestamp relative to the first exported gaze sample.",
                "Units": "s",
                "Origin": "Tobii system_time_stamp",
            },
            "x_coordinate": {
                "LongName": "Gaze position (x)",
                "Description": "Gaze position x-coordinate on the stimulus screen.",
                "Units": "pixel",
            },
            "y_coordinate": {
                "LongName": "Gaze position (y)",
                "Description": "Gaze position y-coordinate on the stimulus screen.",
                "Units": "pixel",
            },
            "pupil_size": {
                "Description": "Pupil diameter in millimeters.",
                "Units": "mm",
            },
        },
    )


def _pixel_coordinate(
    sample: dict[str, Any],
    eye: str,
    axis: str,
    display: dict[str, Any],
) -> float | None:
    if sample.get(f"{eye}_gaze_point_validity") != 1:
        return None
    point = sample.get(f"{eye}_gaze_point_on_display_area")
    if point is None or None in point:
        return None
    width, height = display["screen_resolution_pixels"]
    return float(point[0] * width if axis == "x" else point[1] * height)


def _valid_pupil_diameter(sample: dict[str, Any], eye: str) -> float | None:
    if sample.get(f"{eye}_pupil_validity") != 1:
        return None
    value = sample.get(f"{eye}_pupil_diameter")
    return None if value is None else float(value)


def _system_timestamp_seconds(row: dict[str, Any]) -> float:
    return float(row["sample"]["system_time_stamp"]) / 1_000_000


def _sampling_frequency(gaze_rows: list[dict[str, Any]]) -> float:
    if len(gaze_rows) < 2:
        return 0.0
    duration = _system_timestamp_seconds(gaze_rows[-1]) - _system_timestamp_seconds(
        gaze_rows[0]
    )
    if duration <= 0:
        return 0.0
    return round((len(gaze_rows) - 1) / duration, 6)


def _write_dataset_description(path: Path) -> Path:
    return _write_json(
        path,
        {
            "Name": "ARIA eye-tracking export",
            "BIDSVersion": "1.10.0",
            "DatasetType": "raw",
            "GeneratedBy": [{"Name": "aria-et"}],
        },
    )


def _write_tsv(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: list[dict[str, str]],
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as fid:
        writer = csv.DictWriter(
            fid,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as fid:
        for line in fid:
            if line.strip():
                yield json.loads(line)


def _format_optional_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    return _format_number(value)


def _format_number(value: float) -> str:
    return str(round(float(value), 9))
