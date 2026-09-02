"""Export page: run discovery, selection, and sequential BIDS export."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from aria_et import tasks
from aria_et.config import AriaEtConfig
from aria_et.gui import artifacts
from aria_et.gui.artifacts import RunDirectory, RunStatus
from aria_et.gui.state import SessionState, bids_root, build_export_args

INCOMPLETE_NOTE = "Incomplete runs can be exported but are not analytically complete."

NO_RUNS_TEXT = "No runs found for this subject and session."

NO_GAZE_NOTE = "no gaze"

EXPORT_HEADER_PREFIX = "Exported BIDS eyetracking files to "

SUCCESS_MARKER = "✓"
FAILURE_MARKER = "✕"

_DISPLAY_NAMES = {task.task_id: task.display_name for task in tasks.BATTERY_ORDER}


@dataclass(frozen=True)
class ExportCandidate:
    run: RunDirectory
    status: RunStatus
    no_gaze: bool

    @property
    def checked_by_default(self) -> bool:
        """Only analytically complete runs are pre-selected."""
        return self.status is RunStatus.COMPLETE and not self.no_gaze


def find_export_candidates(
    sourcedata_root: Path, subject: str, session: str
) -> list[ExportCandidate]:
    candidates = []
    for run in artifacts.find_run_directories(sourcedata_root, subject, session):
        status, no_gaze = artifacts.summarize_run(run)
        candidates.append(ExportCandidate(run=run, status=status, no_gaze=no_gaze))
    return candidates


def describe_candidate(candidate: ExportCandidate) -> str:
    name = _DISPLAY_NAMES.get(candidate.run.task_id, candidate.run.task_id)
    notes = [candidate.status.value]
    if candidate.no_gaze:
        notes.append(NO_GAZE_NOTE)
    return f"{name}  —  run-{candidate.run.run_label}  —  {', '.join(notes)}"


def parse_written_files(lines: Iterable[str]) -> list[str]:
    """Collect the paths ``export-bids`` prints after its summary line."""
    written = []
    collecting = False
    for line in lines:
        text = line.strip()
        if text.startswith(EXPORT_HEADER_PREFIX):
            collecting = True
            continue
        if collecting and text:
            written.append(text)
    return written


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


class ExportPage(QWidget):
    export_requested = Signal(list)

    def __init__(self, config: AriaEtConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._session: SessionState | None = None
        self._boxes: list[tuple[QCheckBox, ExportCandidate]] = []
        self._queue: list[ExportCandidate] = []
        self._active: ExportCandidate | None = None
        self._output_lines: list[str] = []
        self._results: list[str] = []

        heading = QLabel("Export")
        heading.setObjectName("PageHeading")

        runs_card, runs_layout = _card("Runs in this session")
        self._runs_container = QWidget()
        self._runs_layout = QVBoxLayout(self._runs_container)
        self._runs_layout.setContentsMargins(0, 0, 0, 0)
        self._runs_layout.setSpacing(4)
        runs_layout.addWidget(self._runs_container)
        runs_layout.addWidget(_helper(INCOMPLETE_NOTE))

        selectors = QHBoxLayout()
        self._select_all = QPushButton("Select all")
        self._select_all.clicked.connect(self._on_select_all)
        self._select_complete = QPushButton("Select complete only")
        self._select_complete.clicked.connect(self._on_select_complete)
        selectors.addWidget(self._select_all)
        selectors.addWidget(self._select_complete)
        selectors.addStretch(1)
        runs_layout.addLayout(selectors)

        destination_card, destination_layout = _card("BIDS root")
        self._bids_root = QLineEdit()
        self._bids_root.setReadOnly(True)
        destination_layout.addWidget(self._bids_root)
        self._reveal = QPushButton("Reveal in Finder")
        self._reveal.clicked.connect(self._on_reveal)
        destination_layout.addWidget(self._reveal)

        self._export_button = QPushButton("Export selected")
        self._export_button.setObjectName("Primary")
        self._export_button.clicked.connect(self._start_export)
        destination_layout.addWidget(self._export_button)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        destination_layout.addWidget(self._progress)

        results_card, results_layout = _card("Results")
        self._results_label = _helper("")
        results_layout.addWidget(self._results_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        layout.addWidget(heading)
        layout.addWidget(runs_card)
        layout.addWidget(destination_card)
        layout.addWidget(results_card)
        layout.addStretch(1)

        self.refresh()

    # -- external state ---------------------------------------------------

    def set_session(self, session: SessionState | None) -> None:
        self._session = session
        self._results = []
        self._results_label.setText("")
        self.refresh()

    def selected_candidates(self) -> list[ExportCandidate]:
        return [candidate for box, candidate in self._boxes if box.isChecked()]

    # -- selection --------------------------------------------------------

    def _on_select_all(self) -> None:
        # A no-gaze run has nothing to export, so bulk selection skips it.
        for box, candidate in self._boxes:
            box.setChecked(not candidate.no_gaze)

    def _on_select_complete(self) -> None:
        for box, candidate in self._boxes:
            box.setChecked(candidate.checked_by_default)

    def _on_reveal(self) -> None:
        root = self._bids_root.text()
        if root:
            Path(root).mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(root))

    # -- exporting --------------------------------------------------------

    def _start_export(self) -> None:
        if self._session is None:
            return
        selected = self.selected_candidates()
        if not selected:
            return
        self._queue = list(selected)
        self._results = []
        self._progress.setRange(0, len(self._queue))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._set_controls_enabled(False)
        self._export_next()

    def _export_next(self) -> None:
        if self._session is None or not self._queue:
            self._finish()
            return
        self._active = self._queue.pop(0)
        self._output_lines = []
        self.export_requested.emit(
            build_export_args(self._active.run.path, bids_root(self._session.data_root))
        )

    def record_output_line(self, line: str) -> None:
        self._output_lines.append(line)

    def report_exit(self, exit_code: int) -> None:
        if self._active is None:
            return
        self._record_result(exit_code)
        self._active = None
        self._progress.setValue(self._progress.value() + 1)
        if self._queue:
            self._export_next()
            return
        self._finish()

    def report_failed_to_start(self, message: str) -> None:
        if self._active is not None:
            self._results.append(f"{FAILURE_MARKER}  {self._active.run.path.name}")
            self._active = None
        self._queue = []
        self._results.append(message)
        self._finish()

    def _record_result(self, exit_code: int) -> None:
        name = self._active.run.path.name
        if exit_code != 0:
            self._results.append(f"{FAILURE_MARKER}  {name} — exit code {exit_code}")
            return
        written = parse_written_files(self._output_lines)
        self._results.append(f"{SUCCESS_MARKER}  {name}")
        self._results.extend(f"      {path}" for path in written)

    def _finish(self) -> None:
        self._active = None
        self._queue = []
        self._progress.setVisible(False)
        self._results_label.setText("\n".join(self._results))
        self._set_controls_enabled(True)

    def _set_controls_enabled(self, enabled: bool) -> None:
        self._runs_container.setEnabled(enabled)
        self._select_all.setEnabled(enabled)
        self._select_complete.setEnabled(enabled)
        self._export_button.setEnabled(enabled and self._session is not None)

    # -- rendering --------------------------------------------------------

    def refresh(self) -> None:
        while self._runs_layout.count():
            item = self._runs_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._boxes = []

        session = self._session
        self._bids_root.setText(
            str(bids_root(session.data_root)) if session is not None else ""
        )
        if session is None:
            self._runs_layout.addWidget(_helper(NO_RUNS_TEXT))
            self._set_controls_enabled(True)
            return

        candidates = find_export_candidates(
            session.sourcedata_root, session.subject, session.session
        )
        if not candidates:
            self._runs_layout.addWidget(_helper(NO_RUNS_TEXT))
        for candidate in candidates:
            box = QCheckBox(describe_candidate(candidate))
            box.setChecked(candidate.checked_by_default)
            self._runs_layout.addWidget(box)
            self._boxes.append((box, candidate))
        self._set_controls_enabled(True)
