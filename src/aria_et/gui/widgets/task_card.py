"""One battery task: status marker, derived progress line, and its controls."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from aria_et.gui.artifacts import RunProgress, RunStatus, WriterHealth
from aria_et.gui.widgets.status_pill import PillTone, tone_foreground

PREVIEW_BUTTON_TEXT = "Preview (records nothing)"

STATUS_MARKERS: dict[RunStatus, str] = {
    RunStatus.NOT_STARTED: "○",
    RunStatus.RUNNING: "◐",
    RunStatus.COMPLETE: "✓",
    RunStatus.INCOMPLETE: "!",
    RunStatus.FAILED: "✕",
}

STATUS_TONES: dict[RunStatus, PillTone] = {
    RunStatus.NOT_STARTED: PillTone.NEUTRAL,
    RunStatus.RUNNING: PillTone.BUSY,
    RunStatus.COMPLETE: PillTone.GOOD,
    RunStatus.INCOMPLETE: PillTone.WARNING,
    RunStatus.FAILED: PillTone.BAD,
}


def describe_progress(
    status: RunStatus, progress: RunProgress, health: WriterHealth | None = None
) -> str:
    """Render the one-line human summary shown under a task's name."""
    if status is RunStatus.NOT_STARTED:
        return "Not started"

    if status is RunStatus.RUNNING:
        if not progress.started:
            return "Starting…"
        if progress.trial_count:
            return (
                f"Running — trial {progress.trials_started} of {progress.trial_count}"
            )
        return f"Running — trial {progress.trials_started}"

    trials = progress.trial_count
    if trials is None:
        trials = progress.trials_ended
    detail = f"{trials} trial{'' if trials == 1 else 's'}"
    if health is not None:
        detail += f", {health.written:,} gaze samples"

    if status is RunStatus.COMPLETE:
        return f"Complete — {detail}"
    if status is RunStatus.INCOMPLETE:
        return f"Incomplete — ended without a completion event after {detail}"
    return f"Failed — {detail}"


def describe_dropped_samples(health: WriterHealth | None) -> str | None:
    if health is None or health.dropped <= 0:
        return None
    return f"{health.dropped:,} gaze samples dropped — queue pressure."


class TaskCard(QFrame):
    run_requested = Signal(str)
    preview_requested = Signal(str)
    stop_requested = Signal(str)

    def __init__(self, task_id: str, display_name: str, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.setObjectName("Card")

        self._marker = QLabel()
        self._marker.setFixedWidth(18)
        self._name = QLabel(display_name)
        self._name.setObjectName("SubsectionHeading")
        self._run_label = QLabel()
        self._run_label.setObjectName("HelperText")

        title_row = QHBoxLayout()
        title_row.addWidget(self._marker)
        title_row.addWidget(self._name)
        title_row.addStretch(1)
        title_row.addWidget(self._run_label)

        self._status = QLabel()
        self._status.setObjectName("HelperText")
        self._status.setWordWrap(True)

        self._warning = QLabel()
        self._warning.setObjectName("ModeBanner")
        self._warning.setWordWrap(True)
        self._warning.setVisible(False)

        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)

        self._run_button = QPushButton("Run")
        self._run_button.setObjectName("Primary")
        self._run_button.clicked.connect(lambda: self.run_requested.emit(self.task_id))
        self._preview_button = QPushButton(PREVIEW_BUTTON_TEXT)
        self._preview_button.clicked.connect(
            lambda: self.preview_requested.emit(self.task_id)
        )
        self._stop_button = QPushButton("Stop")
        self._stop_button.clicked.connect(
            lambda: self.stop_requested.emit(self.task_id)
        )
        self._stop_button.setVisible(False)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self._run_button)
        button_row.addWidget(self._preview_button)
        button_row.addWidget(self._stop_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        layout.addLayout(title_row)
        layout.addWidget(self._status)
        layout.addWidget(self._progress)
        layout.addWidget(self._warning)
        layout.addLayout(button_row)

        self.show_idle(RunStatus.NOT_STARTED, RunProgress(), next_run_label="01")

    def show_idle(
        self,
        status: RunStatus,
        progress: RunProgress,
        *,
        next_run_label: str,
        health: WriterHealth | None = None,
        run_label: str | None = None,
    ) -> None:
        self._apply_status(status, progress, health, run_label)
        self._progress.setVisible(False)
        self._stop_button.setVisible(False)
        self._run_button.setVisible(True)
        self._preview_button.setVisible(True)
        self._run_button.setText(
            "Run"
            if status is RunStatus.NOT_STARTED
            else f"Run again (run-{next_run_label})"
        )

    def show_running(
        self,
        progress: RunProgress,
        *,
        health: WriterHealth | None = None,
        run_label: str | None = None,
    ) -> None:
        self._apply_status(RunStatus.RUNNING, progress, health, run_label)
        self._run_button.setVisible(False)
        self._preview_button.setVisible(False)
        self._stop_button.setVisible(True)
        self._stop_button.setEnabled(True)
        self._progress.setVisible(True)
        if progress.trial_count:
            self._progress.setRange(0, progress.trial_count)
            self._progress.setValue(progress.trials_ended)
        else:
            self._progress.setRange(0, 0)

    def set_controls_enabled(self, *, can_run: bool, can_preview: bool) -> None:
        self._run_button.setEnabled(can_run)
        self._preview_button.setEnabled(can_preview)

    def _apply_status(
        self,
        status: RunStatus,
        progress: RunProgress,
        health: WriterHealth | None,
        run_label: str | None,
    ) -> None:
        color = tone_foreground(STATUS_TONES[status])
        self._marker.setText(STATUS_MARKERS[status])
        self._marker.setStyleSheet(f"color: {color}; font-weight: 700;")
        self._run_label.setText(f"run-{run_label}" if run_label else "")
        self._status.setText(describe_progress(status, progress, health))
        warning = describe_dropped_samples(health)
        self._warning.setText(warning or "")
        self._warning.setVisible(warning is not None)
