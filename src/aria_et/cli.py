"""Command line entry points for ARIA eye-tracking tasks."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from aria_et.tasks import BATTERY_ORDER


DemoCalibrationRunner = Callable[..., int]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aria-et")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "list-tasks",
        help="Print the configured battery order.",
    )

    demo_calibration = subparsers.add_parser(
        "demo-calibration",
        help="Run the bundled Pikachu calibration sequence in PsychoPy.",
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

    return parser


def main(
    argv: Sequence[str] | None = None,
    demo_calibration_runner: DemoCalibrationRunner | None = None,
) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "list-tasks":
        for task in BATTERY_ORDER:
            print(task.task_id)
        return 0

    if args.command == "demo-calibration":
        runner = demo_calibration_runner
        if runner is None:
            from aria_et.psychopy.calibration import run_pikachu_calibration_demo

            runner = run_pikachu_calibration_demo

        return runner(
            fullscreen=args.fullscreen,
            window_size=parse_window_size(args.size),
            play_sound=not args.no_sound,
            point_duration_seconds=args.point_duration,
            advance_on_space=args.advance_on_space,
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
