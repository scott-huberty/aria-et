"""Per-page completion shown in the sidebar.

Completion is read from real state (the open session, the tracker check, and
artifacts on disk), never from the operator having clicked through a page, so
a check mark can be trusted at a glance. It is informational only: nothing
here gates navigation or running tasks.
"""

from __future__ import annotations

from dataclasses import dataclass

from aria_et import tasks
from aria_et.gui import artifacts
from aria_et.gui.artifacts import RunStatus
from aria_et.gui.state import SessionState


@dataclass(frozen=True)
class PageProgress:
    done: bool
    detail: str = ""  # shown after the page name, e.g. "2/4" for the battery


def page_progress(
    session: SessionState | None,
    *,
    tracker_connected: bool,
    export_succeeded: bool,
) -> tuple[PageProgress, ...]:
    """Progress for Setup, Hardware, Calibration, Battery and Export, in order."""
    hardware = PageProgress(done=tracker_connected)
    if session is None:
        return (
            PageProgress(done=False),
            hardware,
            PageProgress(done=False),
            PageProgress(done=False),
            PageProgress(done=False),
        )

    calibrated = bool(
        artifacts.find_calibrations(
            session.sourcedata_root, session.subject, session.session
        )
    )
    completed_tasks = sum(
        _task_completed(session, task.task_id) for task in tasks.STANDALONE_TASKS
    )
    total_tasks = len(tasks.STANDALONE_TASKS)
    return (
        PageProgress(done=True),
        hardware,
        PageProgress(done=calibrated),
        PageProgress(
            done=completed_tasks == total_tasks,
            detail=f"{completed_tasks}/{total_tasks}",
        ),
        PageProgress(done=export_succeeded),
    )


def _task_completed(session: SessionState, task_id: str) -> bool:
    """A task counts once any of its runs completed; a later re-run can't undo that."""
    return any(
        artifacts.derive_status(
            artifacts.read_progress(run), process_running=False, exit_code=None
        )
        is RunStatus.COMPLETE
        for run in artifacts.find_run_directories(
            session.sourcedata_root, session.subject, session.session, task_id
        )
    )
