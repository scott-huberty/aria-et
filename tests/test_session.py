import json
import re
import sys

import pytest

from aria_et.runtime import RuntimeEvent
from aria_et.session import (
    BidsSessionMetadata,
    StimulusDisplayMetadata,
    run_recording_session,
)


SESSION_LOG_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{2}:\d{2} "
)


class FakeRecorder:
    def __init__(self, gaze_path, tracker_metadata_path):
        self.gaze_path = gaze_path
        self.tracker_metadata_path = tracker_metadata_path
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        self.tracker_metadata_path.write_text(
            json.dumps(
                {
                    "address": "tobii-prp://169.254.10.180",
                    "model": "Tobii Pro Spectrum",
                    "serial_number": "TPSP1-010214213025",
                    "firmware_version": "2.6.2-orbicularis-0",
                }
            )
            + "\n"
        )
        self.gaze_path.write_text(
            json.dumps(
                {
                    "received_at": 10.0,
                    "sample": {"system_time_stamp": 123},
                }
            )
            + "\n"
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.exited = True


def _write_calibration_artifact(
    artifact_dir,
    *,
    created_at,
    serial_number,
    method,
):
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "calibration.bin").write_bytes(b"fake-calibration")
    metadata = {
        "schema_version": 1,
        "calibration_id": artifact_dir.name,
        "created_at": created_at,
        "method": method,
        "tracker": {
            "serial_number": serial_number,
        },
        "calibration_data_file": "calibration.bin",
    }
    (artifact_dir / "calibration.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata


def test_run_recording_session_writes_metadata_and_events_for_no_tracker(tmp_path):
    output_dir = tmp_path / "run-am"

    def present(event_sink):
        event_sink.emit(
            RuntimeEvent(
                "activity-monitoring.started",
                1.25,
                {"sequence_id": "activity-monitoring"},
            )
        )

    exit_code = run_recording_session(
        task_id="activity-monitoring",
        tracker="none",
        output_dir=output_dir,
        present=present,
    )

    assert exit_code == 0
    metadata = json.loads((output_dir / "session.json").read_text())
    assert metadata["task_id"] == "activity-monitoring"
    assert metadata["tracker"] == "none"

    events = [
        json.loads(line)
        for line in (output_dir / "events.jsonl").read_text().splitlines()
    ]
    assert events == [
        {
            "name": "activity-monitoring.started",
            "timestamp": 1.25,
            "payload": {"sequence_id": "activity-monitoring"},
        }
    ]


def test_run_recording_session_tees_terminal_output_to_session_log(tmp_path, capsys):
    output_dir = tmp_path / "run-am"

    def present(event_sink):
        print("program status")
        print("psychopy warning", file=sys.stderr)
        event_sink.emit(RuntimeEvent("activity-monitoring.started", 1.25, {}))

    exit_code = run_recording_session(
        task_id="activity-monitoring",
        tracker="none",
        output_dir=output_dir,
        present=present,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "program status" in captured.out
    assert "psychopy warning" in captured.err

    session_log = (output_dir / "session.log").read_text()
    assert "program status" in session_log
    assert "psychopy warning" in session_log
    assert all(
        SESSION_LOG_TIMESTAMP.match(line)
        for line in session_log.splitlines()
        if line
    )


def test_run_recording_session_writes_uncaught_traceback_to_session_log(tmp_path):
    output_dir = tmp_path / "run-am"

    def present(event_sink):
        print("before crash")
        raise RuntimeError("movie frame failed")

    with pytest.raises(RuntimeError, match="movie frame failed"):
        run_recording_session(
            task_id="activity-monitoring",
            tracker="none",
            output_dir=output_dir,
            present=present,
        )

    session_log = (output_dir / "session.log").read_text()
    assert "before crash" in session_log
    assert "Traceback (most recent call last)" in session_log
    assert "RuntimeError: movie frame failed" in session_log
    assert all(
        SESSION_LOG_TIMESTAMP.match(line)
        for line in session_log.splitlines()
        if line
    )


def test_run_recording_session_rejects_existing_output_directory(tmp_path, capsys):
    output_dir = tmp_path / "run-am"
    output_dir.mkdir()

    exit_code = run_recording_session(
        task_id="activity-monitoring",
        tracker="none",
        output_dir=output_dir,
        present=lambda event_sink: None,
    )

    assert exit_code != 0
    assert "already exists" in capsys.readouterr().err


def test_run_recording_session_records_events_and_gaze_for_tobii(tmp_path):
    check_calls = []
    recorder_calls = []
    recorders = []

    def check_eyetracker(**kwargs):
        check_calls.append(kwargs)
        print("Found 1 Tobii eye tracker.")
        return 0

    def recorder_factory(**kwargs):
        recorder_calls.append(kwargs)
        recorder = FakeRecorder(kwargs["gaze_path"], kwargs["tracker_metadata_path"])
        recorders.append(recorder)
        return recorder

    def present(event_sink):
        event_sink.emit(RuntimeEvent("task.started", 1.0, {}))

    output_dir = tmp_path / "run-am"

    exit_code = run_recording_session(
        task_id="activity-monitoring",
        tracker="tobii",
        tracker_address="tobii-prp://169.254.10.180",
        output_dir=output_dir,
        present=present,
        check_eyetracker=check_eyetracker,
        recorder_factory=recorder_factory,
    )

    assert exit_code == 0
    assert check_calls == [{"address": "tobii-prp://169.254.10.180"}]
    assert recorder_calls == [
        {
            "gaze_path": output_dir / "gaze.jsonl",
            "tracker_metadata_path": output_dir / "tracker.json",
            "address": "tobii-prp://169.254.10.180",
        }
    ]
    assert recorders[0].entered is True
    assert recorders[0].exited is True
    assert json.loads((output_dir / "tracker.json").read_text())[
        "serial_number"
    ] == "TPSP1-010214213025"
    assert json.loads((output_dir / "gaze.jsonl").read_text())["sample"] == {
        "system_time_stamp": 123
    }
    assert json.loads((output_dir / "events.jsonl").read_text())["name"] == (
        "task.started"
    )
    assert "Found 1 Tobii eye tracker." in (output_dir / "session.log").read_text()


def test_run_recording_session_writes_bids_and_display_metadata(tmp_path):
    output_root = tmp_path / "runs"
    output_dir = output_root / "sub-01" / "ses-baseline" / (
        "task-pupillary-light-reflex_run-02"
    )

    exit_code = run_recording_session(
        task_id="pupillary-light-reflex",
        tracker="none",
        output_dir=output_root,
        present=lambda event_sink: None,
        bids=BidsSessionMetadata(subject="01", session="baseline", run="02"),
        stimulus_display=StimulusDisplayMetadata(
            screen_distance_meters=0.6,
            screen_origin=("top", "left"),
            screen_resolution_pixels=(1920, 1080),
            screen_size_meters=(0.527, 0.296),
            psychopy_screen=1,
            fullscreen=True,
            window_size_pixels=(1024, 768),
        ),
    )

    assert exit_code == 0
    metadata = json.loads((output_dir / "session.json").read_text())
    assert metadata["bids"] == {
        "subject": "01",
        "session": "baseline",
        "run": "02",
    }
    assert metadata["stimulus_display"] == {
        "screen_distance_meters": 0.6,
        "screen_origin": ["top", "left"],
        "screen_resolution_pixels": [1920, 1080],
        "screen_size_meters": [0.527, 0.296],
        "psychopy_screen": 1,
        "fullscreen": True,
        "window_size_pixels": [1024, 768],
    }
    assert "calibration" not in metadata


def test_run_recording_session_records_latest_calibration_provenance(tmp_path):
    output_root = tmp_path / "sourcedata"
    calibration_dir = (
        output_root / "sub-01" / "ses-baseline" / "calibrations"
    )
    _write_calibration_artifact(
        calibration_dir / "calibration-20260819T160000Z",
        created_at="2026-08-19T16:00:00Z",
        serial_number="TPS-old",
        method="tobii-pro-eye-tracker-manager",
    )
    latest_metadata = _write_calibration_artifact(
        calibration_dir / "calibration-20260819T170000Z",
        created_at="2026-08-19T17:00:00Z",
        serial_number="TPS-new",
        method="child-friendly-sdk",
    )

    exit_code = run_recording_session(
        task_id="activity-monitoring",
        tracker="tobii",
        tracker_address="tobii-prp://169.254.10.180",
        output_dir=output_root,
        present=lambda event_sink: None,
        bids=BidsSessionMetadata(subject="01", session="baseline", run="01"),
        check_eyetracker=lambda **kwargs: 0,
        recorder_factory=lambda **kwargs: FakeRecorder(
            kwargs["gaze_path"], kwargs["tracker_metadata_path"]
        ),
    )

    run_dir = (
        output_root
        / "sub-01"
        / "ses-baseline"
        / "task-activity-monitoring_run-01"
    )
    metadata = json.loads((run_dir / "session.json").read_text())
    assert exit_code == 0
    assert metadata["calibration"] == {
        "artifact_dir": "../calibrations/calibration-20260819T170000Z",
        "calibration_id": "calibration-20260819T170000Z",
        "created_at": "2026-08-19T17:00:00Z",
        "metadata": latest_metadata,
        "metadata_file": (
            "../calibrations/calibration-20260819T170000Z/calibration.json"
        ),
        "method": "child-friendly-sdk",
        "tracker": {
            "serial_number": "TPS-new",
        },
    }


def test_run_recording_session_omits_calibration_provenance_for_no_tracker(tmp_path):
    output_root = tmp_path / "sourcedata"
    calibration_dir = output_root / "sub-01" / "ses-baseline" / "calibrations"
    _write_calibration_artifact(
        calibration_dir / "calibration-20260819T170000Z",
        created_at="2026-08-19T17:00:00Z",
        serial_number="TPS-new",
        method="child-friendly-sdk",
    )

    exit_code = run_recording_session(
        task_id="activity-monitoring",
        tracker="none",
        output_dir=output_root,
        present=lambda event_sink: None,
        bids=BidsSessionMetadata(subject="01", session="baseline", run="01"),
    )

    run_dir = (
        output_root
        / "sub-01"
        / "ses-baseline"
        / "task-activity-monitoring_run-01"
    )
    metadata = json.loads((run_dir / "session.json").read_text())
    assert exit_code == 0
    assert "calibration" not in metadata


def test_run_recording_session_normalizes_bids_labels_and_allocates_next_run(tmp_path):
    output_root = tmp_path / "runs"
    existing = output_root / "sub-01" / "ses-02" / (
        "task-pupillary-light-reflex_run-01"
    )
    existing.mkdir(parents=True)

    exit_code = run_recording_session(
        task_id="pupillary-light-reflex",
        tracker="none",
        output_dir=output_root,
        present=lambda event_sink: None,
        bids=BidsSessionMetadata(subject="sub-1", session="ses-2", run=None),
    )

    output_dir = output_root / "sub-01" / "ses-02" / (
        "task-pupillary-light-reflex_run-02"
    )
    assert exit_code == 0
    assert output_dir.exists()
    metadata = json.loads((output_dir / "session.json").read_text())
    assert metadata["bids"] == {
        "subject": "01",
        "session": "02",
        "run": "02",
    }


def test_run_recording_session_rejects_explicit_existing_bids_run(tmp_path, capsys):
    output_root = tmp_path / "runs"
    existing = output_root / "sub-01" / "ses-baseline" / (
        "task-pupillary-light-reflex_run-01"
    )
    existing.mkdir(parents=True)

    exit_code = run_recording_session(
        task_id="pupillary-light-reflex",
        tracker="none",
        output_dir=output_root,
        present=lambda event_sink: None,
        bids=BidsSessionMetadata(subject="1", session="baseline", run="1"),
    )

    assert exit_code != 0
    assert "already exists" in capsys.readouterr().err
