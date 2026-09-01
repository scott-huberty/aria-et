import json

import pytest

from aria_et.gui import artifacts

TASK_ID = "activity-monitoring"


def make_run_dir(sourcedata_root, subject="abby", session="01", task=TASK_ID, run="01"):
    run_dir = (
        sourcedata_root / f"sub-{subject}" / f"ses-{session}" / f"task-{task}_run-{run}"
    )
    run_dir.mkdir(parents=True)
    return run_dir


def event(name, **payload):
    return {"name": name, "timestamp": 0.0, "payload": payload}


def test_find_run_directories_returns_nothing_for_a_missing_session(tmp_path):
    assert artifacts.find_run_directories(tmp_path, "abby", "01") == []


def test_find_run_directories_parses_task_and_run_labels(tmp_path):
    make_run_dir(tmp_path, run="01")
    make_run_dir(tmp_path, task="social-interactive", run="02")

    runs = artifacts.find_run_directories(tmp_path, "abby", "01")

    assert [(run.task_id, run.run_label) for run in runs] == [
        (TASK_ID, "01"),
        ("social-interactive", "02"),
    ]


def test_find_run_directories_filters_by_task(tmp_path):
    make_run_dir(tmp_path)
    make_run_dir(tmp_path, task="social-interactive")

    runs = artifacts.find_run_directories(tmp_path, "abby", "01", TASK_ID)

    assert [run.task_id for run in runs] == [TASK_ID]


def test_find_run_directories_ignores_unrelated_entries(tmp_path):
    session_dir = tmp_path / "sub-abby" / "ses-01"
    (session_dir / "calibrations").mkdir(parents=True)
    (session_dir / "notes.txt").write_text("hello", encoding="utf-8")

    assert artifacts.find_run_directories(tmp_path, "abby", "01") == []


def test_classify_session_treats_calibrations_only_as_new(tmp_path):
    (tmp_path / "sub-abby" / "ses-01" / "calibrations").mkdir(parents=True)

    assert (
        artifacts.classify_session(tmp_path, "abby", "01")
        is artifacts.SessionOpenState.NEW
    )


def test_classify_session_detects_existing_task_data(tmp_path):
    make_run_dir(tmp_path)

    assert (
        artifacts.classify_session(tmp_path, "abby", "01")
        is artifacts.SessionOpenState.HAS_DATA
    )


def test_next_free_session_label_skips_sessions_with_data(tmp_path):
    make_run_dir(tmp_path, session="01")
    make_run_dir(tmp_path, session="02")

    assert artifacts.next_free_session_label(tmp_path, "abby") == "03"


def test_find_new_run_directory_detects_the_directory_the_cli_created(tmp_path):
    make_run_dir(tmp_path, run="01")
    snapshot = artifacts.snapshot_run_directories(tmp_path, "abby", "01", TASK_ID)
    make_run_dir(tmp_path, run="02")

    created = artifacts.find_new_run_directory(
        snapshot, tmp_path, "abby", "01", TASK_ID
    )

    assert created is not None
    assert created.run_label == "02"


def test_find_new_run_directory_returns_none_when_nothing_appeared(tmp_path):
    make_run_dir(tmp_path)
    snapshot = artifacts.snapshot_run_directories(tmp_path, "abby", "01", TASK_ID)

    assert (
        artifacts.find_new_run_directory(snapshot, tmp_path, "abby", "01", TASK_ID)
        is None
    )


def test_apply_events_counts_trials_and_records_the_reported_total():
    progress = artifacts.apply_events(
        artifacts.RunProgress(),
        [
            event(f"{TASK_ID}.started", sequence_id="abcct"),
            event(f"{TASK_ID}.trial.started", trial_id="t1"),
            event(f"{TASK_ID}.trial.ended", trial_id="t1"),
            event(f"{TASK_ID}.ended", trial_count=4),
        ],
        TASK_ID,
    )

    assert progress.started
    assert progress.ended
    assert progress.trials_started == 1
    assert progress.trials_ended == 1
    assert progress.trial_count == 4


def test_apply_events_accumulates_across_polls():
    first = artifacts.apply_events(
        artifacts.RunProgress(), [event(f"{TASK_ID}.trial.started")], TASK_ID
    )
    second = artifacts.apply_events(first, [event(f"{TASK_ID}.trial.started")], TASK_ID)

    assert second.trials_started == 2


def test_apply_events_ignores_events_from_another_task():
    progress = artifacts.apply_events(
        artifacts.RunProgress(), [event("social-interactive.started")], TASK_ID
    )

    assert not progress.started


@pytest.mark.parametrize(
    ("progress", "process_running", "exit_code", "expected"),
    [
        (artifacts.RunProgress(), False, None, artifacts.RunStatus.NOT_STARTED),
        (artifacts.RunProgress(started=True), True, None, artifacts.RunStatus.RUNNING),
        (
            artifacts.RunProgress(started=True, ended=True),
            False,
            0,
            artifacts.RunStatus.COMPLETE,
        ),
        (
            artifacts.RunProgress(started=True),
            False,
            0,
            artifacts.RunStatus.INCOMPLETE,
        ),
        (artifacts.RunProgress(started=True), False, 3, artifacts.RunStatus.FAILED),
        (artifacts.RunProgress(), False, 2, artifacts.RunStatus.FAILED),
    ],
)
def test_derive_status(progress, process_running, exit_code, expected):
    assert (
        artifacts.derive_status(
            progress, process_running=process_running, exit_code=exit_code
        )
        is expected
    )


def test_derive_status_reports_a_crash_that_exited_zero_as_incomplete():
    progress = artifacts.RunProgress(started=True, trials_started=3, trials_ended=3)

    assert (
        artifacts.derive_status(progress, process_running=False, exit_code=0)
        is artifacts.RunStatus.INCOMPLETE
    )


def test_json_lines_tail_returns_only_new_complete_lines(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(event("a")) + "\n", encoding="utf-8")
    tail = artifacts.JsonLinesTail(path)

    assert [record["name"] for record in tail.read_new()] == ["a"]
    assert tail.read_new() == []

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event("b")) + "\n")

    assert [record["name"] for record in tail.read_new()] == ["b"]


def test_json_lines_tail_waits_for_a_torn_line_to_be_completed(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text('{"name": "a", "time', encoding="utf-8")
    tail = artifacts.JsonLinesTail(path)

    assert tail.read_new() == []

    path.write_text(json.dumps(event("a")) + "\n", encoding="utf-8")

    assert [record["name"] for record in tail.read_new()] == ["a"]


def test_json_lines_tail_skips_unparseable_lines(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text("not json\n" + json.dumps(event("a")) + "\n", encoding="utf-8")

    assert [record["name"] for record in artifacts.JsonLinesTail(path).read_new()] == [
        "a"
    ]


def test_json_lines_tail_tolerates_a_missing_file(tmp_path):
    assert artifacts.JsonLinesTail(tmp_path / "events.jsonl").read_new() == []


def test_dry_run_metadata_is_detected_from_the_tracker_field(tmp_path):
    run_dir = make_run_dir(tmp_path)
    (run_dir / "session.json").write_text(
        json.dumps({"task_id": TASK_ID, "tracker": "none"}), encoding="utf-8"
    )

    metadata = artifacts.read_session_metadata(run_dir)

    assert artifacts.is_dry_run_metadata(metadata)


def test_acquisition_metadata_is_not_flagged_as_dry_run(tmp_path):
    run_dir = make_run_dir(tmp_path)
    (run_dir / "session.json").write_text(
        json.dumps({"task_id": TASK_ID, "tracker": "tobii"}), encoding="utf-8"
    )

    assert not artifacts.is_dry_run_metadata(artifacts.read_session_metadata(run_dir))


def test_read_session_metadata_returns_none_when_absent(tmp_path):
    assert artifacts.read_session_metadata(make_run_dir(tmp_path)) is None


def test_has_gaze_requires_a_non_empty_file(tmp_path):
    run_dir = make_run_dir(tmp_path)

    assert not artifacts.has_gaze(run_dir)

    (run_dir / "gaze.jsonl").write_text("", encoding="utf-8")
    assert not artifacts.has_gaze(run_dir)

    (run_dir / "gaze.jsonl").write_text('{"x": 0}\n', encoding="utf-8")
    assert artifacts.has_gaze(run_dir)


def test_read_writer_health_maps_the_recorder_keys(tmp_path):
    run_dir = make_run_dir(tmp_path)
    (run_dir / "gaze_writer.json").write_text(
        json.dumps(
            {
                "received_queue_samples": 1200,
                "written_queue_samples": 1195,
                "dropped_queue_samples": 5,
                "queued_samples": 0,
                "flush_count": 12,
            }
        ),
        encoding="utf-8",
    )

    health = artifacts.read_writer_health(run_dir)

    assert health == artifacts.WriterHealth(
        received=1200, written=1195, dropped=5, queued=0, flush_count=12
    )


def test_read_writer_health_returns_none_when_absent(tmp_path):
    assert artifacts.read_writer_health(make_run_dir(tmp_path)) is None
