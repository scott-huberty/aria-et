import gzip
import json
from pathlib import Path

import pytest

from aria_et.bids import export_run_to_bids


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_export_run_to_bids_writes_binocular_physio_and_events(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "session.json",
        {
            "task_id": "pupillary-light-reflex",
            "tracker": "tobii",
            "started_at": "2026-07-29T12:00:00+00:00",
            "bids": {"subject": "01", "session": "baseline", "run": "02"},
            "stimulus_display": {
                "screen_distance_meters": 0.6,
                "screen_origin": ["top", "left"],
                "screen_resolution_pixels": [1920, 1080],
                "screen_size_meters": [0.527, 0.296],
            },
        },
    )
    _write_json(
        run_dir / "tracker.json",
        {
            "model": "Tobii Pro Spectrum",
            "serial_number": "TPSP1-010214213025",
            "firmware_version": "2.6.2-orbicularis-0",
        },
    )
    _write_jsonl(
        run_dir / "events.jsonl",
        [
            {
                "name": "pupillary-light-reflex.started",
                "timestamp": 10.0,
                "payload": {"sequence_id": "pupillary-light-reflex"},
            },
            {
                "name": "pupillary-light-reflex.trial.started",
                "timestamp": 11.0,
                "payload": {"trial_id": "plr-01", "stimulus_id": "plr65"},
            },
            {
                "name": "pupillary-light-reflex.trial.ended",
                "timestamp": 13.5,
                "payload": {"trial_id": "plr-01"},
            },
        ],
    )
    _write_jsonl(
        run_dir / "gaze.jsonl",
        [
            {
                "received_at": 100.0,
                "sample": {
                    "system_time_stamp": 1_000_000,
                    "left_gaze_point_on_display_area": [0.25, 0.75],
                    "left_gaze_point_validity": 1,
                    "left_pupil_diameter": 4.1,
                    "left_pupil_validity": 1,
                    "right_gaze_point_on_display_area": [0.5, 0.5],
                    "right_gaze_point_validity": 1,
                    "right_pupil_diameter": 4.2,
                    "right_pupil_validity": 1,
                },
            },
            {
                "received_at": 100.002,
                "sample": {
                    "system_time_stamp": 1_002_000,
                    "left_gaze_point_on_display_area": [None, None],
                    "left_gaze_point_validity": 0,
                    "left_pupil_diameter": None,
                    "left_pupil_validity": 0,
                    "right_gaze_point_on_display_area": [0.6, 0.4],
                    "right_gaze_point_validity": 1,
                    "right_pupil_diameter": 4.3,
                    "right_pupil_validity": 1,
                },
            },
        ],
    )

    written = export_run_to_bids(run_dir=run_dir, bids_root=tmp_path / "bids")

    beh_dir = tmp_path / "bids" / "sub-01" / "ses-baseline" / "beh"
    base = beh_dir / "sub-01_ses-baseline_task-PupillaryLightReflex_run-02"
    assert written.bids_root == tmp_path / "bids"
    assert (base.with_name(base.name + "_events.tsv")).exists()
    assert (base.with_name(base.name + "_recording-eye1_physio.tsv.gz")).exists()
    assert (base.with_name(base.name + "_recording-eye2_physio.tsv.gz")).exists()

    events = (base.with_name(base.name + "_events.tsv")).read_text().splitlines()
    assert events == [
        "onset\tduration\ttrial_type\tvalue",
        "0.0\tn/a\tpupillary-light-reflex.started\tpupillary-light-reflex",
        "1.0\t2.5\tpupillary-light-reflex.trial.started\tplr65",
    ]

    with gzip.open(
        base.with_name(base.name + "_recording-eye1_physio.tsv.gz"),
        "rt",
        encoding="utf-8",
    ) as fid:
        rows = fid.read().splitlines()
    assert rows == [
        "0.0\t480.0\t810.0\t4.1",
        "0.002\tn/a\tn/a\tn/a",
    ]
    gzip_payload = base.with_name(
        base.name + "_recording-eye1_physio.tsv.gz"
    ).read_bytes()
    assert gzip_payload[3] == 0
    assert gzip_payload[4:8] == b"\x00\x00\x00\x00"

    sidecar = json.loads(
        base.with_name(base.name + "_recording-eye1_physio.json").read_text()
    )
    assert sidecar["TaskName"] == "PupillaryLightReflex"
    assert sidecar["PhysioType"] == "eyetrack"
    assert sidecar["RecordedEye"] == "left"
    assert sidecar["SamplingFrequency"] == 500.0
    assert sidecar["pupil_size"]["Description"].endswith("diameter in millimeters.")

    events_sidecar = json.loads(
        (tmp_path / "bids" / "task-PupillaryLightReflex_events.json").read_text()
    )
    assert events_sidecar["onset"]["Format"] == "number"
    assert events_sidecar["duration"]["Format"] == "number"
    assert events_sidecar["StimulusPresentation"] == {
        "ScreenDistance": 0.6,
        "ScreenOrigin": ["top", "left"],
        "ScreenResolution": [1920, 1080],
        "ScreenSize": [0.527, 0.296],
    }


def test_export_run_to_bids_requires_acquisition_metadata(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "session.json",
        {
            "task_id": "pupillary-light-reflex",
            "tracker": "tobii",
        },
    )
    _write_json(run_dir / "tracker.json", {})

    with pytest.raises(ValueError, match="bids.subject"):
        export_run_to_bids(run_dir=run_dir, bids_root=tmp_path / "bids")

    _write_json(
        run_dir / "session.json",
        {
            "task_id": "pupillary-light-reflex",
            "tracker": "tobii",
            "bids": {"subject": "01"},
        },
    )
    with pytest.raises(ValueError, match="stimulus display metadata"):
        export_run_to_bids(run_dir=run_dir, bids_root=tmp_path / "bids")
