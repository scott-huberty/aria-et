"""Main window: navigation, session header, shared console, and CLI dispatch."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from aria_et.config import AriaEtConfig
from aria_et.gui.pages.battery import BatteryPage
from aria_et.gui.pages.calibration import CalibrationPage
from aria_et.gui.pages.export import ExportPage
from aria_et.gui.pages.hardware import HardwarePage
from aria_et.gui.pages.setup import SetupPage
from aria_et.gui.process import CliProcess
from aria_et.gui.state import RunMode, SessionState, build_init_config_args
from aria_et.gui.widgets.crash_panel import CRASH_LOG_LINES
from aria_et.gui.widgets.log_pane import LogPane
from aria_et.gui.widgets.status_pill import PillTone, StatusPill

NAV_ITEMS = ("1  Setup", "2  Hardware", "3  Calibration", "4  Battery", "5  Export")

MODE_BANNERS = {
    RunMode.DRY_RUN: "DRY RUN — NO GAZE DATA IS BEING RECORDED",
}


class MainWindow(QMainWindow):
    def __init__(self, config: AriaEtConfig, screen_count: int = 1):
        super().__init__()
        self._config = config
        self._session: SessionState | None = None

        self.setWindowTitle("ARIA-ET")
        self.setMinimumSize(1000, 680)

        self._process = CliProcess(self)
        self._process.output_line.connect(self._on_output_line)
        self._process.finished.connect(self._on_process_finished)
        self._process.failed_to_start.connect(self._on_failed_to_start)
        self._process.escalated.connect(self._log_message)
        self._output_consumer: HardwarePage | ExportPage | None = None
        self._on_exit: Callable[[int], None] | None = None
        self._recent_lines: deque[str] = deque(maxlen=CRASH_LOG_LINES)

        self._setup_page = SetupPage(config, screen_count)
        self._setup_page.session_opened.connect(self._on_session_opened)
        self._setup_page.session_closed.connect(self._on_session_closed)
        self._setup_page.create_config_requested.connect(self._create_config)

        self._hardware_page = HardwarePage()
        self._hardware_page.check_requested.connect(self._run_tracker_check)

        self._battery_page = BatteryPage(config)
        self._battery_page.run_requested.connect(self._run_task)
        self._battery_page.stop_requested.connect(self._stop_task)

        self._calibration_page = CalibrationPage(config)
        self._calibration_page.calibrate_requested.connect(self._run_calibration)

        self._export_page = ExportPage(config)
        self._export_page.export_requested.connect(self._run_export)

        self._pages = QStackedWidget()
        self._pages.addWidget(_scrollable(self._setup_page))
        self._pages.addWidget(_scrollable(self._hardware_page))
        self._pages.addWidget(_scrollable(self._calibration_page))
        self._pages.addWidget(_scrollable(self._battery_page))
        self._pages.addWidget(_scrollable(self._export_page))

        self._nav = QListWidget()
        self._nav.setObjectName("NavList")
        self._nav.addItems(NAV_ITEMS)
        self._nav.setFixedWidth(170)
        self._nav.currentRowChanged.connect(self._pages.setCurrentIndex)
        self._nav.setCurrentRow(0)

        self._log_pane = LogPane()

        content = QSplitter(Qt.Orientation.Vertical)
        content.addWidget(self._pages)
        content.addWidget(self._log_pane)
        content.setStretchFactor(0, 1)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._nav)
        body_layout.addWidget(content, 1)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self._mode_banner = self._build_mode_banner()
        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._mode_banner)
        root_layout.addWidget(body, 1)
        self.setCentralWidget(root)

        self._apply_session_gating()

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background-color: #FFFFFF;")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 10, 16, 10)

        title = QLabel("ARIA-ET")
        title.setObjectName("PageHeading")
        self._session_label = QLabel("No session open")
        self._session_label.setObjectName("SubsectionHeading")
        self._tracker_pill = StatusPill("Tracker unknown", PillTone.NEUTRAL)

        layout.addWidget(title)
        layout.addSpacing(24)
        layout.addWidget(self._session_label)
        layout.addStretch(1)
        layout.addWidget(self._tracker_pill)
        return header

    def _build_mode_banner(self) -> QLabel:
        banner = QLabel()
        banner.setObjectName("ModeBanner")
        banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        banner.setVisible(False)
        return banner

    # -- session ----------------------------------------------------------

    def _on_session_opened(self, session: SessionState) -> None:
        self._session = session
        self._session_label.setText(
            f"sub-{session.subject} / ses-{session.session}  —  "
            f"{session.sourcedata_root}"
        )
        banner = MODE_BANNERS.get(session.mode)
        self._mode_banner.setText(banner or "")
        self._mode_banner.setVisible(banner is not None)
        self._battery_page.set_session(session)
        self._calibration_page.set_session(session)
        self._export_page.set_session(session)
        self._apply_session_gating()

    def _on_session_closed(self) -> None:
        self._session = None
        self._session_label.setText("No session open")
        self._mode_banner.setVisible(False)
        self._battery_page.set_session(None)
        self._calibration_page.set_session(None)
        self._export_page.set_session(None)
        self._apply_session_gating()

    def _apply_session_gating(self) -> None:
        open_session = self._session is not None
        for row in range(2, self._nav.count()):
            item = self._nav.item(row)
            if open_session:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)

    # -- CLI dispatch -----------------------------------------------------

    def _run_tracker_check(self, args: list[str]) -> None:
        self._output_consumer = self._hardware_page
        self._start(args, on_exit=self._finish_tracker_check)

    def _run_task(self, args: list[str]) -> None:
        self._log_pane.expand()
        if not self._start(args, on_exit=self._finish_task):
            self._battery_page.report_exit(1)

    def _finish_task(self, exit_code: int) -> None:
        self._battery_page.report_exit(exit_code, list(self._recent_lines))

    def _run_calibration(self, args: list[str]) -> None:
        self._log_pane.expand()
        if not self._start(args, on_exit=self._calibration_page.report_exit):
            self._calibration_page.report_exit(1)

    def _run_export(self, args: list[str]) -> None:
        self._log_pane.expand()
        self._output_consumer = self._export_page
        if not self._start(args, on_exit=self._export_page.report_exit):
            self._export_page.report_exit(1)

    def _stop_task(self) -> None:
        self._log_message("Stopping — saving data…")
        self._process.request_stop()

    def _log_message(self, message: str) -> None:
        self._log_pane.append_line(message)

    def _create_config(self) -> None:
        self._start(
            build_init_config_args(),
            on_exit=lambda _code: self._setup_page.refresh_config_banner(),
        )

    def _start(self, args: list[str], *, on_exit: Callable[[int], None]) -> bool:
        if self._process.is_running():
            self._log_pane.append_line("A command is already running; ignoring.")
            return False
        self._on_exit = on_exit
        self._recent_lines.clear()
        self._log_pane.append_line(f"$ aria-et {' '.join(args)}")
        self._process.start(args)
        return True

    def _finish_tracker_check(self, exit_code: int) -> None:
        self._hardware_page.report_exit(exit_code)
        self._sync_tracker_pill()
        self._battery_page.set_tracker_checked(self._hardware_page.tracker_connected)

    def _on_output_line(self, line: str) -> None:
        self._log_pane.append_line(line)
        self._recent_lines.append(line)
        if self._output_consumer is not None:
            self._output_consumer.record_output_line(line)

    def _on_process_finished(self, exit_code: int) -> None:
        handler, self._on_exit = self._on_exit, None
        self._output_consumer = None
        if handler is not None:
            handler(exit_code)

    def _on_failed_to_start(self, message: str) -> None:
        self._log_pane.expand()
        self._log_pane.append_line(message)
        if self._output_consumer is not None:
            self._output_consumer.report_failed_to_start(message)
            self._output_consumer = None
            self._on_exit = None
            return
        handler, self._on_exit = self._on_exit, None
        if handler is not None:
            handler(1)

    def _sync_tracker_pill(self) -> None:
        if self._hardware_page.tracker_connected:
            self._tracker_pill.set_status("Tracker connected", PillTone.GOOD)
        else:
            self._tracker_pill.set_status("Tracker not found", PillTone.WARNING)


def _scrollable(page: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setWidget(page)
    return area
