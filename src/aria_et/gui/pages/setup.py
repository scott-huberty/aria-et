"""Session setup: subject/session entry, config summary, and the session gate."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRegularExpression, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from aria_et.config import AriaEtConfig, default_config_path
from aria_et.gui import artifacts, validation
from aria_et.gui.state import (
    DEFAULT_SESSION_LABEL,
    RunMode,
    SessionState,
    dry_run_allowed,
    sourcedata_root,
)

LABEL_HELPER_TEXT = "Letters and numbers only — no hyphens or spaces."

MODE_LABELS = {
    RunMode.ACQUISITION: "Acquisition",
    RunMode.DRY_RUN: "Dry run (no tracker — writes empty run)",
}

DRY_RUN_CONFIRMATION = (
    "Dry run records no gaze data. Runs are written to the dry-run data root "
    "and are not valid session data. Continue?"
)


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


class SetupPage(QWidget):
    session_opened = Signal(object)
    session_closed = Signal()
    create_config_requested = Signal()

    def __init__(self, config: AriaEtConfig, screen_count: int = 1, parent=None):
        super().__init__(parent)
        self._config = config
        self._screen_count = screen_count
        self._session: SessionState | None = None

        heading = QLabel("Session setup")
        heading.setObjectName("PageHeading")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        layout.addWidget(heading)
        layout.addWidget(self._build_config_banner())
        layout.addWidget(self._build_session_card())
        layout.addWidget(self._build_display_card())
        layout.addStretch(1)

        self._refresh_open_button()

    # -- construction -----------------------------------------------------

    def _build_config_banner(self) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)

        self._config_banner = QLabel()
        self._config_banner.setObjectName("ModeBanner")
        self._config_banner.setWordWrap(True)
        self._create_config_button = QPushButton("Create config")
        self._create_config_button.clicked.connect(self.create_config_requested)

        row.addWidget(self._config_banner, 1)
        row.addWidget(self._create_config_button)

        config_present = default_config_path().is_file()
        container.setVisible(not config_present)
        self._config_banner.setText(
            "No config found; using built-in EIZO defaults. "
            f"Create config writes {default_config_path()}."
        )
        self._config_banner_container = container
        return container

    def _build_session_card(self) -> QWidget:
        card, layout = _card("Participant session")

        self._subject_field = QLineEdit()
        self._subject_field.setPlaceholderText("abby")
        self._session_field = QLineEdit(DEFAULT_SESSION_LABEL)
        for field in (self._subject_field, self._session_field):
            field.setValidator(
                QRegularExpressionValidator(QRegularExpression(r"[A-Za-z0-9]*"))
            )
            field.textChanged.connect(self._on_label_changed)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Subject", self._subject_field)
        form.addRow("", _helper(LABEL_HELPER_TEXT))
        form.addRow("Session", self._session_field)
        form.addRow("", _helper("Defaults to 01 — the first visit."))

        self._mode_selector = QComboBox()
        for mode in (RunMode.ACQUISITION, RunMode.DRY_RUN):
            if mode is RunMode.DRY_RUN and not dry_run_allowed():
                continue
            self._mode_selector.addItem(MODE_LABELS[mode], mode)
        self._mode_selector.currentIndexChanged.connect(self._on_mode_changed)
        if self._mode_selector.count() > 1:
            form.addRow("Mode", self._mode_selector)

        self._error_label = QLabel()
        self._error_label.setObjectName("ErrorText")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)

        # The validator blocks invalid keystrokes, but a paste is dropped
        # wholesale rather than corrected, so offer the correction explicitly.
        self._fix_button = QPushButton("Fix labels")
        self._fix_button.setVisible(False)
        self._fix_button.clicked.connect(self._fix_labels)

        self._open_button = QPushButton("Open session")
        self._open_button.setObjectName("Primary")
        self._open_button.clicked.connect(self._open_session)
        self._close_button = QPushButton("Close session")
        self._close_button.setVisible(False)
        self._close_button.clicked.connect(self._close_session)

        self._session_path_label = _helper("")
        self._session_path_label.setVisible(False)
        self._session_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        buttons = QHBoxLayout()
        buttons.addWidget(self._open_button)
        buttons.addWidget(self._close_button)
        buttons.addWidget(self._fix_button)
        buttons.addStretch(1)

        layout.addLayout(form)
        layout.addWidget(self._error_label)
        layout.addWidget(self._session_path_label)
        layout.addLayout(buttons)
        return card

    def _build_display_card(self) -> QWidget:
        card, layout = _card("Lab configuration")
        config = self._config

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(6)
        rows = [
            ("Data root", str(config.data_root)),
            ("Monitor", config.monitor_name),
            ("Resolution", config.screen_resolution),
            ("Physical size (m)", config.screen_size_meters),
            ("Viewing distance (m)", f"{config.screen_distance_meters}"),
            ("Stimulus screen", str(config.psychopy_screen)),
            ("Eye Tracker Manager screen", str(config.etm_screen)),
        ]
        for row, (name, value) in enumerate(rows):
            grid.addWidget(QLabel(name), row, 0)
            value_label = QLabel(value)
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            grid.addWidget(value_label, row, 1)
        grid.setColumnStretch(1, 1)

        reveal = QPushButton("Reveal data root in Finder")
        reveal.clicked.connect(self._reveal_data_root)

        layout.addLayout(grid)
        layout.addWidget(self._build_display_warning())
        layout.addWidget(reveal, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    def _build_display_warning(self) -> QWidget:
        required = max(self._config.psychopy_screen, self._config.etm_screen) + 1
        warning = QLabel(
            f"Only {self._screen_count} display(s) detected, but the config "
            f"expects at least {required} (stimulus screen "
            f"{self._config.psychopy_screen}, ETM screen {self._config.etm_screen}). "
            "This is fine for development but not for acquisition."
        )
        warning.setObjectName("ModeBanner")
        warning.setWordWrap(True)
        warning.setVisible(self._screen_count < required)
        return warning

    # -- behaviour --------------------------------------------------------

    @property
    def session(self) -> SessionState | None:
        return self._session

    def selected_mode(self) -> RunMode:
        return self._mode_selector.currentData()

    def _on_label_changed(self) -> None:
        self._set_error("")
        self._refresh_open_button()

    def _refresh_open_button(self) -> None:
        subject = validation.normalize_subject(self._subject_field.text())
        session = validation.normalize_session(self._session_field.text())
        valid = validation.is_valid_label(subject) and validation.is_valid_label(
            session
        )
        self._open_button.setEnabled(valid)
        correctable = any(
            value
            and not validation.is_valid_label(value)
            and validation.suggest_label(value)
            for value in (subject, session)
        )
        self._fix_button.setVisible(correctable)

    def _set_error(self, text: str) -> None:
        self._error_label.setText(text)
        self._error_label.setVisible(bool(text))

    def _fix_labels(self) -> None:
        for field, normalize in (
            (self._subject_field, validation.normalize_subject),
            (self._session_field, validation.normalize_session),
        ):
            field.setText(validation.suggest_label(normalize(field.text())))

    def _on_mode_changed(self) -> None:
        if self.selected_mode() is not RunMode.DRY_RUN:
            return
        confirmed = QMessageBox.question(
            self,
            "Enable dry run?",
            DRY_RUN_CONFIRMATION,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed is not QMessageBox.StandardButton.Yes:
            self._mode_selector.setCurrentIndex(0)

    def _normalized_labels(self) -> tuple[str, str]:
        subject = validation.normalize_subject(self._subject_field.text())
        session = validation.normalize_session(self._session_field.text())
        self._subject_field.setText(subject)
        self._session_field.setText(session)
        return subject, session

    def _open_session(self) -> None:
        subject, session = self._normalized_labels()
        for value, name in ((subject, "Subject"), (session, "Session")):
            error = validation.label_error(value, name)
            if error:
                self._set_error(error)
                return

        mode = self.selected_mode()
        root = sourcedata_root(self._config.data_root, mode)
        if artifacts.classify_session(root, subject, session) is (
            artifacts.SessionOpenState.HAS_DATA
        ):
            session = self._resolve_collision(root, subject, session)
            if session is None:
                return

        self._session = SessionState(
            subject=subject,
            data_root=self._config.data_root,
            session=session,
            mode=mode,
        )
        self._apply_open_state()
        self.session_opened.emit(self._session)

    def _resolve_collision(self, root: Path, subject: str, session: str) -> str | None:
        runs = artifacts.find_run_directories(root, subject, session)
        suggested = artifacts.next_free_session_label(root, subject)
        listing = "\n".join(
            f"  {run.task_id:<22} run-{run.run_label}  "
            f"{artifacts.summarize_run(run)[0].value}"
            for run in runs
        )

        box = QMessageBox(self)
        box.setWindowTitle("Session already has data")
        box.setText(
            f"Session ses-{session} already has {len(runs)} run(s) for sub-{subject}."
        )
        box.setInformativeText(listing)
        use_next = box.addButton(
            f"Use ses-{suggested} instead", QMessageBox.ButtonRole.AcceptRole
        )
        box.addButton(f"Continue ses-{session}", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(use_next)
        box.exec()

        clicked = box.clickedButton()
        if clicked is cancel:
            return None
        if clicked is use_next:
            self._session_field.setText(suggested)
            return suggested
        return session

    def _apply_open_state(self) -> None:
        assert self._session is not None
        session_dir = artifacts.subject_session_dir(
            self._session.sourcedata_root, self._session.subject, self._session.session
        )
        self._session_path_label.setText(f"Session directory: {session_dir}")
        self._session_path_label.setVisible(True)
        self._set_error("")
        self._open_button.setVisible(False)
        self._close_button.setVisible(True)
        for widget in (self._subject_field, self._session_field, self._mode_selector):
            widget.setEnabled(False)

    def _close_session(self) -> None:
        self._session = None
        self._session_path_label.setVisible(False)
        self._open_button.setVisible(True)
        self._close_button.setVisible(False)
        for widget in (self._subject_field, self._session_field, self._mode_selector):
            widget.setEnabled(True)
        self._refresh_open_button()
        self.session_closed.emit()

    def _reveal_data_root(self) -> None:
        self._config.data_root.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._config.data_root)))

    def refresh_config_banner(self) -> None:
        self._config_banner_container.setVisible(not default_config_path().is_file())
