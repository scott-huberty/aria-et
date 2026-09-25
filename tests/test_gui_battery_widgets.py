import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QStyle,
    QStyleFactory,
    QStyleOptionSpinBox,
)

from aria_et.cli import build_parser
from aria_et.config import AriaEtConfig
from aria_et.gui import state
from aria_et.gui.pages.battery import (
    CUSTOM_SETTINGS_NOTICE,
    EDIT_SETTINGS_TEXT,
    LOCK_SETTINGS_TEXT,
    BatteryPage,
)
from aria_et.gui.theme import stylesheet
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


def test_window_size_is_locked_while_fullscreen_is_checked(qapp, config):
    page = BatteryPage(config)
    page._edit_settings_button.click()

    assert page._fullscreen.isChecked()
    assert not page._window_size.isEnabled()

    page._fullscreen.setChecked(False)
    assert page._window_size.isEnabled()

    page._fullscreen.setChecked(True)
    assert not page._window_size.isEnabled()


def test_window_size_stays_locked_after_a_run_unlocks_the_options(
    qapp, config, session
):
    page = _open(BatteryPage(config), session)
    page._edit_settings_button.click()

    page._set_shared_controls_enabled(False)
    page._set_shared_controls_enabled(True)

    assert page._options_card.isEnabled()
    assert page._screen.isEnabled()
    assert not page._window_size.isEnabled()


def test_presentation_settings_start_locked_at_the_defaults(qapp, config):
    page = BatteryPage(config)

    assert not page._settings_fields.isEnabled()
    assert page._edit_settings_button.text() == EDIT_SETTINGS_TEXT
    assert page.presentation_options() == page.default_presentation_options()
    assert page._custom_notice.isHidden()
    assert not page._restore_defaults_button.isEnabled()


def test_change_settings_unlocks_and_relocks_the_fields(qapp, config):
    page = BatteryPage(config)

    page._edit_settings_button.click()
    assert page._settings_fields.isEnabled()
    assert page._edit_settings_button.text() == LOCK_SETTINGS_TEXT

    page._edit_settings_button.click()
    assert not page._settings_fields.isEnabled()
    assert page._edit_settings_button.text() == EDIT_SETTINGS_TEXT


def test_finishing_a_task_does_not_unlock_the_settings(qapp, config, session):
    page = _open(BatteryPage(config), session)

    page._set_shared_controls_enabled(False)
    page._set_shared_controls_enabled(True)

    assert not page._settings_fields.isEnabled()


@pytest.fixture
def windows11_style(qapp):
    """The overlap only happens with Qt's windows11 style (side-by-side arrows)."""
    available_styles = QStyleFactory.keys()  # a list, not a dict
    if "windows11" not in available_styles:
        pytest.skip("Qt's windows11 style is only available on Windows")
    original = qapp.style().name()
    qapp.setStyle("windows11")
    yield
    qapp.setStyle(original)


@pytest.mark.parametrize("field", ["_screen", "_trial_limit"])
def test_spin_box_text_does_not_cover_the_arrow_buttons(
    qapp, windows11_style, config, field
):
    # With the app stylesheet, Qt's windows11 style let the text field cover
    # the up arrow, so clicks on it edited text instead of stepping the value.
    page = BatteryPage(config)
    page.setStyleSheet(stylesheet())
    page.resize(700, 1000)
    page.show()
    page._edit_settings_button.click()
    qapp.processEvents()
    spin_box = getattr(page, field)

    option = QStyleOptionSpinBox()
    spin_box.initStyleOption(option)

    def arrow(sub_control):
        return spin_box.style().subControlRect(
            QStyle.ComplexControl.CC_SpinBox, option, sub_control, spin_box
        )

    text_field = spin_box.findChild(QLineEdit).geometry()
    assert not text_field.intersects(arrow(QStyle.SubControl.SC_SpinBoxUp))
    assert not text_field.intersects(arrow(QStyle.SubControl.SC_SpinBoxDown))
    page.close()


@pytest.mark.parametrize("field", ["_screen", "_trial_limit"])
def test_mouse_wheel_does_not_change_spin_boxes(qapp, config, field):
    page = BatteryPage(config)
    page._edit_settings_button.click()
    spin_box = getattr(page, field)
    before = spin_box.value()

    wheel = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(spin_box, wheel)

    assert spin_box.value() == before
    assert not wheel.isAccepted()  # left for the page's scroll area


def test_custom_settings_show_a_notice_until_defaults_are_restored(qapp, config):
    page = BatteryPage(config)
    page._edit_settings_button.click()

    page._trial_limit.setValue(2)
    assert not page._custom_notice.isHidden()
    assert page._custom_notice.text() == CUSTOM_SETTINGS_NOTICE
    assert page._restore_defaults_button.isEnabled()

    page._restore_defaults_button.click()
    assert page.presentation_options() == page.default_presentation_options()
    assert page.presentation_options().trial_limit is None
    assert page._custom_notice.isHidden()
    assert not page._settings_fields.isEnabled()


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
