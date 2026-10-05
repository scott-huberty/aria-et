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

from aria_et.config import AriaEtConfig, load_config
from aria_et.gui.state import (
    ExitSeverity,
    build_check_args,
    build_save_tracker_args,
    describe_exit_code,
)
from aria_et.gui.widgets.status_pill import PillTone, StatusPill

ADDRESS_PLACEHOLDER = "tobii-prp://169.254.x.x"

TROUBLESHOOTING_TEXT = (
    "Confirm the tracker is powered on, confirm the Ethernet link is up, and "
    "allow a minute for the link-local address to be assigned. If you know "
    "the tracker's address, tick “Connect to this address instead” and retry."
)

NO_SAVED_TRACKER_TEXT = (
    "No tracker is saved for this laptop yet. Click “Check tracker” to find "
    "it, then “Save as this laptop's tracker”."
)

_TRACKER_LINE = re.compile(
    r"^\s*\d+\.\s*(?P<name>.+?)\s+model=(?P<model>.+?)"
    r"\s+serial=(?P<serial>\S+)\s+address=(?P<address>\S+)"
    r"(?:\s+firmware=(?P<firmware>\S+))?\s*$"
)

_COLUMNS = (
    ("name", "Name"),
    ("model", "Model"),
    ("serial", "Serial"),
    ("address", "Address"),
    ("firmware", "Firmware"),
)


def parse_tracker_lines(lines: list[str]) -> list[dict[str, str]]:
    """Extract discovered trackers from ``check-eyetracker`` output."""
    trackers = []
    for line in lines:
        match = _TRACKER_LINE.match(line)
        if match is not None:
            tracker = match.groupdict()
            tracker["firmware"] = tracker["firmware"] or "unknown"
            trackers.append(tracker)
    return trackers


def saved_tracker_text(config: AriaEtConfig) -> str:
    if not config.tracker_address and not config.tracker_serial_number:
        return NO_SAVED_TRACKER_TEXT
    return (
        "Saved tracker for this laptop: "
        f"{config.tracker_serial_number or 'unknown serial'} at "
        f"{config.tracker_address or 'unknown address'}."
    )


class HardwarePage(QWidget):
    check_requested = Signal(list)
    save_requested = Signal(list)

    def __init__(self, config: AriaEtConfig | None = None, parent=None):
        super().__init__(parent)
        self._config = config or load_config()
        self._output_lines: list[str] = []
        self._trackers: list[dict[str, str]] = []
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

        self._saved_tracker = QLabel()
        self._saved_tracker.setObjectName("HelperText")
        self._saved_tracker.setWordWrap(True)

        self._address_field = QLineEdit(self._config.tracker_address or "")
        self._address_field.setPlaceholderText(ADDRESS_PLACEHOLDER)
        self._use_address = QCheckBox("Connect to this address instead")

        self._message = QLabel()
        self._message.setObjectName("HelperText")
        self._message.setWordWrap(True)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels([label for _, label in _COLUMNS])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.itemSelectionChanged.connect(self._refresh_save_button)
        self._table.setVisible(False)

        self._save_button = QPushButton("Save as this laptop's tracker")
        self._save_button.clicked.connect(self._request_save)
        self._save_button.setVisible(False)
        self._refresh_saved_tracker()

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 16)
        card_layout.setSpacing(10)
        address_heading = QLabel("Tracker address")
        address_heading.setObjectName("SubsectionHeading")

        card_layout.addLayout(status_row)
        card_layout.addWidget(self._saved_tracker)
        card_layout.addWidget(address_heading)
        card_layout.addWidget(self._address_field)
        card_layout.addWidget(self._use_address)
        card_layout.addWidget(self._message)
        card_layout.addWidget(self._table)
        card_layout.addWidget(self._save_button, 0, Qt.AlignmentFlag.AlignRight)

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

    def _selected_tracker(self) -> dict[str, str] | None:
        """The selected row, or the only discovered tracker."""
        rows = {index.row() for index in self._table.selectedIndexes()}
        if len(rows) == 1:
            return self._trackers[rows.pop()]
        if len(self._trackers) == 1:
            return self._trackers[0]
        return None

    def report_save_exit(self, exit_code: int) -> None:
        self._config = load_config()
        self._refresh_saved_tracker()
        self._refresh_save_button()
        if exit_code == 0:
            self._address_field.setText(self._config.tracker_address or "")
            self._use_address.setChecked(False)
        else:
            self._message.setText("Saving the tracker failed. See the log for details.")

    def _refresh_saved_tracker(self) -> None:
        self._saved_tracker.setText(saved_tracker_text(self._config))

    def _refresh_save_button(self) -> None:
        tracker = self._selected_tracker()
        already_saved = tracker is not None and (
            tracker["serial"] == self._config.tracker_serial_number
            and tracker["address"] == self._config.tracker_address
        )
        self._save_button.setVisible(bool(self._trackers))
        self._save_button.setEnabled(tracker is not None and not already_saved)

    def _request_save(self) -> None:
        tracker = self._selected_tracker()
        if tracker is None:
            self._message.setText("Select the tracker to save.")
            return
        self._save_button.setEnabled(False)
        self.save_requested.emit(build_save_tracker_args(tracker["serial"]))

    def _request_check(self) -> None:
        self._output_lines = []
        self._trackers = []
        self._connected = False
        self._save_button.setVisible(False)
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
        self._trackers = trackers
        self._table.setRowCount(len(trackers))
        for row, tracker in enumerate(trackers):
            for column, (key, _label) in enumerate(_COLUMNS):
                item = QTableWidgetItem(tracker[key])
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(row, column, item)
        self._table.setVisible(bool(trackers))
        self._refresh_save_button()
