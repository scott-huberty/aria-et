from pathlib import Path

import pytest

from aria_et import tasks
from aria_et.cli import build_parser
from aria_et.config import AriaEtConfig
from aria_et.gui import state


@pytest.fixture
def parser(tmp_path):
    return build_parser(AriaEtConfig(data_root=tmp_path / "aria-data"))


@pytest.fixture
def session(tmp_path):
    return state.SessionState(subject="abby", data_root=tmp_path / "aria-data")


def test_dry_run_is_disallowed_unless_env_var_is_set():
    assert not state.dry_run_allowed({})
    assert not state.dry_run_allowed({state.DRY_RUN_ENV_VAR: "true"})
    assert state.dry_run_allowed({state.DRY_RUN_ENV_VAR: "1"})


def test_dry_run_writes_under_a_separate_root(tmp_path):
    data_root = tmp_path / "aria-data"
    assert state.sourcedata_root(data_root, state.RunMode.ACQUISITION) == (
        data_root / "sourcedata"
    )
    assert state.sourcedata_root(data_root, state.RunMode.DRY_RUN) == (
        data_root / "dry-runs" / "sourcedata"
    )


def test_run_mode_maps_to_cli_tracker_choice():
    assert state.RunMode.ACQUISITION.tracker == "tobii"
    assert state.RunMode.DRY_RUN.tracker == "none"


@pytest.mark.parametrize("task_id", sorted(state.TASK_RUN_COMMANDS))
def test_build_run_args_parse_against_the_real_cli(parser, session, task_id):
    args = parser.parse_args(state.build_run_args(session, task_id))

    assert args.command == state.TASK_RUN_COMMANDS[task_id]
    assert args.subject == "abby"
    assert args.session == "01"
    assert args.tracker == "tobii"
    assert Path(args.output) == session.sourcedata_root


def test_build_run_args_never_request_an_explicit_run_label(session):
    args = state.build_run_args(session, tasks.ACTIVITY_MONITORING.task_id)

    assert "--run" not in args


def test_build_run_args_omit_address_in_dry_run_mode(session):
    dry = state.SessionState(
        subject=session.subject,
        data_root=session.data_root,
        mode=state.RunMode.DRY_RUN,
        tracker_address="tobii-prp://169.254.10.180",
    )

    args = state.build_run_args(dry, tasks.ACTIVITY_MONITORING.task_id)

    assert "--address" not in args
    assert args[args.index("--tracker") + 1] == "none"


def test_build_run_args_pass_address_in_acquisition_mode(session):
    acquisition = state.SessionState(
        subject=session.subject,
        data_root=session.data_root,
        tracker_address="tobii-prp://169.254.10.180",
    )

    args = state.build_run_args(acquisition, tasks.ACTIVITY_MONITORING.task_id)

    assert args[args.index("--address") + 1] == "tobii-prp://169.254.10.180"


def test_build_run_args_translate_windowed_presentation(parser, session):
    windowed = state.SessionState(
        subject=session.subject,
        data_root=session.data_root,
        presentation=state.PresentationOptions(
            fullscreen=False,
            screen=0,
            window_size="800x600",
            play_sound=False,
            trial_limit=2,
            debug_render=True,
        ),
    )

    args = parser.parse_args(
        state.build_run_args(windowed, tasks.ACTIVITY_MONITORING.task_id)
    )

    assert args.fullscreen is False
    assert args.screen == 0
    assert args.size == "800x600"
    assert args.no_sound is True
    assert args.trial_limit == 2
    assert args.debug_render is True


@pytest.mark.parametrize("task_id", sorted(state.TASK_DEMO_COMMANDS))
def test_build_demo_args_parse_and_carry_no_bids_entities(parser, session, task_id):
    argv = state.build_demo_args(session, task_id)
    args = parser.parse_args(argv)

    assert args.command == state.TASK_DEMO_COMMANDS[task_id]
    assert not any(flag in argv for flag in ("--subject", "--output", "--tracker"))


def test_build_check_args_parse(parser):
    args = parser.parse_args(state.build_check_args("tobii-prp://169.254.10.180"))

    assert args.command == "check-eyetracker"
    assert args.address == "tobii-prp://169.254.10.180"


def test_build_calibrate_args_parse_for_the_etm_routine(parser, session):
    argv = state.build_calibrate_args(session, state.CalibrationOptions())
    args = parser.parse_args(argv)

    assert args.command == "calibrate-eyetracker"
    assert args.routine == "etm"
    assert args.subject == "abby"
    assert args.session == "01"
    assert "--point-duration" not in argv


def test_build_calibrate_args_include_child_friendly_flags(parser, session):
    args = parser.parse_args(
        state.build_calibrate_args(
            session,
            state.CalibrationOptions(
                routine="child-friendly",
                point_duration_seconds=1.5,
                advance_on_space=True,
                fullscreen=False,
                window_size="800x600",
                play_sound=False,
            ),
        )
    )

    assert args.routine == "child-friendly"
    assert args.point_duration == 1.5
    assert args.advance_on_space is True
    assert args.fullscreen is False
    assert args.size == "800x600"
    assert args.no_sound is True


def test_build_export_args_parse(parser, tmp_path):
    run_dir = tmp_path / "task-activity-monitoring_run-01"
    bids_dir = tmp_path / "bids"

    args = parser.parse_args(state.build_export_args(run_dir, bids_dir))

    assert args.command == "export-bids"
    assert Path(args.run_dir) == run_dir
    assert Path(args.bids_root) == bids_dir
