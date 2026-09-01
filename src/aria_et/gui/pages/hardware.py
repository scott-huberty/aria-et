"""Hardware page: tracker discovery and direct-address connection."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aria_et.gui.state import ExitSeverity, build_check_args, describe_exit_code
from aria_et.gui.widgets.status_pill import PillTone, StatusPill

DEFAULT_TRACKER_ADDRESS = "tobii-prp://169.254.10.180"

TROUBLESHOOTING_TEXT = (
    "Confirm the tracker is powered on, confirm the Ethernet link is up, and "
    "allow a minute for the link-local address to be assigned. Then tick "
    "“Connect directly to this address” and retry."
)

_TRACKER_LINE = re.compile(
    r"^\s*\d+\.\s*(?P<name>.+?)\s+model=(?P<model>.+?)"
    r"\s+serial=(?P<serial>\S+)\s+address=(?P<address>\S+)\s*$"
)


def parse_tracker_lines(lines: list[str]) -> list[dict[str, str]]:
    """Extract discovered trackers from ``check-eyetracker`` output."""
    trackers = []
    for line in lines:
        match = _TRACKER_LINE.match(line)
        if match is not None:
            trackers.append(match.groupdict())
    return trackers


class HardwarePage(QWidget):
    check_requested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._output_lines: list[str] = []
        self._connected = False

        heading = QLabel("Hardware")
        heading.setObjectName("PageHeading")

        self._pill = StatusPill("Unknown", PillTone.NEUTRAL)
        self._check_button = QPushButton("Check tracker")
        self._check_button.setObjectName("Primary")
        self._check_button.clicked.connect(self._request_check)

        status_row = QHBoxLayout()
        status_row.addWidget(self._pill)
        status_row.addStretch(1)
        status_row.addWidget(self._check_button)

        self._address_field = QLineEdit(DEFAULT_TRACKER_ADDRESS)
        self._use_address = QCheckBox(
            "Connect directly to this address (skip discovery)"
        )

        self._message = QLabel()
        self._message.setObjectName("HelperText")
        self._message.setWordWrap(True)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Name", "Model", "Serial", "Address"])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setVisible(False)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 16)
        card_layout.setSpacing(10)
        address_heading = QLabel("Tracker address")
        address_heading.setObjectName("SubsectionHeading")

        card_layout.addLayout(status_row)
        card_layout.addWidget(address_heading)
        card_layout.addWidget(self._address_field)
        card_layout.addWidget(self._use_address)
        card_layout.addWidget(self._message)
        card_layout.addWidget(self._table)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        layout.addWidget(heading)
        layout.addWidget(card)
        layout.addStretch(1)

    @property
    def tracker_connected(self) -> bool:
        return self._connected

    def tracker_address(self) -> str | None:
        if self._use_address.isChecked():
            return self._address_field.text().strip() or None
        return None

    def _request_check(self) -> None:
        self._output_lines = []
        self._connected = False
        self._table.setVisible(False)
        self._message.setText("")
        self._pill.set_status("Checking", PillTone.BUSY)
        self._check_button.setEnabled(False)
        self.check_requested.emit(build_check_args(self.tracker_address()))

    def record_output_line(self, line: str) -> None:
        self._output_lines.append(line)

    def report_exit(self, exit_code: int) -> None:
        self._check_button.setEnabled(True)
        outcome = describe_exit_code(exit_code)

        if outcome.severity is ExitSeverity.SUCCESS:
            trackers = parse_tracker_lines(self._output_lines)
            self._populate_table(trackers)
            self._connected = bool(trackers)
            if trackers:
                self._pill.set_status("Connected", PillTone.GOOD)
                self._message.setText("")
            else:
                self._pill.set_status("Not found", PillTone.WARNING)
                self._message.setText(TROUBLESHOOTING_TEXT)
            return

        if exit_code == 2:
            self._pill.set_status("SDK missing", PillTone.BAD)
        elif exit_code == 3:
            self._pill.set_status("Not found", PillTone.WARNING)
        else:
            self._pill.set_status("Check failed", PillTone.BAD)

        message = outcome.message
        if exit_code == 3:
            message = f"{message}\n\n{TROUBLESHOOTING_TEXT}"
        self._message.setText(message)

    def report_failed_to_start(self, message: str) -> None:
        self._check_button.setEnabled(True)
        self._connected = False
        self._pill.set_status("Check failed", PillTone.BAD)
        self._message.setText(message)

    def _populate_table(self, trackers: list[dict[str, str]]) -> None:
        self._table.setRowCount(len(trackers))
        for row, tracker in enumerate(trackers):
            for column, key in enumerate(("name", "model", "serial", "address")):
                item = QTableWidgetItem(tracker[key])
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(row, column, item)
        self._table.setVisible(bool(trackers))
