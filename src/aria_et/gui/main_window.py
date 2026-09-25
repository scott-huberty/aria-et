"""Main window: navigation, session header, shared console, and CLI dispatch."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
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
from aria_et.gui.progress import PageProgress, page_progress
from aria_et.gui.state import RunMode, SessionState, build_init_config_args
from aria_et.gui.theme import PALETTE
from aria_et.gui.widgets.crash_panel import CRASH_LOG_LINES
from aria_et.gui.widgets.log_pane import LogPane
from aria_et.gui.widgets.status_pill import PillTone, StatusPill

NAV_ITEMS = ("1  Setup", "2  Hardware", "3  Calibration", "4  Battery", "5  Export")
NAV_ICON_SIZE = 16

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
        pages = (
            self._setup_page,
            self._hardware_page,
            self._calibration_page,
            self._battery_page,
            self._export_page,
        )
        # A Next shortcut under every page but the last, and Close session on
        # the last. They never gate: the sidebar still reaches any page the
        # session allows. Both are pinned below the scroll area so they stay
        # visible on long pages.
        self._next_buttons: list[QPushButton] = []
        for row, page in enumerate(pages):
            if row + 1 < len(pages):
                button = QPushButton(f"Next: {_nav_name(NAV_ITEMS[row + 1])}  →")
                button.clicked.connect(lambda _checked, r=row: self._go_to(r + 1))
                self._next_buttons.append(button)
            else:
                button = QPushButton("Close session")
                button.clicked.connect(self._close_session_from_export)
                self._close_session_button = button
            button.setObjectName("Next")
            self._pages.addWidget(_with_footer(_scrollable(page), button))

        self._nav = QListWidget()
        self._nav.setObjectName("NavList")
        self._nav.addItems(NAV_ITEMS)
        self._nav.setFixedWidth(190)
        self._nav.setIconSize(QSize(NAV_ICON_SIZE, NAV_ICON_SIZE))
        self._done_icon = _progress_icon(done=True)
        self._pending_icon = _progress_icon(done=False)
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
        self._refresh_nav_progress()

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
        self._refresh_nav_progress()

    def _on_session_closed(self) -> None:
        self._session = None
        self._session_label.setText("No session open")
        self._mode_banner.setVisible(False)
        self._battery_page.set_session(None)
        self._calibration_page.set_session(None)
        self._export_page.set_session(None)
        self._apply_session_gating()
        self._refresh_nav_progress()

    def _apply_session_gating(self) -> None:
        open_session = self._session is not None
        for row in range(2, self._nav.count()):
            item = self._nav.item(row)
            if open_session:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)

    def _refresh_nav_progress(self) -> None:
        """Mark each sidebar page done or not, from real state; never gates."""
        progress = page_progress(
            self._session,
            tracker_connected=self._hardware_page.tracker_connected,
            export_succeeded=self._export_page.export_succeeded,
        )
        for row, (label, page) in enumerate(zip(NAV_ITEMS, progress, strict=True)):
            self._apply_nav_progress(self._nav.item(row), label, page)
        for row, button in enumerate(self._next_buttons):
            # Clickable exactly when the page's check mark shows, and only
            # toward a page the sidebar already allows.
            next_item = self._nav.item(row + 1)
            button.setEnabled(
                progress[row].done
                and bool(next_item.flags() & Qt.ItemFlag.ItemIsEnabled)
            )

        # Closing ends the participant's session, so never mid-command.
        self._close_session_button.setEnabled(
            progress[-1].done and not self._process.is_running()
        )

    def _go_to(self, row: int) -> None:
        self._nav.setCurrentRow(row)

    def _close_session_from_export(self) -> None:
        if self._process.is_running():
            return
        self._setup_page.close_session()
        self._go_to(0)

    def _apply_nav_progress(self, item, label: str, page: PageProgress) -> None:
        item.setIcon(self._done_icon if page.done else self._pending_icon)
        item.setText(f"{label}   {page.detail}" if page.detail else label)
        item.setToolTip("Complete" if page.done else "Not complete yet")

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
        self._refresh_nav_progress()
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
        self._refresh_nav_progress()

    def _on_failed_to_start(self, message: str) -> None:
        self._log_pane.expand()
        self._log_pane.append_line(message)
        if self._output_consumer is not None:
            self._output_consumer.report_failed_to_start(message)
            self._output_consumer = None
            self._on_exit = None
        else:
            handler, self._on_exit = self._on_exit, None
            if handler is not None:
                handler(1)
        self._refresh_nav_progress()

    def _sync_tracker_pill(self) -> None:
        if self._hardware_page.tracker_connected:
            self._tracker_pill.set_status("Tracker connected", PillTone.GOOD)
        else:
            self._tracker_pill.set_status("Tracker not found", PillTone.WARNING)


def _nav_name(label: str) -> str:
    """'2  Hardware' -> 'Hardware'."""
    return label.split(maxsplit=1)[1]


def _with_footer(view: QWidget, button: QPushButton) -> QWidget:
    footer = QHBoxLayout()
    footer.setContentsMargins(20, 8, 20, 12)
    footer.addStretch(1)
    footer.addWidget(button)
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(view, 1)
    layout.addLayout(footer)
    return container


def _scrollable(page: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setWidget(page)
    return area


def _progress_icon(*, done: bool) -> QIcon:
    """A filled green check disc when done, a grey ring otherwise."""
    scale = 2  # draw at 2x so the icon stays crisp on high-DPI displays
    size = NAV_ICON_SIZE * scale
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    circle = QRectF(1.5 * scale, 1.5 * scale, size - 3 * scale, size - 3 * scale)
    if done:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(PALETTE["aria_teal"]))
        painter.drawEllipse(circle)
        tick = QPainterPath(QPointF(size * 0.28, size * 0.52))
        tick.lineTo(QPointF(size * 0.44, size * 0.67))
        tick.lineTo(QPointF(size * 0.73, size * 0.36))
        pen = QPen(QColor(PALETTE["surface"]), 2.2 * scale)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(tick)
    else:
        painter.setPen(QPen(QColor(PALETTE["border"]), 1.5 * scale))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(circle)
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return QIcon(pixmap)
