import pytest

pytest.importorskip("PySide6")

from aria_et.gui.artifacts import RunProgress, RunStatus, WriterHealth, next_run_label
from aria_et.gui.pages.battery import preflight_conditions
from aria_et.gui.state import RunMode, SessionState
from aria_et.gui.widgets.task_card import describe_dropped_samples, describe_progress


def _health(**overrides):
    fields = {
        "received": 0,
        "written": 0,
        "dropped": 0,
        "queued": 0,
        "flush_count": 0,
    }
    fields.update(overrides)
    return WriterHealth(**fields)


def _make_run(root, subject, session, task_id, run_label):
    run_dir = (
        root / f"sub-{subject}" / f"ses-{session}" / f"task-{task_id}_run-{run_label}"
    )
    run_dir.mkdir(parents=True)
    return run_dir


def test_next_run_label_starts_at_01(tmp_path):
    assert next_run_label(tmp_path, "abby", "01", "activity-monitoring") == "01"


def test_next_run_label_fills_the_first_free_slot(tmp_path):
    _make_run(tmp_path, "abby", "01", "activity-monitoring", "01")
    _make_run(tmp_path, "abby", "01", "activity-monitoring", "03")

    assert next_run_label(tmp_path, "abby", "01", "activity-monitoring") == "02"


def test_next_run_label_is_scoped_to_one_task(tmp_path):
    _make_run(tmp_path, "abby", "01", "social-interactive", "01")

    assert next_run_label(tmp_path, "abby", "01", "activity-monitoring") == "01"


def test_describe_progress_reports_the_current_trial(tmp_path):
    progress = RunProgress(
        started=True, trials_started=3, trials_ended=2, trial_count=4
    )

    assert describe_progress(RunStatus.RUNNING, progress) == "Running — trial 3 of 4"


def test_describe_progress_tolerates_an_unknown_trial_count():
    progress = RunProgress(started=True, trials_started=2)

    assert describe_progress(RunStatus.RUNNING, progress) == "Running — trial 2"


def test_describe_progress_counts_gaze_samples_when_complete():
    progress = RunProgress(started=True, ended=True, trials_ended=8, trial_count=8)

    summary = describe_progress(RunStatus.COMPLETE, progress, _health(written=122517))

    assert summary == "Complete — 8 trials, 122,517 gaze samples"


def test_describe_progress_names_an_incomplete_run_distinctly():
    progress = RunProgress(started=True, trials_started=3, trials_ended=2)

    summary = describe_progress(RunStatus.INCOMPLETE, progress)

    assert summary.startswith("Incomplete —")


def test_describe_dropped_samples_is_silent_when_nothing_dropped():
    assert describe_dropped_samples(_health(written=100)) is None


def test_describe_dropped_samples_warns_about_queue_pressure():
    assert describe_dropped_samples(_health(dropped=1250)) == (
        "1,250 gaze samples dropped — queue pressure."
    )


def test_preflight_reports_every_condition_unmet_without_a_session():
    conditions = preflight_conditions(None, tracker_checked=False)

    assert [met for _, met in conditions] == [False, False, False]


def test_preflight_still_blocks_on_the_tracker_with_a_session_open(tmp_path):
    session = SessionState(subject="abby", data_root=tmp_path)

    conditions = preflight_conditions(session, tracker_checked=False)

    assert {text.split(" (")[0]: met for text, met in conditions} == {
        "A session is open": True,
        "Data root is writable": True,
        "Tracker check has succeeded": False,
    }


def test_preflight_passes_once_the_tracker_check_succeeds(tmp_path):
    session = SessionState(subject="abby", data_root=tmp_path, mode=RunMode.DRY_RUN)

    conditions = preflight_conditions(session, tracker_checked=True)

    assert all(met for _, met in conditions)
