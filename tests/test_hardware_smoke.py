import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = [
    pytest.mark.requires_eyetracker,
    pytest.mark.skipif(
        os.environ.get("ARIA_ET_HARDWARE") != "1",
        reason="Set ARIA_ET_HARDWARE=1 to run Tobii hardware smoke tests.",
    ),
]


TASKS = [
    ("run-am", "activity-monitoring", "ActivityMonitoring"),
    ("run-si", "social-interactive", "SocialInteractive"),
    ("run-ss", "static-social-scenes", "StaticSocialScenes"),
    ("run-plr", "pupillary-light-reflex", "PupillaryLightReflex"),
]


def _env_value(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _run_command(command: list[str], *, timeout: int = 180) -> str:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "Traceback" not in output
    assert "segmentation fault" not in output.lower()
    return output


def _raw_line_count(path: Path) -> int:
    return sum(1 for _ in path.open(encoding="utf-8"))


def _gzip_line_count(path: Path) -> int:
    with gzip.open(path, "rt", encoding="utf-8") as fid:
        return sum(1 for _ in fid)


def test_check_eyetracker_hardware_smoke():
    tracker_address = _env_value(
        "ARIA_ET_TRACKER_ADDRESS",
        "tobii-prp://169.254.10.180",
    )

    output = _run_command(
        [
            sys.executable,
            "-m",
            "aria_et.cli",
            "check-eyetracker",
            "--address",
            tracker_address,
        ],
        timeout=30,
    )

    assert "Tobii Pro SDK" in output
    assert "Connected to Tobii eye tracker" in output
    assert "Found 1 Tobii eye tracker" in output


@pytest.mark.parametrize(
    ("command_name", "task_id", "task_label"),
    TASKS,
    ids=[task[1] for task in TASKS],
)
def test_task_acquisition_and_bids_export_hardware_smoke(
    tmp_path,
    command_name,
    task_id,
    task_label,
):
    tracker_address = _env_value(
        "ARIA_ET_TRACKER_ADDRESS",
        "tobii-prp://169.254.10.180",
    )
    subject = _env_value("ARIA_ET_SMOKE_SUBJECT", "smoke")
    session = _env_value("ARIA_ET_SMOKE_SESSION", "hardware")
    screen = _env_value("ARIA_ET_PSYCHOPY_SCREEN", "1")
    screen_resolution = _env_value("ARIA_ET_SCREEN_RESOLUTION", "1920x1080")
    screen_size_meters = _env_value("ARIA_ET_SCREEN_SIZE_METERS", "0.527x0.296")
    screen_distance_meters = _env_value("ARIA_ET_SCREEN_DISTANCE_METERS", "0.65")
    trial_limit = _env_value("ARIA_ET_SMOKE_TRIAL_LIMIT", "2")
    output_root = Path(
        _env_value("ARIA_ET_SMOKE_OUTPUT_ROOT", str(tmp_path / "sourcedata"))
    )
    bids_root = Path(_env_value("ARIA_ET_SMOKE_BIDS_ROOT", str(tmp_path / "bids")))

    output = _run_command(
        [
            sys.executable,
            "-m",
            "aria_et.cli",
            command_name,
            "--tracker",
            "tobii",
            "--address",
            tracker_address,
            "--output",
            str(output_root),
            "--subject",
            subject,
            "--session",
            session,
            "--run",
            "01",
            "--fullscreen",
            "--screen",
            screen,
            "--screen-resolution",
            screen_resolution,
            "--screen-size-meters",
            screen_size_meters,
            "--screen-distance-meters",
            screen_distance_meters,
            "--trial-limit",
            trial_limit,
        ],
        timeout=240,
    )

    assert f"ended after {trial_limit} completed trial(s)" in output
    run_dir = output_root / f"sub-{subject}" / f"ses-{session}" / f"task-{task_id}_run-01"
    _assert_raw_run(run_dir, task_id, int(trial_limit))

    _run_command(
        [
            sys.executable,
            "-m",
            "aria_et.cli",
            "export-bids",
            "--input",
            str(run_dir),
            "--output",
            str(bids_root),
        ],
        timeout=120,
    )
    _assert_bids_export(
        bids_root=bids_root,
        subject=subject,
        session=session,
        task_label=task_label,
        raw_gaze_lines=_raw_line_count(run_dir / "gaze.jsonl"),
    )


def _assert_raw_run(run_dir: Path, task_id: str, trial_limit: int) -> None:
    assert (run_dir / "session.json").exists()
    assert (run_dir / "tracker.json").exists()
    assert (run_dir / "events.jsonl").exists()
    assert (run_dir / "gaze.jsonl").exists()
    assert (run_dir / "session.log").exists()

    session = json.loads((run_dir / "session.json").read_text(encoding="utf-8"))
    assert session["task_id"] == task_id
    assert session["tracker"] == "tobii"

    events = [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert events[0]["name"] == f"{task_id}.started"
    assert events[-1]["name"] == f"{task_id}.ended"
    assert events[-1]["payload"]["trial_count"] == trial_limit

    gaze_lines = _raw_line_count(run_dir / "gaze.jsonl")
    assert gaze_lines > 100


def _assert_bids_export(
    *,
    bids_root: Path,
    subject: str,
    session: str,
    task_label: str,
    raw_gaze_lines: int,
) -> None:
    beh_dir = bids_root / f"sub-{subject}" / f"ses-{session}" / "beh"
    base = beh_dir / f"sub-{subject}_ses-{session}_task-{task_label}_run-01"

    assert base.with_name(base.name + "_events.tsv").exists()
    eye1 = base.with_name(base.name + "_recording-eye1_physio.tsv.gz")
    eye2 = base.with_name(base.name + "_recording-eye2_physio.tsv.gz")
    assert eye1.exists()
    assert eye2.exists()
    assert base.with_name(base.name + "_recording-eye1_physio.json").exists()
    assert base.with_name(base.name + "_recording-eye2_physio.json").exists()

    assert _gzip_line_count(eye1) == raw_gaze_lines
    assert _gzip_line_count(eye2) == raw_gaze_lines
