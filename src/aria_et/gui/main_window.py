"""Main window: navigation, session header, shared console, and CLI dispatch."""

from __future__ import annotations

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
from aria_et.gui.pages.hardware import HardwarePage
from aria_et.gui.pages.setup import SetupPage
from aria_et.gui.process import CliProcess
from aria_et.gui.state import RunMode, SessionState, build_init_config_args
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
        self._output_consumer: HardwarePage | None = None

        self._setup_page = SetupPage(config, screen_count)
        self._setup_page.session_opened.connect(self._on_session_opened)
        self._setup_page.session_closed.connect(self._on_session_closed)
        self._setup_page.create_config_requested.connect(self._create_config)

        self._hardware_page = HardwarePage()
        self._hardware_page.check_requested.connect(self._run_tracker_check)

        self._pages = QStackedWidget()
        self._pages.addWidget(_scrollable(self._setup_page))
        self._pages.addWidget(_scrollable(self._hardware_page))
        for name in ("Calibration", "Battery", "Export"):
            self._pages.addWidget(_scrollable(_placeholder(name)))

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
        self._apply_session_gating()

    def _on_session_closed(self) -> None:
        self._session = None
        self._session_label.setText("No session open")
        self._mode_banner.setVisible(False)
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
        self._start(args)

    def _create_config(self) -> None:
        self._output_consumer = None
        self._start(build_init_config_args())

    def _start(self, args: list[str]) -> None:
        if self._process.is_running():
            self._log_pane.append_line("A command is already running; ignoring.")
            return
        self._log_pane.append_line(f"$ aria-et {' '.join(args)}")
        self._process.start(args)

    def _on_output_line(self, line: str) -> None:
        self._log_pane.append_line(line)
        if self._output_consumer is not None:
            self._output_consumer.record_output_line(line)

    def _on_process_finished(self, exit_code: int) -> None:
        if self._output_consumer is not None:
            self._output_consumer.report_exit(exit_code)
            self._sync_tracker_pill()
            self._output_consumer = None
        else:
            self._setup_page.refresh_config_banner()

    def _on_failed_to_start(self, message: str) -> None:
        self._log_pane.expand()
        self._log_pane.append_line(message)
        if self._output_consumer is not None:
            self._output_consumer.report_failed_to_start(message)
            self._output_consumer = None

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


def _placeholder(name: str) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(20, 18, 20, 18)
    heading = QLabel(name)
    heading.setObjectName("PageHeading")
    body = QLabel("Not implemented yet.")
    body.setObjectName("HelperText")
    layout.addWidget(heading)
    layout.addWidget(body)
    layout.addStretch(1)
    return page
