import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from aria_et.cli import build_parser
from aria_et.config import AriaEtConfig
from aria_et.gui import state
from aria_et.gui.pages.battery import BatteryPage
from aria_et.gui.widgets.task_card import PREVIEW_BUTTON_TEXT

pytestmark = pytest.mark.qt_gui

TASK_ID = "activity-monitoring"


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def config(tmp_path):
    return AriaEtConfig(data_root=tmp_path / "aria-data")


@pytest.fixture
def session(config):
    return state.SessionState(subject="abby", data_root=config.data_root)


def _open(page, session, *, tracker_checked=True):
    page.set_session(session)
    page.set_tracker_checked(tracker_checked)
    return page


def _write_events(run_dir, names):
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
        for name in names:
            handle.write(json.dumps({"name": name, "payload": {}}) + "\n")


def test_battery_blocks_running_until_the_tracker_check_passes(qapp, config, session):
    page = _open(BatteryPage(config), session, tracker_checked=False)

    assert not page._cards[TASK_ID]._run_button.isEnabled()


def test_battery_enables_running_once_preflight_is_met(qapp, config, session):
    page = _open(BatteryPage(config), session)

    assert page._cards[TASK_ID]._run_button.isEnabled()


def test_battery_keeps_preview_available_without_a_tracker(qapp, config, session):
    page = _open(BatteryPage(config), session, tracker_checked=False)

    assert page._cards[TASK_ID]._preview_button.isEnabled()


def test_preview_button_says_it_records_nothing(qapp, config, session):
    page = _open(BatteryPage(config), session)

    assert page._cards[TASK_ID]._preview_button.text() == PREVIEW_BUTTON_TEXT


def test_battery_emits_run_args_the_cli_accepts(qapp, config, session):
    page = _open(BatteryPage(config), session)
    emitted = []
    page.run_requested.connect(emitted.append)

    page._start_run(TASK_ID)

    assert emitted == [
        [
            "run-am",
            "--tracker",
            "tobii",
            "--subject",
            "abby",
            "--session",
            "01",
            "--output",
            str(session.sourcedata_root),
            "--fullscreen",
            "--screen",
            str(config.psychopy_screen),
        ]
    ]


@pytest.mark.parametrize("launch", ["_start_run", "_start_preview"])
def test_battery_argv_still_parses_against_the_real_cli(qapp, config, session, launch):
    page = _open(BatteryPage(config), session)
    page._debug_render.setChecked(True)
    page._sound.setChecked(False)
    page._trial_limit.setValue(3)
    emitted = []
    page.run_requested.connect(emitted.append)

    getattr(page, launch)(TASK_ID)

    build_parser(config).parse_args(emitted[0])


def test_battery_never_requests_an_explicit_run_label(qapp, config, session):
    page = _open(BatteryPage(config), session)
    emitted = []
    page.run_requested.connect(emitted.append)

    page._start_run(TASK_ID)

    assert "--run" not in emitted[0]


def test_battery_refuses_to_run_when_preflight_fails(qapp, config, session):
    page = _open(BatteryPage(config), session, tracker_checked=False)
    emitted = []
    page.run_requested.connect(emitted.append)

    page._start_run(TASK_ID)

    assert emitted == []


def test_battery_locks_the_other_cards_while_a_task_runs(qapp, config, session):
    page = _open(BatteryPage(config), session)

    page._start_run(TASK_ID)

    other = page._cards["social-interactive"]
    assert not other._run_button.isEnabled()
    assert not other._preview_button.isEnabled()
    assert not page._options_card.isEnabled()


def test_battery_swaps_run_for_stop_while_a_task_runs(qapp, config, session):
    page = _open(BatteryPage(config), session)

    page._start_run(TASK_ID)

    card = page._cards[TASK_ID]
    assert card._stop_button.isVisibleTo(card)
    assert not card._run_button.isVisibleTo(card)


def test_battery_tracks_trial_progress_from_the_new_run_directory(
    qapp, config, session
):
    page = _open(BatteryPage(config), session)
    page._start_run(TASK_ID)

    run_dir = session.sourcedata_root / "sub-abby" / "ses-01" / f"task-{TASK_ID}_run-01"
    _write_events(
        run_dir,
        [f"{TASK_ID}.started", f"{TASK_ID}.trial.started", f"{TASK_ID}.trial.ended"],
    )
    page._poll()

    assert page._active_run is not None
    assert page._active_run.run_label == "01"
    assert page._progress.trials_started == 1
    assert "trial 1" in page._cards[TASK_ID]._status.text()


def test_battery_flags_a_run_that_ended_without_a_completion_event(
    qapp, config, session
):
    page = _open(BatteryPage(config), session)
    page._start_run(TASK_ID)

    run_dir = session.sourcedata_root / "sub-abby" / "ses-01" / f"task-{TASK_ID}_run-01"
    _write_events(run_dir, [f"{TASK_ID}.started", f"{TASK_ID}.trial.started"])
    page.report_exit(0)

    assert page._cards[TASK_ID]._status.text().startswith("Incomplete")


def test_battery_marks_a_finished_run_complete(qapp, config, session):
    page = _open(BatteryPage(config), session)
    page._start_run(TASK_ID)

    run_dir = session.sourcedata_root / "sub-abby" / "ses-01" / f"task-{TASK_ID}_run-01"
    _write_events(run_dir, [f"{TASK_ID}.started", f"{TASK_ID}.ended"])
    page.report_exit(0)

    assert page._cards[TASK_ID]._status.text().startswith("Complete")


def test_battery_offers_the_next_run_label_after_a_run(qapp, config, session):
    page = _open(BatteryPage(config), session)
    page._start_run(TASK_ID)

    run_dir = session.sourcedata_root / "sub-abby" / "ses-01" / f"task-{TASK_ID}_run-01"
    _write_events(run_dir, [f"{TASK_ID}.started", f"{TASK_ID}.ended"])
    page.report_exit(0)

    assert page._cards[TASK_ID]._run_button.text() == "Run again (run-02)"


def test_preview_emits_demo_args_and_writes_no_entities(qapp, config, session):
    page = _open(BatteryPage(config), session)
    emitted = []
    page.run_requested.connect(emitted.append)

    page._start_preview(TASK_ID)

    assert emitted[0][0] == "demo-am"
    assert "--subject" not in emitted[0]
    assert "--output" not in emitted[0]


def test_preview_does_not_poll_for_artifacts(qapp, config, session):
    page = _open(BatteryPage(config), session)

    page._start_preview(TASK_ID)

    assert not page._timer.isActive()


def test_preview_leaves_the_card_status_untouched(qapp, config, session):
    page = _open(BatteryPage(config), session)
    run_dir = session.sourcedata_root / "sub-abby" / "ses-01" / f"task-{TASK_ID}_run-01"
    _write_events(run_dir, [f"{TASK_ID}.started", f"{TASK_ID}.ended"])
    page.set_session(session)

    page._start_preview(TASK_ID)
    page.report_exit(0)

    assert page._cards[TASK_ID]._status.text().startswith("Complete")


def test_battery_warns_about_dropped_gaze_samples(qapp, config, session):
    page = _open(BatteryPage(config), session)
    page._start_run(TASK_ID)

    run_dir = session.sourcedata_root / "sub-abby" / "ses-01" / f"task-{TASK_ID}_run-01"
    _write_events(run_dir, [f"{TASK_ID}.started"])
    (run_dir / "gaze_writer.json").write_text(
        json.dumps({"dropped_queue_samples": 42}), encoding="utf-8"
    )
    page._poll()

    card = page._cards[TASK_ID]
    assert card._warning.isVisibleTo(card)
    assert "42 gaze samples dropped" in card._warning.text()
