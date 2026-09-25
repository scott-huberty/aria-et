import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QComboBox

from aria_et.cli import build_parser
from aria_et.config import AriaEtConfig
from aria_et.gui import state
from aria_et.gui.artifacts import find_calibrations
from aria_et.gui.pages.calibration import (
    CHILD_FRIENDLY_ROUTINE,
    ETM_ROUTINE,
    NO_HISTORY_TEXT,
    CalibrationPage,
    resolve_manager_path,
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


def _write_calibration(session, calibration_id, method):
    directory = (
        session.sourcedata_root
        / "sub-abby"
        / "ses-01"
        / "calibrations"
        / calibration_id
    )
    directory.mkdir(parents=True)
    (directory / "calibration.json").write_text(
        json.dumps({"created_at": calibration_id[-8:], "method": method}),
        encoding="utf-8",
    )


def test_manager_path_falls_back_to_the_bundled_default(config):
    path, _ = resolve_manager_path(config)

    assert path.endswith("TobiiProEyeTrackerManager")


def test_manager_path_prefers_the_configured_executable(tmp_path):
    executable = tmp_path / "etm"
    executable.write_text("", encoding="utf-8")
    config = AriaEtConfig(eye_tracker_manager=str(executable))

    assert resolve_manager_path(config) == (str(executable), True)


def test_calibration_warns_when_the_manager_is_missing(qapp, config):
    page = CalibrationPage(config)

    _, exists = resolve_manager_path(config)
    assert page._manager_warning.isVisibleTo(page) is not exists


def test_calibration_hides_child_options_in_etm_mode(qapp, config):
    page = CalibrationPage(config)

    assert page.selected_routine() == ETM_ROUTINE
    assert not page._child_options.isVisibleTo(page)


def test_calibration_reveals_child_options_for_the_child_routine(qapp, config):
    page = CalibrationPage(config)

    page._routine.setCurrentIndex(1)

    assert page.selected_routine() == CHILD_FRIENDLY_ROUTINE
    assert page._child_options.isVisibleTo(page)
    assert not page._manager_label.isVisibleTo(page)


def test_calibration_needs_a_session_before_it_can_run(qapp, config):
    page = CalibrationPage(config)

    assert not page._calibrate_button.isEnabled()


def test_calibration_emits_args_the_cli_accepts(qapp, config, session):
    page = CalibrationPage(config)
    page.set_session(session)
    emitted = []
    page.calibrate_requested.connect(emitted.append)

    page._request_calibration()

    build_parser(config).parse_args(emitted[0])
    assert emitted[0][0] == "calibrate-eyetracker"
    assert "--subject" in emitted[0]
    assert "--session" in emitted[0]


def test_child_friendly_calibration_args_still_parse(qapp, config, session):
    page = CalibrationPage(config)
    page.set_session(session)
    page._routine.setCurrentIndex(1)
    page._advance_on_space.setChecked(True)
    page._sound.setChecked(False)
    emitted = []
    page.calibrate_requested.connect(emitted.append)

    page._request_calibration()

    build_parser(config).parse_args(emitted[0])
    assert "--advance-on-space" in emitted[0]
    assert "--point-duration" in emitted[0]


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


@pytest.mark.parametrize("field", ["_routine", "_point_duration", "_screen"])
def test_mouse_wheel_does_not_change_calibration_inputs(qapp, config, field):
    page = CalibrationPage(config)
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
