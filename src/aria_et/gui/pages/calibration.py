"""Calibration page: routine selection, ETM path check, and history."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from aria_et.config import AriaEtConfig
from aria_et.eyetracker import DEFAULT_EYETRACKER_MANAGER_PATH
from aria_et.gui import artifacts
from aria_et.gui.state import CalibrationOptions, SessionState, build_calibrate_args

ETM_ROUTINE = "etm"
CHILD_FRIENDLY_ROUTINE = "child-friendly"

ESCAPE_NOTE = (
    "Child-friendly calibration accepts Escape to abort. The four task runners do not."
)

NO_HISTORY_TEXT = "No calibrations yet for this session."

HISTORY_PREAMBLE = (
    "A run records the most recent calibration under the same subject and "
    "session, newest first:"
)


def resolve_manager_path(config: AriaEtConfig) -> tuple[str, bool]:
    """Return the manager executable the CLI will use and whether it exists."""
    path = config.eye_tracker_manager or DEFAULT_EYETRACKER_MANAGER_PATH
    return path, Path(path).exists()


def describe_calibration(record: artifacts.CalibrationRecord) -> str:
    method = record.method or "unknown method"
    return f"{record.created_at or record.calibration_id}  —  {method}"


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(10)
    heading = QLabel(title)
    heading.setObjectName("SectionHeading")
    layout.addWidget(heading)
    return frame, layout


def _helper(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("HelperText")
    label.setWordWrap(True)
    return label


class CalibrationPage(QWidget):
    calibrate_requested = Signal(list)

    def __init__(self, config: AriaEtConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._session: SessionState | None = None

        heading = QLabel("Calibration")
        heading.setObjectName("PageHeading")

        routine_card, routine_layout = _card("Routine")
        self._routine = QComboBox()
        self._routine.addItem("Eye Tracker Manager", ETM_ROUTINE)
        self._routine.addItem("Child-friendly", CHILD_FRIENDLY_ROUTINE)
        self._routine.currentIndexChanged.connect(self._on_routine_changed)
        routine_layout.addWidget(self._routine)

        self._manager_label = _helper("")
        self._manager_warning = QLabel()
        self._manager_warning.setObjectName("ModeBanner")
        self._manager_warning.setWordWrap(True)
        routine_layout.addWidget(self._manager_label)
        routine_layout.addWidget(self._manager_warning)

        self._child_options, child_layout = _card("Child-friendly options")
        child_form = QFormLayout()
        child_form.setVerticalSpacing(6)
        self._point_duration = QDoubleSpinBox()
        self._point_duration.setRange(0.5, 30.0)
        self._point_duration.setSingleStep(0.5)
        self._point_duration.setValue(3.0)
        self._point_duration.setSuffix(" s")
        self._advance_on_space = QCheckBox("Advance on space")
        self._fullscreen = QCheckBox("Fullscreen")
        self._fullscreen.setChecked(True)
        self._window_size = QLineEdit("1024x768")
        self._sound = QCheckBox("Play sound")
        self._sound.setChecked(True)
        self._debug_render = QCheckBox("Debug render overlay")
        child_form.addRow("Point duration", self._point_duration)
        child_form.addRow("Advance", self._advance_on_space)
        child_form.addRow("Display", self._fullscreen)
        child_form.addRow("Window size", self._window_size)
        child_form.addRow("Sound", self._sound)
        child_form.addRow("Diagnostics", self._debug_render)
        child_layout.addLayout(child_form)
        child_layout.addWidget(_helper(ESCAPE_NOTE))

        tracker_card, tracker_layout = _card("Tracker")
        self._screen = QSpinBox()
        self._screen.setRange(0, 8)
        self._screen.setValue(config.etm_screen)
        self._serial = QLineEdit()
        self._serial.setPlaceholderText("Optional — leave blank to auto-detect")
        tracker_form = QFormLayout()
        tracker_form.setVerticalSpacing(6)
        tracker_form.addRow("Screen", self._screen)
        tracker_form.addRow("Serial number", self._serial)
        tracker_layout.addLayout(tracker_form)

        self._calibrate_button = QPushButton("Run calibration")
        self._calibrate_button.setObjectName("Primary")
        self._calibrate_button.clicked.connect(self._request_calibration)
        tracker_layout.addWidget(self._calibrate_button)

        history_card, history_layout = _card("Calibration history")
        history_layout.addWidget(_helper(HISTORY_PREAMBLE))
        self._history = QLabel()
        self._history.setObjectName("HelperText")
        self._history.setWordWrap(True)
        history_layout.addWidget(self._history)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        layout.addWidget(heading)
        layout.addWidget(routine_card)
        layout.addWidget(self._child_options)
        layout.addWidget(tracker_card)
        layout.addWidget(history_card)
        layout.addStretch(1)

        self._on_routine_changed()
        self.refresh()

    def set_session(self, session: SessionState | None) -> None:
        self._session = session
        self.refresh()

    def selected_routine(self) -> str:
        return self._routine.currentData()

    def calibration_options(self) -> CalibrationOptions:
        routine = self.selected_routine()
        manager, _ = resolve_manager_path(self._config)
        return CalibrationOptions(
            routine=routine,
            serial_number=self._serial.text().strip() or None,
            manager=manager if routine == ETM_ROUTINE else None,
            screen=self._screen.value(),
            point_duration_seconds=self._point_duration.value(),
            advance_on_space=self._advance_on_space.isChecked(),
            fullscreen=self._fullscreen.isChecked(),
            window_size=self._window_size.text().strip() or "1024x768",
            play_sound=self._sound.isChecked(),
            debug_render=self._debug_render.isChecked(),
        )

    def report_exit(self, _exit_code: int) -> None:
        self._calibrate_button.setEnabled(True)
        self.refresh()

    def _request_calibration(self) -> None:
        if self._session is None:
            return
        self._calibrate_button.setEnabled(False)
        self.calibrate_requested.emit(
            build_calibrate_args(self._session, self.calibration_options())
        )

    def _on_routine_changed(self) -> None:
        is_etm = self.selected_routine() == ETM_ROUTINE
        self._child_options.setVisible(not is_etm)
        path, exists = resolve_manager_path(self._config)
        self._manager_label.setText(f"Manager executable: {path}")
        self._manager_label.setVisible(is_etm)
        self._manager_warning.setText(
            ""
            if exists
            else f"No executable at {path}. Set eye_tracker_manager "
            "in the config or install Tobii Pro Eye Tracker Manager."
        )
        self._manager_warning.setVisible(is_etm and not exists)

    def refresh(self) -> None:
        self._calibrate_button.setEnabled(self._session is not None)
        if self._session is None:
            self._history.setText(NO_HISTORY_TEXT)
            return
        records = artifacts.find_calibrations(
            self._session.sourcedata_root,
            self._session.subject,
            self._session.session,
        )
        self._history.setText(
            "\n".join(describe_calibration(record) for record in records)
            or NO_HISTORY_TEXT
        )
