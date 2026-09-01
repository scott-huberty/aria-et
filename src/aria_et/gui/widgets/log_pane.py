"""Collapsible console pane showing merged CLI output."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

MAX_LOG_LINES = 5000


class LogPane(QWidget):
    """Bounded log view. The complete record always lives in ``session.log``."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._toggle = QToolButton()
        self._toggle.setText("▸  Console")
        self._toggle.setCheckable(True)
        self._toggle.setStyleSheet("border: none; font-weight: 600;")
        self._toggle.toggled.connect(self._on_toggled)

        self._clear = QPushButton("Clear")
        self._clear.setVisible(False)
        self._clear.clicked.connect(self.clear)

        self._output = QPlainTextEdit()
        self._output.setObjectName("LogPane")
        self._output.setReadOnly(True)
        self._output.setMaximumBlockCount(MAX_LOG_LINES)
        self._output.setVisible(False)
        self._output.setMinimumHeight(180)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self._toggle)
        header.addStretch(1)
        header.addWidget(self._clear)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 12)
        layout.addLayout(header)
        layout.addWidget(self._output)

    def append_line(self, line: str) -> None:
        self._output.appendPlainText(line)
        scrollbar = self._output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        self._output.clear()

    def tail(self, line_count: int = 20) -> list[str]:
        lines = self._output.toPlainText().splitlines()
        return lines[-line_count:]

    def expand(self) -> None:
        self._toggle.setChecked(True)

    def _on_toggled(self, expanded: bool) -> None:
        self._toggle.setText("▾  Console" if expanded else "▸  Console")
        self._output.setVisible(expanded)
        self._clear.setVisible(expanded)
