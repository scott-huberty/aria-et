import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit

from aria_et.cli import build_parser
from aria_et.config import AriaEtConfig
from aria_et.gui import state
from aria_et.gui.artifacts import find_calibrations
from aria_et.gui.pages.calibration import (
    NO_HISTORY_TEXT,
    NO_QUALITY_TEXT,
    NO_VALIDATION_TEXT,
    VALIDATION_SKIPPED_TEXT,
    CalibrationPage,
)

pytestmark = pytest.mark.qt_gui


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def config(tmp_path):
    return AriaEtConfig(data_root=tmp_path / "aria-data")


@pytest.fixture
def session(config):
    return state.SessionState(subject="abby", data_root=config.data_root)


def _write_calibration(session, calibration_id, method, validation=None):
    directory = (
        session.sourcedata_root
        / "sub-abby"
        / "ses-01"
        / "calibrations"
        / calibration_id
    )
    directory.mkdir(parents=True)
    metadata = {"created_at": calibration_id[-8:], "method": method}
    if validation is not None:
        metadata["validation"] = validation
    (directory / "calibration.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )


VALIDATION = {
    "status": "complete",
    "points_adcs": [[0.5, 0.5]] * 5,
    "points": [{"target_adcs": [0.5, 0.5]}] * 5,
    "summary": {
        "left": {
            "accuracy_deg": 0.761,
            "max_accuracy_deg": 1.2,
            "precision_rms_deg": 0.07,
            "data_loss": 0.0,
        },
        "right": {
            "accuracy_deg": 0.94,
            "max_accuracy_deg": 1.4,
            "precision_rms_deg": None,
            "data_loss": 0.125,
        },
    },
}


def _quality_table(page):
    return [
        (left.text(), right.text()) for left, right in page._quality_cells
    ]


def test_calibration_page_has_no_routine_or_tracker_choice(qapp, config):
    page = CalibrationPage(config)

    # Only the window size (WxH) is free text; no serial-number box. (Qt's
    # spin boxes contain an internal line edit, which doesn't count.)
    line_edits = [
        widget
        for widget in page.findChildren(QLineEdit)
        if widget.objectName() != "qt_spinbox_lineedit"
    ]
    assert line_edits == [page._window_size]
    assert page.findChildren(QComboBox) == []
    assert not hasattr(page, "_routine")


def test_calibration_defaults_to_the_stimulus_screen(qapp):
    config = AriaEtConfig(etm_screen=2, psychopy_screen=1)
    page = CalibrationPage(config)

    # The child-friendly PsychoPy window must open on the EIZO display.
    assert page.calibration_options().screen == 1


def test_child_friendly_defaults(qapp, config):
    page = CalibrationPage(config)

    options = page.calibration_options()

    assert options.fullscreen is True
    assert options.play_sound is True


def test_calibration_settings_start_locked(qapp, config):
    page = CalibrationPage(config)

    assert not page._settings_fields.isEnabled()
    assert not page._custom_notice.isVisibleTo(page)
    assert not page._restore_defaults_button.isEnabled()

    page._edit_settings_button.click()
    assert page._settings_fields.isEnabled()


def test_custom_calibration_settings_show_a_notice_until_restored(qapp, config):
    page = CalibrationPage(config)
    page._edit_settings_button.click()

    page._sound.setChecked(False)

    assert page._custom_notice.isVisibleTo(page)
    assert page._restore_defaults_button.isEnabled()

    page._restore_defaults_button.click()

    assert page.calibration_options().play_sound is True
    assert not page._custom_notice.isVisibleTo(page)
    assert not page._settings_fields.isEnabled()


def test_calibration_needs_a_session_before_it_can_run(qapp, config):
    page = CalibrationPage(config)

    assert not page._calibrate_button.isEnabled()


def test_calibration_emits_args_the_cli_accepts(qapp, config, session):
    page = CalibrationPage(config)
    page.set_session(session)
    emitted = []
    page.calibrate_requested.connect(emitted.append)

    page._request_calibration()

    args = build_parser(config).parse_args(emitted[0])
    assert emitted[0][0] == "calibrate-eyetracker"
    assert args.routine == "child-friendly"
    assert args.screen == config.psychopy_screen
    assert "--subject" in emitted[0]
    assert "--session" in emitted[0]
    for flag in ("--serial-number", "--manager"):
        assert flag not in emitted[0]


def test_child_friendly_calibration_args_still_parse(qapp, config, session):
    page = CalibrationPage(config)
    page.set_session(session)
    page._sound.setChecked(False)
    emitted = []
    page.calibrate_requested.connect(emitted.append)

    page._request_calibration()

    build_parser(config).parse_args(emitted[0])
    assert "--no-sound" in emitted[0]
    # The DeToX procedure settings are not exposed; the CLI defaults apply.
    for flag in ("--points", "--no-shuffle", "--animation", "--skip-positioning"):
        assert flag not in emitted[0]


def test_calibration_history_is_empty_for_a_fresh_session(qapp, config, session):
    page = CalibrationPage(config)
    page.set_session(session)

    assert page._history.text() == NO_HISTORY_TEXT


def test_calibration_history_lists_newest_first(qapp, config, session):
    _write_calibration(session, "calibration-20260101", "etm")
    _write_calibration(session, "calibration-20260202", "child-friendly")
    page = CalibrationPage(config)

    page.set_session(session)

    lines = page._history.text().splitlines()
    assert "child-friendly" in lines[0]
    assert "etm" in lines[1]


def test_find_calibrations_tolerates_missing_metadata(tmp_path):
    directory = (
        tmp_path / "sub-abby" / "ses-01" / "calibrations" / "calibration-20260101"
    )
    directory.mkdir(parents=True)

    records = find_calibrations(tmp_path, "abby", "01")

    assert len(records) == 1
    assert records[0].method is None


def test_calibration_re_enables_its_button_after_a_refused_start(qapp, config, session):
    page = CalibrationPage(config)
    page.set_session(session)

    page._request_calibration()
    assert not page._calibrate_button.isEnabled()

    page.report_exit(1)

    assert page._calibrate_button.isEnabled()


@pytest.mark.parametrize("field", ["_screen"])
def test_mouse_wheel_does_not_change_calibration_inputs(qapp, config, field):
    page = CalibrationPage(config)
    page._edit_settings_button.click()  # locked fields ignore input anyway
    widget = getattr(page, field)

    def current():
        return widget.currentIndex() if isinstance(widget, QComboBox) else widget.value()

    before = current()
    for delta in (120, -120):  # both directions, so neither end of a range hides it
        wheel = QWheelEvent(
            QPointF(5, 5),
            QPointF(5, 5),
            QPoint(0, 0),
            QPoint(0, delta),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(widget, wheel)
        assert not wheel.isAccepted()  # left for the page's scroll area

    assert current() == before


def test_quality_table_shows_the_latest_validation(qapp, config, session):
    _write_calibration(session, "calibration-20260101", "child-friendly-detox")
    _write_calibration(
        session, "calibration-20260202", "child-friendly-detox", VALIDATION
    )
    page = CalibrationPage(config)

    page.set_session(session)

    assert page._quality_grid.isVisibleTo(page)
    assert _quality_table(page) == [
        ("0.76", "0.94"),
        ("0.07", "n/a"),
        ("0", "12"),
    ]
    assert "validated at 5 targets" in page._quality_status.text()
    latest = page._history.text().splitlines()[0]
    assert "accuracy L 0.76° R 0.94°" in latest
    assert "—  child friendly  —" in latest
    assert "detox" not in latest.lower()


def test_quality_card_explains_a_skipped_validation(qapp, config, session):
    _write_calibration(
        session,
        "calibration-20260202",
        "child-friendly-detox",
        {"status": "skipped", "points": [], "summary": None},
    )
    page = CalibrationPage(config)

    page.set_session(session)

    assert page._quality_status.text() == VALIDATION_SKIPPED_TEXT
    assert not page._quality_grid.isVisibleTo(page)


def test_quality_card_explains_a_calibration_without_validation(
    qapp, config, session
):
    _write_calibration(session, "calibration-20260202", "tobii-pro-eye-tracker-manager")
    page = CalibrationPage(config)

    page.set_session(session)

    assert page._quality_status.text() == NO_VALIDATION_TEXT
    assert not page._quality_grid.isVisibleTo(page)


def test_quality_card_without_a_session(qapp, config):
    page = CalibrationPage(config)

    assert page._quality_status.text() == NO_QUALITY_TEXT
    assert not page._quality_grid.isVisibleTo(page)
