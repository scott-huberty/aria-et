import json

import pytest

pytest.importorskip("PySide6")

from aria_et.config import AriaEtConfig
from aria_et.gui import state
from aria_et.gui.artifacts import RunStatus
from aria_et.gui.pages.export import (
    describe_candidate,
    find_export_candidates,
    parse_written_files,
)


@pytest.fixture
def config(tmp_path):
    return AriaEtConfig(data_root=tmp_path / "aria-data")


@pytest.fixture
def session(config):
    return state.SessionState(subject="abby", data_root=config.data_root)


def _write_run(session, task_id, run_label, *, events=(), tracker="tobii", gaze=True):
    directory = (
        session.sourcedata_root
        / "sub-abby"
        / f"ses-{session.session}"
        / f"task-{task_id}_run-{run_label}"
    )
    directory.mkdir(parents=True)
    (directory / "session.json").write_text(
        json.dumps({"tracker": tracker}), encoding="utf-8"
    )
    (directory / "events.jsonl").write_text(
        "".join(json.dumps({"name": name}) + "\n" for name in events),
        encoding="utf-8",
    )
    if gaze:
        (directory / "gaze.jsonl").write_text('{"x": 0}\n', encoding="utf-8")
    return directory


def _complete(task_id):
    return (f"{task_id}.started", f"{task_id}.ended")


def test_export_candidates_are_empty_for_a_fresh_session(session):
    assert (
        find_export_candidates(session.sourcedata_root, "abby", session.session) == []
    )


def test_export_candidates_classify_a_completed_run(session):
    _write_run(
        session, "activity-monitoring", "01", events=_complete("activity-monitoring")
    )

    candidates = find_export_candidates(
        session.sourcedata_root, "abby", session.session
    )

    assert len(candidates) == 1
    assert candidates[0].status is RunStatus.COMPLETE
    assert not candidates[0].no_gaze
    assert candidates[0].checked_by_default


def test_export_candidates_flag_a_run_that_never_ended(session):
    _write_run(
        session, "activity-monitoring", "01", events=("activity-monitoring.started",)
    )

    candidate = find_export_candidates(
        session.sourcedata_root, "abby", session.session
    )[0]

    assert candidate.status is RunStatus.INCOMPLETE
    assert not candidate.checked_by_default


def test_export_candidates_flag_a_dry_run_as_having_no_gaze(session):
    _write_run(
        session,
        "activity-monitoring",
        "01",
        events=_complete("activity-monitoring"),
        tracker="none",
    )

    candidate = find_export_candidates(
        session.sourcedata_root, "abby", session.session
    )[0]

    assert candidate.no_gaze
    assert not candidate.checked_by_default


def test_describe_candidate_names_the_task_and_run(session):
    _write_run(
        session, "social-interactive", "02", events=_complete("social-interactive")
    )

    candidate = find_export_candidates(
        session.sourcedata_root, "abby", session.session
    )[0]

    assert describe_candidate(candidate) == "Social Interactive  —  run-02  —  complete"


def test_parse_written_files_collects_the_paths_after_the_summary():
    lines = [
        "some unrelated warning",
        "Exported BIDS eyetracking files to /data/bids.",
        "/data/bids/sub-abby/eyetrack.tsv.gz",
        "/data/bids/sub-abby/eyetrack.json",
    ]

    assert parse_written_files(lines) == [
        "/data/bids/sub-abby/eyetrack.tsv.gz",
        "/data/bids/sub-abby/eyetrack.json",
    ]


def test_parse_written_files_is_empty_without_a_summary_line():
    assert parse_written_files(["Traceback (most recent call last):"]) == []
