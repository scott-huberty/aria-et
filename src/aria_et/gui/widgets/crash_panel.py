"""Panel shown when a run ends badly, so the operator can capture context."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from aria_et.gui.state import describe_exit_code

CRASH_LOG_LINES = 20

SESSION_LOG_NAME = "session.log"

NO_END_EVENT_MESSAGE = (
    "The task ended without a completion event, so the run is incomplete."
)


def describe_crash(display_name: str, run_label: str | None, exit_code: int) -> str:
    where = display_name if run_label is None else f"{display_name} — run-{run_label}"
    if exit_code == 0:
        return f"{where} — exit code 0. {NO_END_EVENT_MESSAGE}"
    return f"{where} — exit code {exit_code}. {describe_exit_code(exit_code).message}"


class CrashPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._run_dir: Path | None = None

        heading = QLabel("Last run needs attention")
        heading.setObjectName("SectionHeading")

        self._detail = QLabel()
        self._detail.setObjectName("ModeBanner")
        self._detail.setWordWrap(True)

        self._log = QPlainTextEdit()
        self._log.setObjectName("LogPane")
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(CRASH_LOG_LINES)
        self._log.setFixedHeight(160)

        self._open_folder = QPushButton("Open run folder")
        self._open_folder.clicked.connect(self._on_open_folder)
        self._open_log = QPushButton("Open session.log")
        self._open_log.clicked.connect(self._on_open_log)
        buttons = QHBoxLayout()
        buttons.addWidget(self._open_folder)
        buttons.addWidget(self._open_log)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(heading)
        layout.addWidget(self._detail)
        layout.addWidget(self._log)
        layout.addLayout(buttons)

        self.setVisible(False)

    def show_crash(
        self,
        display_name: str,
        *,
        run_label: str | None,
        exit_code: int,
        log_lines: list[str],
        run_dir: Path | None,
    ) -> None:
        self._run_dir = run_dir
        self._detail.setText(describe_crash(display_name, run_label, exit_code))
        self._log.setPlainText("\n".join(log_lines[-CRASH_LOG_LINES:]))
        self._open_folder.setEnabled(run_dir is not None)
        self._open_log.setEnabled(
            run_dir is not None and (run_dir / SESSION_LOG_NAME).is_file()
        )
        self.setVisible(True)

    def clear(self) -> None:
        self._run_dir = None
        self.setVisible(False)

    def _on_open_folder(self) -> None:
        if self._run_dir is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._run_dir)))

    def _on_open_log(self) -> None:
        if self._run_dir is not None:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self._run_dir / SESSION_LOG_NAME))
            )
