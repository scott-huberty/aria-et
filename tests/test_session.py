import json

from aria_et.runtime import RuntimeEvent
from aria_et.session import run_recording_session


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


def test_run_recording_session_fails_fast_for_tobii_until_backend_is_wired(tmp_path, capsys):
    calls = []

    def check_eyetracker(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = run_recording_session(
        task_id="activity-monitoring",
        tracker="tobii",
        tracker_address="tobii-prp://169.254.10.180",
        output_dir=tmp_path / "run-am",
        present=lambda event_sink: None,
        check_eyetracker=check_eyetracker,
    )

    assert exit_code != 0
    assert calls == [{"address": "tobii-prp://169.254.10.180"}]
    assert "not implemented yet" in capsys.readouterr().err
