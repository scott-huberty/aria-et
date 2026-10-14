"""Calibration page: routine selection, ETM path check, and history."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from aria_et.config import AriaEtConfig
from aria_et.eyetracker import default_eyetracker_manager_path
from aria_et.gui import artifacts
from aria_et.gui.state import CalibrationOptions, SessionState, build_calibrate_args
from aria_et.gui.widgets.inputs import (
    WheelSafeComboBox,
    WheelSafeSpinBox,
)

ETM_ROUTINE = "etm"
CHILD_FRIENDLY_ROUTINE = "child-friendly"

CHILD_FRIENDLY_NOTE = (
    "Child-friendly calibration uses DeToX with the study's 5-point protocol. "
    "After the positioning screen (Space to continue), number keys select a "
    "point, Space collects, Enter shows the results, and Escape aborts. On the "
    "results screen, pick points to redo or press Enter to accept."
)

EDIT_SETTINGS_TEXT = "Change settings"
LOCK_SETTINGS_TEXT = "Lock settings"
CUSTOM_SETTINGS_NOTICE = (
    "Custom calibration settings are in use. Restore defaults before "
    "collecting data unless you mean to change them."
)

NO_HISTORY_TEXT = "No calibrations yet for this session."

HISTORY_PREAMBLE = (
    "A run records the most recent calibration under the same subject and "
    "session, newest first:"
)


def resolve_manager_path(config: AriaEtConfig) -> tuple[str, bool]:
    """Return the manager executable the CLI will use and whether it exists."""
    path = config.eye_tracker_manager or default_eyetracker_manager_path()
    return path, Path(path).exists()


NO_QUALITY_TEXT = "No calibration yet for this session."
NO_VALIDATION_TEXT = (
    "No validation for the latest calibration (ETM, or a calibration made "
    "before validation was added)."
)
VALIDATION_SKIPPED_TEXT = "Validation was skipped for the latest calibration."

# (row label, summary key, scale, decimals) for the quality table.
QUALITY_ROWS = (
    ("Accuracy (deg)", "accuracy_deg", 1, 2),
    ("Precision (deg)", "precision_rms_deg", 1, 2),
    ("Data loss (%)", "data_loss", 100, 0),
)
EYES = ("left", "right")


def describe_calibration(record: artifacts.CalibrationRecord) -> str:
    method = record.method or "unknown method"
    text = f"{record.created_at or record.calibration_id}  —  {method}"
    accuracy = _summary_values(record.validation, "accuracy_deg")
    if accuracy is not None:
        left, right = (_format_value(value, 1, 2) for value in accuracy)
        text += f"  —  accuracy L {left}° R {right}°"
    return text


def quality_rows(validation: dict | None) -> list[tuple[str, str, str]]:
    """Rows of (label, left eye, right eye) for the quality table."""
    rows = []
    for label, key, scale, decimals in QUALITY_ROWS:
        values = _summary_values(validation, key) or (None, None)
        rows.append(
            (label, *(_format_value(value, scale, decimals) for value in values))
        )
    return rows


def describe_quality_status(record: artifacts.CalibrationRecord | None) -> str:
    if record is None:
        return NO_QUALITY_TEXT
    validation = record.validation
    if validation is None:
        return NO_VALIDATION_TEXT
    status = validation.get("status")
    if status == "skipped" or not validation.get("summary"):
        return VALIDATION_SKIPPED_TEXT
    points = len(validation.get("points") or ())
    planned = len(validation.get("points_adcs") or ()) or points
    when = record.created_at or record.calibration_id
    if status == "partial":
        return f"Latest calibration ({when}): validation partial, {points} of {planned} targets."
    return f"Latest calibration ({when}): validated at {points} targets."


def _summary_values(validation: dict | None, key: str) -> tuple | None:
    summary = (validation or {}).get("summary")
    if not summary:
        return None
    return tuple((summary.get(eye) or {}).get(key) for eye in EYES)


def _format_value(value: float | None, scale: float, decimals: int) -> str:
    return "n/a" if value is None else f"{value * scale:.{decimals}f}"


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
        self._routine = WheelSafeComboBox()
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

        settings_card, settings_layout = _card("Settings")
        # Production calibrations want the defaults, so the fields start locked
        # and must be unlocked deliberately, as on the Battery page.
        self._settings_fields = QWidget()
        self._settings_fields.setObjectName("CardFields")
        fields_layout = QVBoxLayout(self._settings_fields)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setSpacing(6)

        self._screen = WheelSafeSpinBox()
        self._screen.setRange(0, 8)
        screen_form = QFormLayout()
        screen_form.setVerticalSpacing(6)
        screen_form.addRow("Screen", self._screen)
        fields_layout.addLayout(screen_form)

        self._child_options = QWidget()
        child_layout = QVBoxLayout(self._child_options)
        child_layout.setContentsMargins(0, 0, 0, 0)
        child_layout.setSpacing(6)
        child_form = QFormLayout()
        child_form.setVerticalSpacing(6)
        self._fullscreen = QCheckBox("Fullscreen")
        self._window_size = QLineEdit()
        self._sound = QCheckBox("Play sound")
        child_form.addRow("Display", self._fullscreen)
        child_form.addRow("Window size", self._window_size)
        child_form.addRow("Sound", self._sound)
        child_layout.addLayout(child_form)
        child_layout.addWidget(_helper(CHILD_FRIENDLY_NOTE))
        fields_layout.addWidget(self._child_options)
        settings_layout.addWidget(self._settings_fields)

        self._custom_notice = QLabel(CUSTOM_SETTINGS_NOTICE)
        self._custom_notice.setObjectName("ModeBanner")
        self._custom_notice.setWordWrap(True)
        settings_layout.addWidget(self._custom_notice)

        self._edit_settings_button = QPushButton(EDIT_SETTINGS_TEXT)
        self._edit_settings_button.clicked.connect(self._toggle_settings_lock)
        self._restore_defaults_button = QPushButton("Restore defaults")
        self._restore_defaults_button.clicked.connect(self._restore_defaults)
        settings_buttons = QHBoxLayout()
        settings_buttons.addWidget(self._edit_settings_button)
        settings_buttons.addWidget(self._restore_defaults_button)
        settings_buttons.addStretch(1)
        settings_layout.addLayout(settings_buttons)

        # Fullscreen ignores the window size, so don't let it look editable.
        self._fullscreen.toggled.connect(self._sync_window_size_enabled)
        for changed in (
            self._screen.valueChanged,
            self._fullscreen.toggled,
            self._window_size.textChanged,
            self._sound.toggled,
        ):
            changed.connect(self._sync_settings_state)

        tracker_card, tracker_layout = _card("Tracker")
        self._serial = QLineEdit()
        self._serial.setPlaceholderText(
            "Optional — leave blank to use the saved tracker"
        )
        tracker_form = QFormLayout()
        tracker_form.setVerticalSpacing(6)
        tracker_form.addRow("Serial number", self._serial)
        tracker_layout.addLayout(tracker_form)

        self._calibrate_button = QPushButton("Run calibration")
        self._calibrate_button.setObjectName("Primary")
        self._calibrate_button.clicked.connect(self._request_calibration)
        tracker_layout.addWidget(self._calibrate_button)

        quality_card, quality_layout = _card("Latest calibration quality")
        self._quality_status = _helper("")
        quality_layout.addWidget(self._quality_status)
        self._quality_grid = QWidget()
        grid = QGridLayout(self._quality_grid)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(4)
        for column, column_title in enumerate(("", "Left eye", "Right eye")):
            grid.addWidget(QLabel(column_title), 0, column)
        self._quality_cells: list[tuple[QLabel, QLabel]] = []
        for row, (label, _key, _scale, _decimals) in enumerate(QUALITY_ROWS, 1):
            grid.addWidget(QLabel(label), row, 0)
            cells = (QLabel(), QLabel())
            grid.addWidget(cells[0], row, 1)
            grid.addWidget(cells[1], row, 2)
            self._quality_cells.append(cells)
        grid.setColumnStretch(3, 1)
        quality_layout.addWidget(self._quality_grid)

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
        layout.addWidget(settings_card)
        layout.addWidget(tracker_card)
        layout.addWidget(quality_card)
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
            fullscreen=self._fullscreen.isChecked(),
            window_size=self._window_size.text().strip() or "1024x768",
            play_sound=self._sound.isChecked(),
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

    def default_calibration_options(self) -> CalibrationOptions:
        """Production settings for the selected routine.

        ETM and PsychoPy number displays differently, so each routine has its
        own configured screen: ETM opens on ``etm_screen``, the child-friendly
        PsychoPy window on ``psychopy_screen`` (the EIZO stimulus display).
        """
        routine = self.selected_routine()
        manager, _ = resolve_manager_path(self._config)
        return CalibrationOptions(
            routine=routine,
            manager=manager if routine == ETM_ROUTINE else None,
            screen=(
                self._config.etm_screen
                if routine == ETM_ROUTINE
                else self._config.psychopy_screen
            ),
        )

    def _restore_defaults(self) -> None:
        defaults = self.default_calibration_options()
        self._screen.setValue(defaults.screen)
        self._fullscreen.setChecked(defaults.fullscreen)
        self._window_size.setText(defaults.window_size)
        self._sound.setChecked(defaults.play_sound)
        self._set_settings_locked(True)

    def _toggle_settings_lock(self) -> None:
        self._set_settings_locked(self._settings_fields.isEnabled())

    def _set_settings_locked(self, locked: bool) -> None:
        self._settings_fields.setEnabled(not locked)
        self._edit_settings_button.setText(
            EDIT_SETTINGS_TEXT if locked else LOCK_SETTINGS_TEXT
        )
        self._sync_window_size_enabled()
        self._sync_settings_state()

    def _sync_window_size_enabled(self) -> None:
        self._window_size.setEnabled(not self._fullscreen.isChecked())

    def _sync_settings_state(self) -> None:
        options = self.calibration_options()
        defaults = self.default_calibration_options()
        if self.selected_routine() == ETM_ROUTINE:
            # Only the screen applies to ETM; hidden child options don't count.
            customised = options.screen != defaults.screen
        else:
            customised = replace(options, serial_number=None) != defaults
        self._custom_notice.setVisible(customised)
        self._restore_defaults_button.setEnabled(customised)

    def _on_routine_changed(self) -> None:
        is_etm = self.selected_routine() == ETM_ROUTINE
        self._child_options.setVisible(not is_etm)
        # Each routine has its own screen, so switching resets to its defaults.
        self._restore_defaults()
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
            self._show_quality(None)
            return
        records = artifacts.find_calibrations(
            self._session.sourcedata_root,
            self._session.subject,
            self._session.session,
        )
        self._show_quality(records[0] if records else None)
        self._history.setText(
            "\n".join(describe_calibration(record) for record in records)
            or NO_HISTORY_TEXT
        )

    def _show_quality(self, record: artifacts.CalibrationRecord | None) -> None:
        self._quality_status.setText(describe_quality_status(record))
        validation = record.validation if record is not None else None
        has_summary = bool((validation or {}).get("summary"))
        self._quality_grid.setVisible(has_summary)
        for (left_cell, right_cell), (_label, left, right) in zip(
            self._quality_cells, quality_rows(validation)
        ):
            left_cell.setText(left)
            right_cell.setText(right)
