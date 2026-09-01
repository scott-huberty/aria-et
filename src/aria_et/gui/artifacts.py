"""Reading run progress and health from on-disk session artifacts."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

RUN_DIR_PATTERN = re.compile(r"^task-(?P<task>.+)_run-(?P<run>[A-Za-z0-9]+)$")

SESSION_METADATA_NAME = "session.json"
EVENTS_NAME = "events.jsonl"
GAZE_NAME = "gaze.jsonl"
WRITER_HEALTH_NAME = "gaze_writer.json"


@dataclass(frozen=True)
class RunDirectory:
    path: Path
    task_id: str
    run_label: str


class SessionOpenState(Enum):
    NEW = "new"
    HAS_DATA = "has-data"


class RunStatus(Enum):
    NOT_STARTED = "not-started"
    RUNNING = "running"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


@dataclass(frozen=True)
class RunProgress:
    started: bool = False
    ended: bool = False
    trials_started: int = 0
    trials_ended: int = 0
    trial_count: int | None = None


@dataclass(frozen=True)
class WriterHealth:
    received: int
    written: int
    dropped: int
    queued: int
    flush_count: int


def subject_session_dir(sourcedata_root: Path, subject: str, session: str) -> Path:
    return sourcedata_root / f"sub-{subject}" / f"ses-{session}"


def find_run_directories(
    sourcedata_root: Path,
    subject: str,
    session: str,
    task_id: str | None = None,
) -> list[RunDirectory]:
    session_dir = subject_session_dir(sourcedata_root, subject, session)
    if not session_dir.is_dir():
        return []
    found = []
    for child in session_dir.iterdir():
        if not child.is_dir():
            continue
        match = RUN_DIR_PATTERN.match(child.name)
        if match is None:
            continue
        if task_id is not None and match.group("task") != task_id:
            continue
        found.append(RunDirectory(child, match.group("task"), match.group("run")))
    return sorted(found, key=lambda run: (run.task_id, run.run_label))


def classify_session(
    sourcedata_root: Path, subject: str, session: str
) -> SessionOpenState:
    if find_run_directories(sourcedata_root, subject, session):
        return SessionOpenState.HAS_DATA
    return SessionOpenState.NEW


def next_free_session_label(sourcedata_root: Path, subject: str, width: int = 2) -> str:
    number = 1
    while True:
        candidate = str(number).zfill(width)
        if (
            classify_session(sourcedata_root, subject, candidate)
            is SessionOpenState.NEW
        ):
            return candidate
        number += 1


def snapshot_run_directories(
    sourcedata_root: Path, subject: str, session: str, task_id: str
) -> set[Path]:
    return {
        run.path
        for run in find_run_directories(sourcedata_root, subject, session, task_id)
    }


def find_new_run_directory(
    snapshot: set[Path], sourcedata_root: Path, subject: str, session: str, task_id: str
) -> RunDirectory | None:
    created = [
        run
        for run in find_run_directories(sourcedata_root, subject, session, task_id)
        if run.path not in snapshot
    ]
    if not created:
        return None
    return max(created, key=lambda run: run.run_label)


def apply_events(
    progress: RunProgress, events: Iterable[dict], task_id: str
) -> RunProgress:
    started = progress.started
    ended = progress.ended
    trials_started = progress.trials_started
    trials_ended = progress.trials_ended
    trial_count = progress.trial_count

    for event in events:
        name = event.get("name")
        if name == f"{task_id}.started":
            started = True
        elif name == f"{task_id}.ended":
            ended = True
            payload = event.get("payload") or {}
            reported = payload.get("trial_count")
            if isinstance(reported, int):
                trial_count = reported
        elif name == f"{task_id}.trial.started":
            trials_started += 1
        elif name == f"{task_id}.trial.ended":
            trials_ended += 1

    return replace(
        progress,
        started=started,
        ended=ended,
        trials_started=trials_started,
        trials_ended=trials_ended,
        trial_count=trial_count,
    )


def derive_status(
    progress: RunProgress, *, process_running: bool, exit_code: int | None
) -> RunStatus:
    if process_running:
        return RunStatus.RUNNING
    if exit_code is None and not progress.started:
        return RunStatus.NOT_STARTED
    if progress.ended:
        return RunStatus.COMPLETE
    if exit_code not in (None, 0):
        return RunStatus.FAILED
    if progress.started:
        return RunStatus.INCOMPLETE
    return RunStatus.NOT_STARTED


class JsonLinesTail:
    """Incrementally reads whole JSON lines appended to a file."""

    def __init__(self, path: Path):
        self.path = path
        self._offset = 0

    def read_new(self) -> list[dict]:
        if not self.path.is_file():
            return []
        with self.path.open("rb") as handle:
            handle.seek(self._offset)
            chunk = handle.read()
        newline = chunk.rfind(b"\n")
        if newline == -1:
            return []
        self._offset += newline + 1
        return _parse_json_lines(chunk[: newline + 1])


def _parse_json_lines(chunk: bytes) -> list[dict]:
    records = []
    for line in chunk.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def read_session_metadata(run_dir: Path) -> dict | None:
    path = run_dir / SESSION_METADATA_NAME
    if not path.is_file():
        return None
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return metadata if isinstance(metadata, dict) else None


def is_dry_run_metadata(metadata: dict | None) -> bool:
    return bool(metadata) and metadata.get("tracker") == "none"


def has_gaze(run_dir: Path) -> bool:
    gaze = run_dir / GAZE_NAME
    return gaze.is_file() and gaze.stat().st_size > 0


def read_writer_health(run_dir: Path) -> WriterHealth | None:
    path = run_dir / WRITER_HEALTH_NAME
    if not path.is_file():
        return None
    try:
        health = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(health, dict):
        return None
    return WriterHealth(
        received=_as_int(health.get("received_queue_samples")),
        written=_as_int(health.get("written_queue_samples")),
        dropped=_as_int(health.get("dropped_queue_samples")),
        queued=_as_int(health.get("queued_samples")),
        flush_count=_as_int(health.get("flush_count")),
    )


def _as_int(value: object) -> int:
    return value if isinstance(value, int) else 0
