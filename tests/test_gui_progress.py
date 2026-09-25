import json

import pytest

from aria_et import tasks
from aria_et.gui import state
from aria_et.gui.progress import PageProgress, page_progress

SETUP, HARDWARE, CALIBRATION, BATTERY, EXPORT = range(5)


@pytest.fixture
def session(tmp_path):
    return state.SessionState(subject="abby", data_root=tmp_path / "aria-data")


def _session_dir(session):
    return session.sourcedata_root / "sub-abby" / "ses-01"


def _write_run(session, task_id, run_label, event_names):
    run_dir = _session_dir(session) / f"task-{task_id}_run-{run_label}"
    run_dir.mkdir(parents=True)
    with (run_dir / "events.jsonl").open("w", encoding="utf-8") as handle:
        for name in event_names:
            handle.write(json.dumps({"name": name, "payload": {}}) + "\n")


def _complete_run(session, task_id, run_label="01"):
    _write_run(session, task_id, run_label, [f"{task_id}.started", f"{task_id}.ended"])


def _progress(session, *, tracker_connected=False, export_succeeded=False):
    return page_progress(
        session,
        tracker_connected=tracker_connected,
        export_succeeded=export_succeeded,
    )


def test_nothing_is_done_without_a_session():
    progress = _progress(None)

    assert progress == (PageProgress(done=False),) * 5


def test_the_tracker_check_counts_even_without_a_session():
    # Hardware is reachable before a session opens, so its check stands alone.
    assert _progress(None, tracker_connected=True)[HARDWARE].done


def test_an_open_session_completes_setup_only(session):
    progress = _progress(session)

    assert progress[SETUP].done
    assert not progress[HARDWARE].done
    assert not progress[CALIBRATION].done
    assert progress[BATTERY] == PageProgress(
        done=False, detail=f"0/{len(tasks.STANDALONE_TASKS)}"
    )
    assert not progress[EXPORT].done


def test_a_recorded_calibration_completes_calibration(session):
    calibration = _session_dir(session) / "calibrations" / "calibration-20260925T120000"
    calibration.mkdir(parents=True)

    assert _progress(session)[CALIBRATION].done


def test_battery_counts_completed_tasks(session):
    first, second = (task.task_id for task in tasks.STANDALONE_TASKS[:2])
    _complete_run(session, first)
    _write_run(session, second, "01", [f"{second}.started"])  # stopped early

    battery = _progress(session)[BATTERY]

    assert not battery.done
    assert battery.detail == f"1/{len(tasks.STANDALONE_TASKS)}"


def test_a_later_incomplete_rerun_does_not_undo_a_completed_task(session):
    task_id = tasks.STANDALONE_TASKS[0].task_id
    _complete_run(session, task_id, "01")
    _write_run(session, task_id, "02", [f"{task_id}.started"])

    assert _progress(session)[BATTERY].detail.startswith("1/")


def test_battery_is_done_once_every_task_completed(session):
    for task in tasks.STANDALONE_TASKS:
        _complete_run(session, task.task_id)

    total = len(tasks.STANDALONE_TASKS)
    assert _progress(session)[BATTERY] == PageProgress(
        done=True, detail=f"{total}/{total}"
    )


def test_export_follows_the_last_export_result(session):
    assert _progress(session, export_succeeded=True)[EXPORT].done
    assert not _progress(session, export_succeeded=False)[EXPORT].done
