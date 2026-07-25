"""Command line entry points for ARIA eye-tracking tasks."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from aria_et.tasks import BATTERY_ORDER


DemoCalibrationRunner = Callable[..., int]
DemoActivityMonitoringRunner = Callable[..., int]
DemoSocialInteractiveRunner = Callable[..., int]
DemoStaticSocialScenesRunner = Callable[..., int]
DemoPupillaryLightReflexRunner = Callable[..., int]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aria-et")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "list-tasks",
        help="Print the configured battery order.",
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
        help="Run in a window. This is the default.",
    )
    demo_calibration.set_defaults(fullscreen=False)
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
        default=1.0,
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
        "--debug-render",
        action="store_true",
        help="Print PLR rendering diagnostics.",
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
    demo_calibration_runner: DemoCalibrationRunner | None = None,
    demo_activity_monitoring_runner: DemoActivityMonitoringRunner | None = None,
    demo_social_interactive_runner: DemoSocialInteractiveRunner | None = None,
    demo_static_social_scenes_runner: DemoStaticSocialScenesRunner | None = None,
    demo_pupillary_light_reflex_runner: DemoPupillaryLightReflexRunner | None = None,
) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "list-tasks":
        for task in BATTERY_ORDER:
            print(task.task_id)
        return 0

    if args.command == "demo-calibration":
        runner = demo_calibration_runner
        if runner is None:
            from aria_et.psychopy.calibration import (
                run_gap_overlap_reward_calibration_demo,
            )

            runner = run_gap_overlap_reward_calibration_demo

        return runner(
            fullscreen=args.fullscreen,
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
            window_size=parse_window_size(args.size),
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    raise ValueError(f"Unsupported command: {args.command}")


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
