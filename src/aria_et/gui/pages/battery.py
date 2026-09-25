"""Battery page: per-task acquisition with progress polled from artifacts."""

from __future__ import annotations

import os
from dataclasses import replace

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from aria_et import tasks
from aria_et.config import AriaEtConfig
from aria_et.gui import artifacts
from aria_et.gui.artifacts import (
    JsonLinesTail,
    RunDirectory,
    RunProgress,
    RunStatus,
    apply_events,
    derive_status,
)
from aria_et.gui.process import SIGINT_SUPPORTED
from aria_et.gui.state import (
    PresentationOptions,
    SessionState,
    build_demo_args,
    build_run_args,
)
from aria_et.gui.widgets.crash_panel import CrashPanel
from aria_et.gui.widgets.task_card import TaskCard

POLL_INTERVAL_MILLISECONDS = 500

PREFLIGHT_MET = "✓"
PREFLIGHT_UNMET = "○"

NO_TRIAL_LIMIT = 0

BUFFERED_SAMPLE_CAVEAT = (
    "This platform cannot interrupt the task gently, so up to half a second "
    "of buffered gaze samples may be lost."
)

_DISPLAY_NAMES = {task.task_id: task.display_name for task in tasks.BATTERY_ORDER}


def describe_stop_confirmation(task_id: str) -> str:
    """The §10.2 prompt — a misclick mid-acquisition is expensive."""
    name = _DISPLAY_NAMES.get(task_id, task_id)
    prompt = f"Stop {name}? The partial run will be saved and marked incomplete."
    if not SIGINT_SUPPORTED:
        prompt += f"\n\n{BUFFERED_SAMPLE_CAVEAT}"
    return prompt


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


def preflight_conditions(
    session: SessionState | None, *, tracker_checked: bool
) -> list[tuple[str, bool]]:
    """The §7.4 gate, as an explainable checklist rather than a dead button."""
    if session is None:
        return [
            ("A session is open", False),
            ("Data root is writable", False),
            ("Tracker check has succeeded", tracker_checked),
        ]
    root = session.sourcedata_root
    writable = False
    existing = root
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    if existing.is_dir():
        writable = os.access(existing, os.W_OK)
    return [
        ("A session is open", True),
        (f"Data root is writable ({root})", writable),
        ("Tracker check has succeeded", tracker_checked),
    ]


class BatteryPage(QWidget):
    run_requested = Signal(list)
    stop_requested = Signal()

    def __init__(self, config: AriaEtConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._session: SessionState | None = None
        self._tracker_checked = False
        self._active_task: str | None = None
        self._active_run: RunDirectory | None = None
        self._active_snapshot: set = set()
        self._events_tail: JsonLinesTail | None = None
        self._progress = RunProgress()
        self._writes_data = True
        self._stop_requested = False

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MILLISECONDS)
        self._timer.timeout.connect(self._poll)

        heading = QLabel("Battery")
        heading.setObjectName("PageHeading")

        preflight_card, preflight_layout = _card("Before you can run")
        self._preflight = QLabel()
        self._preflight.setObjectName("HelperText")
        self._preflight.setWordWrap(True)
        preflight_layout.addWidget(self._preflight)

        self._options_card, options_layout = _card("Presentation")
        form = QFormLayout()
        form.setVerticalSpacing(6)
        self._fullscreen = QCheckBox("Fullscreen")
        self._fullscreen.setChecked(True)
        self._sound = QCheckBox("Play sound")
        self._sound.setChecked(True)
        self._debug_render = QCheckBox("Debug render overlay")
        self._window_size = QLineEdit("1024x768")
        self._screen = QSpinBox()
        self._screen.setRange(0, 8)
        self._screen.setValue(config.psychopy_screen)
        self._trial_limit = QSpinBox()
        self._trial_limit.setRange(NO_TRIAL_LIMIT, 999)
        self._trial_limit.setSpecialValueText("All trials")
        form.addRow("Display", self._fullscreen)
        form.addRow("Window size", self._window_size)
        form.addRow("Screen", self._screen)
        form.addRow("Trial limit", self._trial_limit)
        form.addRow("Sound", self._sound)
        form.addRow("Diagnostics", self._debug_render)
        options_layout.addLayout(form)
        # Fullscreen ignores the window size, so don't let it look editable.
        self._fullscreen.toggled.connect(self._sync_window_size_enabled)
        self._sync_window_size_enabled()

        self._cards: dict[str, TaskCard] = {}
        cards_container = QWidget()
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(10)
        for task in tasks.STANDALONE_TASKS:
            card = TaskCard(task.task_id, task.display_name)
            card.run_requested.connect(self._start_run)
            card.preview_requested.connect(self._start_preview)
            card.stop_requested.connect(self._request_stop)
            self._cards[task.task_id] = card
            cards_layout.addWidget(card)

        self._crash_panel = CrashPanel()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        layout.addWidget(heading)
        layout.addWidget(preflight_card)
        layout.addWidget(self._options_card)
        layout.addWidget(cards_container)
        layout.addWidget(self._crash_panel)
        layout.addStretch(1)

        self._refresh()

    # -- external state ---------------------------------------------------

    def set_session(self, session: SessionState | None) -> None:
        self._session = session
        self._refresh()

    def set_tracker_checked(self, checked: bool) -> None:
        self._tracker_checked = checked
        self._refresh()

    def presentation_options(self) -> PresentationOptions:
        limit = self._trial_limit.value()
        return PresentationOptions(
            fullscreen=self._fullscreen.isChecked(),
            screen=self._screen.value(),
            window_size=self._window_size.text().strip() or "1024x768",
            play_sound=self._sound.isChecked(),
            trial_limit=None if limit == NO_TRIAL_LIMIT else limit,
            debug_render=self._debug_render.isChecked(),
        )

    # -- launching --------------------------------------------------------

    def _start_run(self, task_id: str) -> None:
        if self._session is None or not self._can_run():
            return
        session = replace(self._session, presentation=self.presentation_options())
        self._active_snapshot = artifacts.snapshot_run_directories(
            session.sourcedata_root, session.subject, session.session, task_id
        )
        self._begin(task_id, writes_data=True)
        self.run_requested.emit(build_run_args(session, task_id))

    def _start_preview(self, task_id: str) -> None:
        if self._session is None:
            return
        session = replace(self._session, presentation=self.presentation_options())
        self._begin(task_id, writes_data=False)
        self.run_requested.emit(build_demo_args(session, task_id))

    def _request_stop(self, task_id: str) -> None:
        answer = QMessageBox.question(
            self,
            "Stop the running task?",
            describe_stop_confirmation(task_id),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is QMessageBox.StandardButton.Yes:
            self._confirm_stop()

    def _confirm_stop(self) -> None:
        self._stop_requested = True
        self.stop_requested.emit()

    def _begin(self, task_id: str, *, writes_data: bool) -> None:
        self._active_task = task_id
        self._active_run = None
        self._events_tail = None
        self._progress = RunProgress()
        self._writes_data = writes_data
        self._stop_requested = False
        self._crash_panel.clear()
        self._cards[task_id].show_running(self._progress)
        self._set_shared_controls_enabled(False)
        self._set_controls_enabled(False)
        if writes_data:
            self._timer.start()

    def report_exit(self, exit_code: int, log_lines: list[str] | None = None) -> None:
        self._timer.stop()
        if self._active_task is None:
            return
        self._poll_once()
        task_id = self._active_task
        self._active_task = None

        if self._writes_data:
            status = derive_status(
                self._progress, process_running=False, exit_code=exit_code
            )
            self._show_idle(task_id, status)
            self._report_crash(task_id, status, exit_code, log_lines or [])
        else:
            # A preview writes nothing, so the card must fall back to whatever
            # the task's real runs on disk say.
            self._refresh_idle_card(task_id, self._cards[task_id])

        self._active_run = None
        self._events_tail = None
        self._set_shared_controls_enabled(True)
        self._set_controls_enabled(True)

    def _report_crash(
        self, task_id: str, status: RunStatus, exit_code: int, log_lines: list[str]
    ) -> None:
        if status is RunStatus.COMPLETE:
            return
        if self._stop_requested and status is RunStatus.INCOMPLETE:
            # An operator-initiated stop is expected to end incomplete.
            return
        self._crash_panel.show_crash(
            _DISPLAY_NAMES.get(task_id, task_id),
            run_label=self._active_run.run_label if self._active_run else None,
            exit_code=exit_code,
            log_lines=log_lines,
            run_dir=self._active_run.path if self._active_run else None,
        )

    # -- polling ----------------------------------------------------------

    def _poll(self) -> None:
        self._poll_once()
        if self._active_task is None:
            return
        self._cards[self._active_task].show_running(
            self._progress,
            health=self._health(),
            run_label=self._active_run.run_label if self._active_run else None,
        )

    def _poll_once(self) -> None:
        if self._session is None or self._active_task is None or not self._writes_data:
            return
        session = self._session
        if self._active_run is None:
            self._active_run = artifacts.find_new_run_directory(
                self._active_snapshot,
                session.sourcedata_root,
                session.subject,
                session.session,
                self._active_task,
            )
            if self._active_run is None:
                return
            self._events_tail = JsonLinesTail(
                self._active_run.path / artifacts.EVENTS_NAME
            )
        if self._events_tail is not None:
            self._progress = apply_events(
                self._progress, self._events_tail.read_new(), self._active_task
            )

    def _health(self):
        if self._active_run is None:
            return None
        return artifacts.read_writer_health(self._active_run.path)

    # -- rendering --------------------------------------------------------

    def _can_run(self) -> bool:
        return all(
            met
            for _, met in preflight_conditions(
                self._session, tracker_checked=self._tracker_checked
            )
        )

    def _set_shared_controls_enabled(self, enabled: bool) -> None:
        self._options_card.setEnabled(enabled)

    def _sync_window_size_enabled(self) -> None:
        self._window_size.setEnabled(not self._fullscreen.isChecked())

    def _set_controls_enabled(self, idle: bool) -> None:
        for card in self._cards.values():
            # Preview needs no tracker and writes nothing, so the pre-flight
            # gate applies to Run alone.
            card.set_controls_enabled(
                can_run=idle and self._can_run(),
                can_preview=idle and self._session is not None,
            )

    def _show_idle(self, task_id: str, status: RunStatus) -> None:
        session = self._session
        next_label = "01"
        run_label = self._active_run.run_label if self._active_run else None
        if session is not None:
            next_label = artifacts.next_run_label(
                session.sourcedata_root, session.subject, session.session, task_id
            )
        self._cards[task_id].show_idle(
            status,
            self._progress,
            next_run_label=next_label,
            health=self._health(),
            run_label=run_label,
        )

    def _refresh(self) -> None:
        conditions = preflight_conditions(
            self._session, tracker_checked=self._tracker_checked
        )
        self._preflight.setText(
            "\n".join(
                f"{PREFLIGHT_MET if met else PREFLIGHT_UNMET}  {text}"
                for text, met in conditions
            )
        )
        if self._active_task is not None:
            return
        for task_id, card in self._cards.items():
            self._refresh_idle_card(task_id, card)
        self._set_controls_enabled(True)

    def _refresh_idle_card(self, task_id: str, card: TaskCard) -> None:
        session = self._session
        if session is None:
            card.show_idle(RunStatus.NOT_STARTED, RunProgress(), next_run_label="01")
            return
        runs = artifacts.find_run_directories(
            session.sourcedata_root, session.subject, session.session, task_id
        )
        next_label = artifacts.next_run_label(
            session.sourcedata_root, session.subject, session.session, task_id
        )
        if not runs:
            card.show_idle(
                RunStatus.NOT_STARTED, RunProgress(), next_run_label=next_label
            )
            return
        latest = runs[-1]
        progress = artifacts.read_progress(latest)
        card.show_idle(
            derive_status(progress, process_running=False, exit_code=None),
            progress,
            next_run_label=next_label,
            health=artifacts.read_writer_health(latest.path),
            run_label=latest.run_label,
        )
