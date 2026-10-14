import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

from aria_et.bids import export_run_to_bids
from aria_et.bids.export import TASK_BIDS_LABELS


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_run(
    run_dir: Path,
    *,
    task_id: str = "pupillary-light-reflex",
    subject: str = "01",
    session: str = "baseline",
    run: str = "02",
    calibration: dict | None = None,
) -> Path:
    """Write a minimal two-sample acquisition run, as the session recorder would."""
    run_dir.mkdir(parents=True)
    session_metadata = {
        "task_id": task_id,
        "tracker": "tobii",
        "started_at": "2026-07-29T12:00:00+00:00",
        "bids": {"subject": subject, "session": session, "run": run},
        "stimulus_display": {
            "screen_distance_meters": 0.6,
            "screen_origin": ["top", "left"],
            "screen_resolution_pixels": [1920, 1080],
            "screen_size_meters": [0.527, 0.296],
        },
    }
    if calibration is not None:
        session_metadata["calibration"] = calibration
    _write_json(run_dir / "session.json", session_metadata)
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
                "name": f"{task_id}.started",
                "timestamp": 10.0,
                "payload": {"sequence_id": task_id},
            },
            {
                "name": f"{task_id}.trial.started",
                "timestamp": 11.0,
                "payload": {"trial_id": "plr-01", "stimulus_id": "plr65"},
            },
            {
                "name": f"{task_id}.trial.ended",
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
    return run_dir


def test_bids_task_labels_cover_all_aria_tasks():
    assert TASK_BIDS_LABELS == {
        "activity-monitoring": "ActivityMonitoring",
        "pupillary-light-reflex": "PupillaryLightReflex",
        "social-interactive": "SocialInteractive",
        "static-social-scenes": "StaticSocialScenes",
    }


def test_export_run_to_bids_writes_binocular_physio_and_events(tmp_path):
    run_dir = _write_run(tmp_path / "run")

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

    assert not (tmp_path / "bids" / "task-PupillaryLightReflex_events.json").exists()
    events_sidecar = json.loads(base.with_name(base.name + "_events.json").read_text())
    assert events_sidecar["onset"]["Format"] == "number"
    assert events_sidecar["duration"]["Format"] == "number"
    assert events_sidecar["StimulusPresentation"] == {
        "ScreenDistance": 0.6,
        "ScreenOrigin": ["top", "left"],
        "ScreenResolution": [1920, 1080],
        "ScreenSize": [0.527, 0.296],
    }


VALIDATED_CALIBRATION = {
    "calibration_id": "calibration-20260729T115500Z",
    "created_at": "2026-07-29T11:55:00Z",
    "method": "child-friendly-detox",
    "metadata": {
        "calibration_points": {
            "count": 5,
            "positions_adcs": [
                [0.1, 0.1],
                [0.9, 0.1],
                [0.5, 0.5],
                [0.1, 0.9],
                [0.9, 0.9],
            ],
        },
        "validation": {
            "status": "complete",
            "summary": {
                "left": {
                    "accuracy_deg": 0.7614,
                    "max_accuracy_deg": 1.2,
                    "precision_rms_deg": 0.07,
                    "data_loss": 0.0,
                },
                "right": {
                    "accuracy_deg": 0.94,
                    "max_accuracy_deg": 1.5,
                    "precision_rms_deg": 0.06,
                    "data_loss": 0.0,
                },
            },
        },
    },
}


def _write_saved_calibrations(session_dir, created_at_values):
    for index, created_at in enumerate(created_at_values):
        directory = session_dir / "calibrations" / f"calibration-{index}"
        directory.mkdir(parents=True)
        _write_json(directory / "calibration.json", {"created_at": created_at})
    # A failed attempt (no calibration.json) doesn't count.
    (session_dir / "calibrations" / "calibration-failed").mkdir()


def test_export_writes_calibration_fields_per_eye(tmp_path):
    session_dir = tmp_path / "sourcedata" / "sub-01" / "ses-baseline"
    run_dir = _write_run(
        session_dir / "task-pupillary-light-reflex_run-02",
        calibration=VALIDATED_CALIBRATION,
    )
    # Two calibrations before the run started, one after.
    _write_saved_calibrations(
        session_dir,
        ["2026-07-29T11:50:00Z", "2026-07-29T11:55:00Z", "2026-07-29T13:00:00Z"],
    )

    export_run_to_bids(run_dir=run_dir, bids_root=tmp_path / "bids")

    base = (
        tmp_path
        / "bids/sub-01/ses-baseline/beh"
        / "sub-01_ses-baseline_task-PupillaryLightReflex_run-02"
    )
    left = json.loads(base.with_name(base.name + "_recording-eye1_physio.json").read_text())
    right = json.loads(base.with_name(base.name + "_recording-eye2_physio.json").read_text())
    assert left["CalibrationType"] == "HV5"
    assert left["CalibrationUnit"] == "pixel"
    assert left["CalibrationPosition"][0] == [192.0, 108.0]
    assert left["CalibrationCount"] == 2
    assert left["AverageCalibrationError"] == 0.761
    assert left["MaximalCalibrationError"] == 1.2
    assert right["AverageCalibrationError"] == 0.94
    assert right["MaximalCalibrationError"] == 1.5
    assert left["CalibrationId"] == "calibration-20260729T115500Z"
    assert left["CalibrationMethod"] == "child-friendly-detox"


def test_export_omits_calibration_fields_the_calibration_cannot_support(tmp_path):
    etm = {
        "calibration_id": "calibration-1",
        "created_at": "2026-07-29T11:55:00Z",
        "method": "tobii-pro-eye-tracker-manager",
        "metadata": {},
    }
    skipped = {
        **VALIDATED_CALIBRATION,
        "metadata": {
            **VALIDATED_CALIBRATION["metadata"],
            "validation": {"status": "skipped", "summary": None},
        },
    }
    for name, calibration in (("etm", etm), ("skipped", skipped), ("none", None)):
        run_dir = _write_run(tmp_path / name / "run", calibration=calibration)
        export_run_to_bids(run_dir=run_dir, bids_root=tmp_path / name / "bids")
        sidecar = json.loads(
            next((tmp_path / name / "bids").rglob("*eye1_physio.json")).read_text()
        )
        assert "AverageCalibrationError" not in sidecar, name
        if name == "etm":
            assert "CalibrationType" not in sidecar
            assert sidecar["CalibrationMethod"] == "tobii-pro-eye-tracker-manager"
        if name == "skipped":
            assert sidecar["CalibrationType"] == "HV5"
        if name == "none":
            assert not any(key.startswith("Calibration") for key in sidecar)


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


def _run_bids_validator(bids_root: Path) -> list[dict]:
    """Run the bundled BIDS validator and return its reported issues."""
    pytest.importorskip("bids_validator_deno")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import bids_validator_deno; bids_validator_deno.cli()",
            str(bids_root),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(
            f"BIDS validator did not produce a JSON report "
            f"(exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
        )
    return report["issues"]["issues"]


def test_exported_dataset_passes_bids_validator(tmp_path):
    bids_root = tmp_path / "bids"
    # Every task, across two subjects and sessions, so the dataset exercises
    # the per-run sidecars rather than a single exported run.
    for subject, session in (("01", "baseline"), ("02", "followup")):
        for task_id in TASK_BIDS_LABELS:
            run_dir = _write_run(
                tmp_path / "runs" / f"{subject}-{session}-{task_id}",
                task_id=task_id,
                subject=subject,
                session=session,
                run="01",
                calibration=VALIDATED_CALIBRATION,
            )
            export_run_to_bids(run_dir=run_dir, bids_root=bids_root)

    issues = _run_bids_validator(bids_root)

    errors = [issue for issue in issues if issue["severity"] == "error"]
    assert errors == [], json.dumps(errors, indent=2)
