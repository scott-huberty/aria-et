"""Run modes, session state, and CLI argument construction for the GUI."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from aria_et import tasks

DRY_RUN_ENV_VAR = "ARIA_ET_ALLOW_DRY_RUN"
DEFAULT_SESSION_LABEL = "01"
DRY_RUN_DIR_NAME = "dry-runs"
SOURCEDATA_DIR_NAME = "sourcedata"
BIDS_DIR_NAME = "bids"


class RunMode(Enum):
    ACQUISITION = "acquisition"
    DRY_RUN = "dry-run"

    @property
    def tracker(self) -> str:
        return "none" if self is RunMode.DRY_RUN else "tobii"


TASK_RUN_COMMANDS: dict[str, str] = {
    tasks.ACTIVITY_MONITORING.task_id: "run-am",
    tasks.SOCIAL_INTERACTIVE.task_id: "run-si",
    tasks.STATIC_SOCIAL_SCENES.task_id: "run-ss",
    tasks.PUPILLARY_LIGHT_REFLEX.task_id: "run-plr",
}

TASK_DEMO_COMMANDS: dict[str, str] = {
    tasks.CALIBRATION.task_id: "demo-calibration",
    tasks.ACTIVITY_MONITORING.task_id: "demo-am",
    tasks.SOCIAL_INTERACTIVE.task_id: "demo-si",
    tasks.STATIC_SOCIAL_SCENES.task_id: "demo-ss",
    tasks.PUPILLARY_LIGHT_REFLEX.task_id: "demo-plr",
}


def dry_run_allowed(env: Mapping[str, str] | None = None) -> bool:
    return (env if env is not None else os.environ).get(DRY_RUN_ENV_VAR) == "1"


def sourcedata_root(data_root: Path, mode: RunMode) -> Path:
    if mode is RunMode.DRY_RUN:
        return data_root / DRY_RUN_DIR_NAME / SOURCEDATA_DIR_NAME
    return data_root / SOURCEDATA_DIR_NAME


def bids_root(data_root: Path) -> Path:
    return data_root / BIDS_DIR_NAME


@dataclass(frozen=True)
class PresentationOptions:
    fullscreen: bool = True
    screen: int | None = None
    window_size: str = "1024x768"
    play_sound: bool = True
    trial_limit: int | None = None
    debug_render: bool = False


@dataclass(frozen=True)
class CalibrationOptions:
    routine: str = "etm"
    serial_number: str | None = None
    manager: str | None = None
    screen: int | None = None
    point_duration_seconds: float = 3.0
    advance_on_space: bool = False
    fullscreen: bool = True
    window_size: str = "1024x768"
    play_sound: bool = True
    debug_render: bool = False


@dataclass(frozen=True)
class SessionState:
    subject: str
    data_root: Path
    session: str = DEFAULT_SESSION_LABEL
    mode: RunMode = RunMode.ACQUISITION
    tracker_address: str | None = None
    presentation: PresentationOptions = field(default_factory=PresentationOptions)

    @property
    def sourcedata_root(self) -> Path:
        return sourcedata_root(self.data_root, self.mode)


def _display_args(
    *, fullscreen: bool, window_size: str, screen: int | None
) -> list[str]:
    args = ["--fullscreen"] if fullscreen else ["--windowed", "--size", window_size]
    if screen is not None:
        args += ["--screen", str(screen)]
    return args


def _presentation_args(
    options: PresentationOptions, *, include_trial_limit: bool = True
) -> list[str]:
    args = _display_args(
        fullscreen=options.fullscreen,
        window_size=options.window_size,
        screen=options.screen,
    )
    if not options.play_sound:
        args.append("--no-sound")
    if include_trial_limit and options.trial_limit is not None:
        args += ["--trial-limit", str(options.trial_limit)]
    if options.debug_render:
        args.append("--debug-render")
    return args


def build_run_args(state: SessionState, task_id: str) -> list[str]:
    """Build ``run-*`` argv. Never passes ``--run``; the CLI auto-assigns it."""
    command = TASK_RUN_COMMANDS[task_id]
    args = [
        command,
        "--tracker",
        state.mode.tracker,
        "--subject",
        state.subject,
        "--session",
        state.session,
        "--output",
        str(state.sourcedata_root),
    ]
    if state.mode is RunMode.ACQUISITION and state.tracker_address:
        args += ["--address", state.tracker_address]
    return args + _presentation_args(state.presentation)


def build_demo_args(state: SessionState, task_id: str) -> list[str]:
    """Build ``demo-*`` argv. Demos write nothing and take no BIDS entities."""
    return [TASK_DEMO_COMMANDS[task_id], *_presentation_args(state.presentation)]


def build_check_args(address: str | None = None) -> list[str]:
    args = ["check-eyetracker"]
    if address:
        args += ["--address", address]
    return args


def build_save_tracker_args(serial_number: str) -> list[str]:
    return ["find-eyetracker", "--save", "--serial-number", serial_number]


def build_calibrate_args(state: SessionState, options: CalibrationOptions) -> list[str]:
    args = [
        "calibrate-eyetracker",
        "--routine",
        options.routine,
        "--subject",
        state.subject,
        "--session",
        state.session,
        "--output",
        str(state.sourcedata_root),
    ]
    if state.tracker_address:
        args += ["--address", state.tracker_address]
    if options.serial_number:
        args += ["--serial-number", options.serial_number]
    if options.manager:
        args += ["--manager", options.manager]
    if options.screen is not None:
        args += ["--screen", str(options.screen)]
    if options.routine == "child-friendly":
        args += _display_args(
            fullscreen=options.fullscreen,
            window_size=options.window_size,
            screen=None,
        )
        if not options.play_sound:
            args.append("--no-sound")
        args += ["--point-duration", str(options.point_duration_seconds)]
        if options.advance_on_space:
            args.append("--advance-on-space")
        if options.debug_render:
            args.append("--debug-render")
    return args


def build_export_args(run_dir: Path, bids_root_dir: Path) -> list[str]:
    return ["export-bids", "--input", str(run_dir), "--output", str(bids_root_dir)]


def build_init_config_args() -> list[str]:
    return ["init-config"]


class ExitSeverity(Enum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ExitOutcome:
    code: int
    severity: ExitSeverity
    message: str


_EXIT_OUTCOMES: dict[int, tuple[ExitSeverity, str]] = {
    0: (ExitSeverity.SUCCESS, "Finished successfully."),
    1: (ExitSeverity.ERROR, "The command failed. See the console output below."),
    2: (ExitSeverity.ERROR, "Tobii Pro SDK not installed in this environment."),
    3: (
        ExitSeverity.WARNING,
        (
            "Tracker not found. Check power and the Ethernet link, "
            "then retry with an explicit address."
        ),
    ),
}


def describe_exit_code(code: int) -> ExitOutcome:
    severity, message = _EXIT_OUTCOMES.get(
        code, (ExitSeverity.ERROR, f"The command exited with code {code}.")
    )
    return ExitOutcome(code=code, severity=severity, message=message)
