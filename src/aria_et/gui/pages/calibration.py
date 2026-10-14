"""Calibration page: child-friendly calibration, its quality, and history.

The GUI always runs the child-friendly (DeToX) calibration with validation.
Eye Tracker Manager calibration stays available from the CLI
(``aria-et calibrate-eyetracker --routine etm``), which records it.
"""

from __future__ import annotations

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

from aria_et.calibration_quality import QUALITY_COLUMNS, format_quality
from aria_et.config import AriaEtConfig
from aria_et.gui import artifacts
from aria_et.gui.state import CalibrationOptions, SessionState, build_calibrate_args
from aria_et.gui.widgets.inputs import WheelSafeSpinBox

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


NO_QUALITY_TEXT = "No calibration yet for this session."
NO_VALIDATION_TEXT = (
    "No validation for the latest calibration (ETM, or a calibration made "
    "before validation was added)."
)
VALIDATION_SKIPPED_TEXT = "Validation was skipped for the latest calibration."

# The same table, with the same formatting, is shown on the stimulus screen
# after validation (aria_et.calibration_quality).
QUALITY_ROWS = QUALITY_COLUMNS


# Display names for calibration methods in the history; calibration.json keeps
# the full method name for provenance and BIDS.
METHOD_LABELS = {"child-friendly-detox": "child friendly"}


def describe_calibration(record: artifacts.CalibrationRecord) -> str:
    method = METHOD_LABELS.get(record.method, record.method) or "unknown method"
    text = f"{record.created_at or record.calibration_id}  —  {method}"
    summary = (record.validation or {}).get("summary")
    if summary:
        left, right = format_quality(summary, "accuracy_deg")
        text += f"  —  accuracy L {left}° R {right}°"
    return text


def quality_rows(validation: dict | None) -> list[tuple[str, str, str]]:
    """Rows of (label, left eye, right eye) for the quality table."""
    summary = (validation or {}).get("summary")
    return [(label, *format_quality(summary, key)) for label, key, _, _ in QUALITY_ROWS]


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


def _card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(10)
    if title is not None:
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

        # No heading: the page title already says Calibration.
        settings_card, settings_layout = _card()
        # Production calibrations want the defaults, so the fields start locked
        # and must be unlocked deliberately, as on the Battery page.
        self._settings_fields = QWidget()
        self._settings_fields.setObjectName("CardFields")
        form = QFormLayout(self._settings_fields)
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(6)
        self._screen = WheelSafeSpinBox()
        self._screen.setRange(0, 8)
        self._fullscreen = QCheckBox("Fullscreen")
        self._window_size = QLineEdit()
        self._sound = QCheckBox("Play sound")
        form.addRow("Screen", self._screen)
        form.addRow("Display", self._fullscreen)
        form.addRow("Window size", self._window_size)
        form.addRow("Sound", self._sound)
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

        # Calibrates the tracker connected on the Hardware page (the saved
        # tracker); the CLI resolves it, so no tracker field is needed here.
        self._calibrate_button = QPushButton("Run calibration")
        self._calibrate_button.setObjectName("Primary")
        self._calibrate_button.clicked.connect(self._request_calibration)
        settings_layout.addWidget(self._calibrate_button)

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
        layout.addWidget(settings_card)
        layout.addWidget(quality_card)
        layout.addWidget(history_card)
        layout.addStretch(1)

        self._restore_defaults()
        self.refresh()

    def set_session(self, session: SessionState | None) -> None:
        self._session = session
        self.refresh()

    def calibration_options(self) -> CalibrationOptions:
        return CalibrationOptions(
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
        """Production settings: the PsychoPy window on the stimulus display."""
        return CalibrationOptions(screen=self._config.psychopy_screen)

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
        customised = self.calibration_options() != self.default_calibration_options()
        self._custom_notice.setVisible(customised)
        self._restore_defaults_button.setEnabled(customised)

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
