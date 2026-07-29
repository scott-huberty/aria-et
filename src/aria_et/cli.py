"""Command line entry points for ARIA eye-tracking tasks."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from aria_et.tasks import BATTERY_ORDER


DEFAULT_ETM_SCREEN = 2
DEFAULT_PSYCHOPY_SCREEN = 1

DemoCalibrationRunner = Callable[..., int]
CalibrateEyeTrackerRunner = Callable[..., int]
DemoActivityMonitoringRunner = Callable[..., int]
DemoSocialInteractiveRunner = Callable[..., int]
DemoStaticSocialScenesRunner = Callable[..., int]
DemoPupillaryLightReflexRunner = Callable[..., int]
CheckEyeTrackerRunner = Callable[..., int]
RunActivityMonitoringRunner = Callable[..., int]
RunStaticSocialScenesRunner = Callable[..., int]
RunPupillaryLightReflexRunner = Callable[..., int]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aria-et")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "list-tasks",
        help="Print the configured battery order.",
    )

    check_eyetracker = subparsers.add_parser(
        "check-eyetracker",
        help="Check Tobii SDK availability and connected eye tracker discovery.",
    )
    check_eyetracker.add_argument(
        "--address",
        default=None,
        help="Optional Tobii tracker URI to connect to directly, bypassing discovery.",
    )

    calibrate_eyetracker = subparsers.add_parser(
        "calibrate-eyetracker",
        help="Launch Tobii Pro Eye Tracker Manager user calibration.",
    )
    calibrate_eyetracker.add_argument(
        "--address",
        default=None,
        help="Optional Tobii tracker URI to calibrate directly.",
    )
    calibrate_eyetracker.add_argument(
        "--serial-number",
        default=None,
        help="Optional Tobii tracker serial number to calibrate directly.",
    )
    calibrate_eyetracker.add_argument(
        "--screen",
        type=int,
        default=DEFAULT_ETM_SCREEN,
        help=(
            "ETM display number for calibration. Default 2 targets the EIZO "
            "stimulus display in the lab setup."
        ),
    )
    calibrate_eyetracker.add_argument(
        "--manager",
        default=None,
        help="Path to Tobii Pro Eye Tracker Manager executable.",
    )
    calibrate_eyetracker.add_argument(
        "--output",
        default="calibrations",
        help="Directory where calibration artifacts are saved.",
    )

    demo_calibration = subparsers.add_parser(
        "demo-calibration",
        help="Run the bundled Gap-Overlap reward calibration sequence in PsychoPy.",
    )
    display_mode = demo_calibration.add_mutually_exclusive_group()
    display_mode.add_argument(
        "--fullscreen",
        action="store_true",
        help="Run full screen.",
    )
    display_mode.add_argument(
        "--windowed",
        action="store_false",
        dest="fullscreen",
        help="Run in a window.",
    )
    demo_calibration.set_defaults(fullscreen=True)
    demo_calibration.add_argument(
        "--screen",
        type=int,
        default=DEFAULT_PSYCHOPY_SCREEN,
        help=(
            "PsychoPy display index. Default 1 targets the EIZO stimulus "
            "display in the lab setup."
        ),
    )
    demo_calibration.add_argument(
        "--size",
        default="1024x768",
        help="Window size for --windowed mode, formatted as WIDTHxHEIGHT.",
    )
    demo_calibration.add_argument(
        "--no-sound",
        action="store_true",
        help="Disable calibration sound playback.",
    )
    demo_calibration.add_argument(
        "--point-duration",
        type=float,
        default=3.0,
        help="Seconds to display each calibration point.",
    )
    demo_calibration.add_argument(
        "--advance-on-space",
        action="store_true",
        help="Wait for Space before moving to the next calibration point.",
    )
    demo_calibration.add_argument(
        "--debug-render",
        action="store_true",
        help="Print frame-level PsychoPy rendering diagnostics.",
    )

    demo_am = subparsers.add_parser(
        "demo-am",
        help="Run the bundled Activity Monitoring sequence in PsychoPy.",
    )
    am_display_mode = demo_am.add_mutually_exclusive_group()
    am_display_mode.add_argument(
        "--fullscreen",
        action="store_true",
        help="Run full screen.",
    )
    am_display_mode.add_argument(
        "--windowed",
        action="store_false",
        dest="fullscreen",
        help="Run in a window. This is the default.",
    )
    demo_am.set_defaults(fullscreen=False)
    _add_screen_argument(demo_am)
    demo_am.add_argument(
        "--size",
        default="1024x768",
        help="Window size for --windowed mode, formatted as WIDTHxHEIGHT.",
    )
    demo_am.add_argument(
        "--no-sound",
        action="store_true",
        help="Disable static-trial soundtrack playback.",
    )
    demo_am.add_argument(
        "--trial-limit",
        type=int,
        default=None,
        help="Limit the number of AM trials for demos.",
    )
    demo_am.add_argument(
        "--debug-render",
        action="store_true",
        help="Print AM rendering diagnostics.",
    )

    run_am = subparsers.add_parser(
        "run-am",
        help="Run Activity Monitoring as an acquisition session.",
    )
    _add_run_presentation_arguments(
        run_am,
        no_sound_help="Disable static-trial soundtrack playback.",
        trial_limit_help="Limit the number of AM trials.",
        debug_help="Print AM rendering diagnostics.",
    )

    demo_si = subparsers.add_parser(
        "demo-si",
        help="Run the bundled Social Interactive sequence in PsychoPy.",
    )
    si_display_mode = demo_si.add_mutually_exclusive_group()
    si_display_mode.add_argument(
        "--fullscreen",
        action="store_true",
        help="Run full screen.",
    )
    si_display_mode.add_argument(
        "--windowed",
        action="store_false",
        dest="fullscreen",
        help="Run in a window. This is the default.",
    )
    demo_si.set_defaults(fullscreen=False)
    _add_screen_argument(demo_si)
    demo_si.add_argument(
        "--size",
        default="1024x768",
        help="Window size for --windowed mode, formatted as WIDTHxHEIGHT.",
    )
    demo_si.add_argument(
        "--no-sound",
        action="store_true",
        help="Disable movie audio playback.",
    )
    demo_si.add_argument(
        "--trial-limit",
        type=int,
        default=None,
        help="Limit the number of SI trials for demos.",
    )
    demo_si.add_argument(
        "--debug-render",
        action="store_true",
        help="Print SI rendering diagnostics.",
    )

    demo_ss = subparsers.add_parser(
        "demo-ss",
        help="Run the bundled Static Social Scenes sequence in PsychoPy.",
    )
    ss_display_mode = demo_ss.add_mutually_exclusive_group()
    ss_display_mode.add_argument(
        "--fullscreen",
        action="store_true",
        help="Run full screen.",
    )
    ss_display_mode.add_argument(
        "--windowed",
        action="store_false",
        dest="fullscreen",
        help="Run in a window. This is the default.",
    )
    demo_ss.set_defaults(fullscreen=False)
    _add_screen_argument(demo_ss)
    demo_ss.add_argument(
        "--size",
        default="1024x768",
        help="Window size for --windowed mode, formatted as WIDTHxHEIGHT.",
    )
    demo_ss.add_argument(
        "--no-sound",
        action="store_true",
        help="Disable per-trial soundtrack playback.",
    )
    demo_ss.add_argument(
        "--trial-limit",
        type=int,
        default=None,
        help="Limit the number of SS trials for demos.",
    )
    demo_ss.add_argument(
        "--debug-render",
        action="store_true",
        help="Print SS rendering diagnostics.",
    )

    run_ss = subparsers.add_parser(
        "run-ss",
        help="Run Static Social Scenes as an acquisition session.",
    )
    _add_run_presentation_arguments(
        run_ss,
        no_sound_help="Disable per-trial soundtrack playback.",
        trial_limit_help="Limit the number of SS trials.",
        debug_help="Print SS rendering diagnostics.",
    )

    demo_plr = subparsers.add_parser(
        "demo-plr",
        help="Run the bundled Pupillary Light Reflex sequence in PsychoPy.",
    )
    plr_display_mode = demo_plr.add_mutually_exclusive_group()
    plr_display_mode.add_argument(
        "--fullscreen",
        action="store_true",
        help="Run full screen.",
    )
    plr_display_mode.add_argument(
        "--windowed",
        action="store_false",
        dest="fullscreen",
        help="Run in a window. This is the default.",
    )
    demo_plr.set_defaults(fullscreen=False)
    _add_screen_argument(demo_plr)
    demo_plr.add_argument(
        "--size",
        default="1024x768",
        help="Window size for --windowed mode, formatted as WIDTHxHEIGHT.",
    )
    demo_plr.add_argument(
        "--no-sound",
        action="store_true",
        help="Disable movie audio playback.",
    )
    demo_plr.add_argument(
        "--trial-limit",
        type=int,
        default=None,
        help="Limit the number of PLR trials for demos.",
    )
    demo_plr.add_argument(
        "--attention-cue-seconds",
        type=float,
        default=1.0,
        help="Seconds to show the inter-trial attention cue. Use 0 to disable.",
    )
    demo_plr.add_argument(
        "--debug-render",
        action="store_true",
        help="Print PLR rendering diagnostics.",
    )

    run_plr = subparsers.add_parser(
        "run-plr",
        help="Run Pupillary Light Reflex as an acquisition session.",
    )
    _add_run_presentation_arguments(
        run_plr,
        no_sound_help="Disable movie audio playback.",
        trial_limit_help="Limit the number of PLR trials.",
        debug_help="Print PLR rendering diagnostics.",
    )
    run_plr.add_argument(
        "--attention-cue-seconds",
        type=float,
        default=1.0,
        help="Seconds to show the inter-trial attention cue. Use 0 to disable.",
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
    demo_calibration_runner: DemoCalibrationRunner | None = None,
    calibrate_eyetracker_runner: CalibrateEyeTrackerRunner | None = None,
    demo_activity_monitoring_runner: DemoActivityMonitoringRunner | None = None,
    demo_social_interactive_runner: DemoSocialInteractiveRunner | None = None,
    demo_static_social_scenes_runner: DemoStaticSocialScenesRunner | None = None,
    demo_pupillary_light_reflex_runner: DemoPupillaryLightReflexRunner | None = None,
    check_eyetracker_runner: CheckEyeTrackerRunner | None = None,
    run_activity_monitoring_runner: RunActivityMonitoringRunner | None = None,
    run_static_social_scenes_runner: RunStaticSocialScenesRunner | None = None,
    run_pupillary_light_reflex_runner: RunPupillaryLightReflexRunner | None = None,
) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "list-tasks":
        for task in BATTERY_ORDER:
            print(task.task_id)
        return 0

    if args.command == "check-eyetracker":
        runner = check_eyetracker_runner
        if runner is None:
            from aria_et.eyetracker import check_eyetracker

            runner = check_eyetracker

        return runner(address=args.address)

    if args.command == "calibrate-eyetracker":
        runner = calibrate_eyetracker_runner
        if runner is None:
            from aria_et.eyetracker import run_eyetracker_manager_calibration

            runner = run_eyetracker_manager_calibration

        kwargs = {
            "address": args.address,
            "serial_number": args.serial_number,
            "screen": args.screen,
            "calibration_output_dir": args.output,
        }
        if args.manager is not None:
            kwargs["executable"] = args.manager

        return runner(**kwargs)

    if args.command == "demo-calibration":
        runner = demo_calibration_runner
        if runner is None:
            from aria_et.psychopy.calibration import (
                run_gap_overlap_reward_calibration_demo,
            )

            runner = run_gap_overlap_reward_calibration_demo

        return runner(
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            play_sound=not args.no_sound,
            point_duration_seconds=args.point_duration,
            advance_on_space=args.advance_on_space,
            debug_render=args.debug_render,
        )

    if args.command == "demo-am":
        runner = demo_activity_monitoring_runner
        if runner is None:
            from aria_et.psychopy.activity_monitoring import run_activity_monitoring_demo

            runner = run_activity_monitoring_demo

        return runner(
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    if args.command == "run-am":
        runner = run_activity_monitoring_runner
        if runner is None:
            from aria_et.psychopy.activity_monitoring import (
                run_activity_monitoring_session,
            )

            runner = run_activity_monitoring_session

        return runner(
            tracker=args.tracker,
            tracker_address=args.address,
            output_dir=args.output,
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    if args.command == "demo-si":
        runner = demo_social_interactive_runner
        if runner is None:
            from aria_et.psychopy.social_interactive import run_social_interactive_demo

            runner = run_social_interactive_demo

        return runner(
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    if args.command == "demo-ss":
        runner = demo_static_social_scenes_runner
        if runner is None:
            from aria_et.psychopy.static_social_scenes import run_static_social_scenes_demo

            runner = run_static_social_scenes_demo

        return runner(
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    if args.command == "run-ss":
        runner = run_static_social_scenes_runner
        if runner is None:
            from aria_et.psychopy.static_social_scenes import (
                run_static_social_scenes_session,
            )

            runner = run_static_social_scenes_session

        return runner(
            tracker=args.tracker,
            tracker_address=args.address,
            output_dir=args.output,
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    if args.command == "demo-plr":
        runner = demo_pupillary_light_reflex_runner
        if runner is None:
            from aria_et.psychopy.pupillary_light_reflex import (
                run_pupillary_light_reflex_demo,
            )

            runner = run_pupillary_light_reflex_demo

        return runner(
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            inter_trial_attention_seconds=args.attention_cue_seconds,
            debug_render=args.debug_render,
        )

    if args.command == "run-plr":
        runner = run_pupillary_light_reflex_runner
        if runner is None:
            from aria_et.psychopy.pupillary_light_reflex import (
                run_pupillary_light_reflex_session,
            )

            runner = run_pupillary_light_reflex_session

        return runner(
            tracker=args.tracker,
            tracker_address=args.address,
            output_dir=args.output,
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            inter_trial_attention_seconds=args.attention_cue_seconds,
            debug_render=args.debug_render,
        )

    raise ValueError(f"Unsupported command: {args.command}")


def _add_run_presentation_arguments(
    parser: argparse.ArgumentParser,
    *,
    no_sound_help: str,
    trial_limit_help: str,
    debug_help: str,
) -> None:
    parser.add_argument(
        "--tracker",
        choices=("tobii", "none"),
        default="tobii",
        help="Eye tracker backend for the session.",
    )
    parser.add_argument(
        "--address",
        default=None,
        help="Optional Tobii tracker URI to connect to directly, bypassing discovery.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Directory where session artifacts will be written.",
    )
    display_mode = parser.add_mutually_exclusive_group()
    display_mode.add_argument(
        "--fullscreen",
        action="store_true",
        help="Run full screen.",
    )
    display_mode.add_argument(
        "--windowed",
        action="store_false",
        dest="fullscreen",
        help="Run in a window.",
    )
    parser.set_defaults(fullscreen=True)
    _add_screen_argument(parser)
    parser.add_argument(
        "--size",
        default="1024x768",
        help="Window size for --windowed mode, formatted as WIDTHxHEIGHT.",
    )
    parser.add_argument(
        "--no-sound",
        action="store_true",
        help=no_sound_help,
    )
    parser.add_argument(
        "--trial-limit",
        type=int,
        default=None,
        help=trial_limit_help,
    )
    parser.add_argument(
        "--debug-render",
        action="store_true",
        help=debug_help,
    )


def _add_screen_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--screen",
        type=int,
        default=DEFAULT_PSYCHOPY_SCREEN,
        help=(
            "PsychoPy display index. Default 1 targets the EIZO stimulus "
            "display in the lab setup."
        ),
    )


def parse_window_size(value: str) -> tuple[int, int]:
    try:
        width, height = value.lower().split("x", maxsplit=1)
        return int(width), int(height)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Expected size formatted as WIDTHxHEIGHT: {value}"
        ) from error


if __name__ == "__main__":
    sys.exit(main())
