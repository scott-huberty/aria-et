"""Command line entry points for ARIA eye-tracking tasks."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from aria_et.config import (
    AriaEtConfig,
    default_config_path,
    default_config_text,
    load_config,
)
from aria_et.tasks import BATTERY_ORDER


DemoCalibrationRunner = Callable[..., int]
CalibrateEyeTrackerRunner = Callable[..., int]
ChildFriendlyCalibrationRunner = Callable[..., int]
DemoActivityMonitoringRunner = Callable[..., int]
DemoSocialInteractiveRunner = Callable[..., int]
DemoStaticSocialScenesRunner = Callable[..., int]
DemoPupillaryLightReflexRunner = Callable[..., int]
CheckEyeTrackerRunner = Callable[..., int]
RunActivityMonitoringRunner = Callable[..., int]
RunSocialInteractiveRunner = Callable[..., int]
RunStaticSocialScenesRunner = Callable[..., int]
RunPupillaryLightReflexRunner = Callable[..., int]
ExportBidsRunner = Callable[..., object]


def build_parser(config: AriaEtConfig | None = None) -> argparse.ArgumentParser:
    config = config or load_config()
    parser = argparse.ArgumentParser(prog="aria-et")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "list-tasks",
        help="Print the configured battery order.",
    )

    init_config = subparsers.add_parser(
        "init-config",
        help="Create a user ARIA-ET config file with lab display/audio defaults.",
    )
    init_config.add_argument(
        "--path",
        default=None,
        help=f"Config file path to write. Defaults to {default_config_path()}.",
    )
    init_config.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing config file.",
    )

    export_bids = subparsers.add_parser(
        "export-bids",
        help="Export an ARIA acquisition run directory to BIDS eyetracking files.",
    )
    export_bids.add_argument(
        "--input",
        "--run-dir",
        dest="run_dir",
        required=True,
        help="ARIA run directory containing session.json, events.jsonl, and gaze.jsonl.",
    )
    export_bids.add_argument(
        "--output",
        "--bids-root",
        dest="bids_root",
        default=None,
        help=f"BIDS dataset root directory to write. Defaults to {config.data_root / 'bids'}.",
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
        "--routine",
        choices=("etm", "child-friendly"),
        default="etm",
        help="Calibration routine to run. Defaults to Tobii Pro Eye Tracker Manager.",
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
        default=None,
        help=(
            "Display index for calibration. Defaults to the configured ETM "
            "screen for --routine etm and PsychoPy screen for --routine child-friendly."
        ),
    )
    calibrate_eyetracker.add_argument(
        "--manager",
        default=config.eye_tracker_manager,
        help="Path to Tobii Pro Eye Tracker Manager executable.",
    )
    calibrate_eyetracker.add_argument(
        "--output",
        "--output-dir",
        dest="output",
        default=None,
        help=(
            "Root directory where calibration artifacts will be written. "
            f"Defaults to {config.data_root / 'sourcedata'}."
        ),
    )
    calibrate_eyetracker.add_argument(
        "--subject",
        required=True,
        help="BIDS subject label without the sub- prefix.",
    )
    calibrate_eyetracker.add_argument(
        "--session",
        required=True,
        help="BIDS session label without the ses- prefix.",
    )
    calibrate_display_mode = calibrate_eyetracker.add_mutually_exclusive_group()
    calibrate_display_mode.add_argument(
        "--fullscreen",
        action="store_true",
        help="Run child-friendly calibration full screen.",
    )
    calibrate_display_mode.add_argument(
        "--windowed",
        action="store_false",
        dest="fullscreen",
        help="Run child-friendly calibration in a window.",
    )
    calibrate_eyetracker.set_defaults(fullscreen=True)
    calibrate_eyetracker.add_argument(
        "--size",
        default="1024x768",
        help="Window size for child-friendly --windowed mode, formatted as WIDTHxHEIGHT.",
    )
    calibrate_eyetracker.add_argument(
        "--no-sound",
        action="store_true",
        help="Disable child-friendly calibration sound playback.",
    )
    calibrate_eyetracker.add_argument(
        "--point-duration",
        type=float,
        default=3.0,
        help="Seconds to display each child-friendly calibration point.",
    )
    calibrate_eyetracker.add_argument(
        "--advance-on-space",
        action="store_true",
        help="Wait for Space before moving to the next child-friendly calibration point.",
    )
    calibrate_eyetracker.add_argument(
        "--debug-render",
        action="store_true",
        help="Print child-friendly calibration rendering diagnostics.",
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
        default=config.psychopy_screen,
        help=(
            "PsychoPy display index. Defaults to the configured EIZO "
            "stimulus display."
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
    _add_screen_argument(demo_am, config)
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
        config,
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
    _add_screen_argument(demo_si, config)
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

    run_si = subparsers.add_parser(
        "run-si",
        help="Run Social Interactive as an acquisition session.",
    )
    _add_run_presentation_arguments(
        run_si,
        config,
        no_sound_help="Disable movie audio playback.",
        trial_limit_help="Limit the number of SI trials.",
        debug_help="Print SI rendering diagnostics.",
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
    _add_screen_argument(demo_ss, config)
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
        config,
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
    _add_screen_argument(demo_plr, config)
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

    run_plr = subparsers.add_parser(
        "run-plr",
        help="Run Pupillary Light Reflex as an acquisition session.",
    )
    _add_run_presentation_arguments(
        run_plr,
        config,
        no_sound_help="Disable movie audio playback.",
        trial_limit_help="Limit the number of PLR trials.",
        debug_help="Print PLR rendering diagnostics.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    demo_calibration_runner: DemoCalibrationRunner | None = None,
    calibrate_eyetracker_runner: CalibrateEyeTrackerRunner | None = None,
    child_friendly_calibration_runner: ChildFriendlyCalibrationRunner | None = None,
    demo_activity_monitoring_runner: DemoActivityMonitoringRunner | None = None,
    demo_social_interactive_runner: DemoSocialInteractiveRunner | None = None,
    demo_static_social_scenes_runner: DemoStaticSocialScenesRunner | None = None,
    demo_pupillary_light_reflex_runner: DemoPupillaryLightReflexRunner | None = None,
    check_eyetracker_runner: CheckEyeTrackerRunner | None = None,
    run_activity_monitoring_runner: RunActivityMonitoringRunner | None = None,
    run_social_interactive_runner: RunSocialInteractiveRunner | None = None,
    run_static_social_scenes_runner: RunStaticSocialScenesRunner | None = None,
    run_pupillary_light_reflex_runner: RunPupillaryLightReflexRunner | None = None,
    export_bids_runner: ExportBidsRunner | None = None,
) -> int:
    config = load_config()
    args = build_parser(config).parse_args(argv)

    if args.command == "list-tasks":
        for task in BATTERY_ORDER:
            print(task.task_id)
        return 0

    if args.command == "init-config":
        return init_config_file(path=args.path, force=args.force)

    if args.command == "export-bids":
        runner = export_bids_runner
        if runner is None:
            from aria_et.bids import export_run_to_bids

            runner = export_run_to_bids

        result = runner(
            run_dir=args.run_dir,
            bids_root=args.bids_root or default_bids_root(config),
        )
        written_files = getattr(result, "written_files", ())
        print(f"Exported BIDS eyetracking files to {result.bids_root}.")
        for path in written_files:
            print(path)
        return 0

    if args.command == "check-eyetracker":
        runner = check_eyetracker_runner
        if runner is None:
            from aria_et.eyetracker import check_eyetracker

            runner = check_eyetracker

        return runner(address=args.address)

    if args.command == "calibrate-eyetracker":
        calibration_output_dir = calibration_artifact_root(
            output_dir=args.output or default_sourcedata_root(config),
            subject=args.subject,
            session=args.session,
        )
        if args.routine == "child-friendly":
            warn_if_config_missing()
            runner = child_friendly_calibration_runner
            if runner is None:
                from aria_et.psychopy.calibration import (
                    run_child_friendly_eyetracker_calibration,
                )

                runner = run_child_friendly_eyetracker_calibration

            return runner(
                address=args.address,
                serial_number=args.serial_number,
                screen=args.screen if args.screen is not None else config.psychopy_screen,
                calibration_output_dir=calibration_output_dir,
                fullscreen=args.fullscreen,
                window_size=parse_window_size(args.size),
                screen_distance_meters=config.screen_distance_meters,
                screen_resolution_pixels=parse_window_size(config.screen_resolution),
                screen_size_meters=parse_float_pair(config.screen_size_meters),
                monitor_name=config.monitor_name,
                audio_speaker=config.audio_speaker,
                play_sound=not args.no_sound,
                point_duration_seconds=args.point_duration,
                advance_on_space=args.advance_on_space,
                debug_render=args.debug_render,
            )

        runner = calibrate_eyetracker_runner
        if runner is None:
            from aria_et.eyetracker import run_eyetracker_manager_calibration

            runner = run_eyetracker_manager_calibration

        kwargs = {
            "address": args.address,
            "serial_number": args.serial_number,
            "screen": args.screen if args.screen is not None else config.etm_screen,
            "calibration_output_dir": calibration_output_dir,
        }
        if args.manager is not None:
            kwargs["executable"] = args.manager

        return runner(**kwargs)

    if args.command == "demo-calibration":
        warn_if_config_missing()
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
            screen_distance_meters=config.screen_distance_meters,
            screen_resolution_pixels=parse_window_size(config.screen_resolution),
            screen_size_meters=parse_float_pair(config.screen_size_meters),
            monitor_name=config.monitor_name,
            audio_speaker=config.audio_speaker,
            play_sound=not args.no_sound,
            point_duration_seconds=args.point_duration,
            advance_on_space=args.advance_on_space,
            debug_render=args.debug_render,
        )

    if args.command == "demo-am":
        warn_if_config_missing()
        runner = demo_activity_monitoring_runner
        if runner is None:
            from aria_et.psychopy.activity_monitoring import run_activity_monitoring_demo

            runner = run_activity_monitoring_demo

        return runner(
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            screen_distance_meters=config.screen_distance_meters,
            screen_resolution_pixels=parse_window_size(config.screen_resolution),
            screen_size_meters=parse_float_pair(config.screen_size_meters),
            monitor_name=config.monitor_name,
            audio_speaker=config.audio_speaker,
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    if args.command == "run-am":
        warn_if_config_missing()
        runner = run_activity_monitoring_runner
        if runner is None:
            from aria_et.psychopy.activity_monitoring import (
                run_activity_monitoring_session,
            )

            runner = run_activity_monitoring_session

        return runner(
            tracker=args.tracker,
            tracker_address=args.address,
            output_dir=args.output or default_sourcedata_root(config),
            subject=args.subject,
            session=args.session,
            run=args.run,
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            screen_distance_meters=args.screen_distance_meters,
            screen_resolution_pixels=parse_window_size(args.screen_resolution),
            screen_size_meters=parse_float_pair(args.screen_size_meters),
            monitor_name=config.monitor_name,
            audio_speaker=config.audio_speaker,
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    if args.command == "demo-si":
        warn_if_config_missing()
        runner = demo_social_interactive_runner
        if runner is None:
            from aria_et.psychopy.social_interactive import run_social_interactive_demo

            runner = run_social_interactive_demo

        return runner(
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            screen_distance_meters=config.screen_distance_meters,
            screen_resolution_pixels=parse_window_size(config.screen_resolution),
            screen_size_meters=parse_float_pair(config.screen_size_meters),
            monitor_name=config.monitor_name,
            audio_speaker=config.audio_speaker,
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    if args.command == "run-si":
        warn_if_config_missing()
        runner = run_social_interactive_runner
        if runner is None:
            from aria_et.psychopy.social_interactive import (
                run_social_interactive_session,
            )

            runner = run_social_interactive_session

        return runner(
            tracker=args.tracker,
            tracker_address=args.address,
            output_dir=args.output or default_sourcedata_root(config),
            subject=args.subject,
            session=args.session,
            run=args.run,
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            screen_distance_meters=args.screen_distance_meters,
            screen_resolution_pixels=parse_window_size(args.screen_resolution),
            screen_size_meters=parse_float_pair(args.screen_size_meters),
            monitor_name=config.monitor_name,
            audio_speaker=config.audio_speaker,
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    if args.command == "demo-ss":
        warn_if_config_missing()
        runner = demo_static_social_scenes_runner
        if runner is None:
            from aria_et.psychopy.static_social_scenes import run_static_social_scenes_demo

            runner = run_static_social_scenes_demo

        return runner(
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            screen_distance_meters=config.screen_distance_meters,
            screen_resolution_pixels=parse_window_size(config.screen_resolution),
            screen_size_meters=parse_float_pair(config.screen_size_meters),
            monitor_name=config.monitor_name,
            audio_speaker=config.audio_speaker,
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    if args.command == "run-ss":
        warn_if_config_missing()
        runner = run_static_social_scenes_runner
        if runner is None:
            from aria_et.psychopy.static_social_scenes import (
                run_static_social_scenes_session,
            )

            runner = run_static_social_scenes_session

        return runner(
            tracker=args.tracker,
            tracker_address=args.address,
            output_dir=args.output or default_sourcedata_root(config),
            subject=args.subject,
            session=args.session,
            run=args.run,
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            screen_distance_meters=args.screen_distance_meters,
            screen_resolution_pixels=parse_window_size(args.screen_resolution),
            screen_size_meters=parse_float_pair(args.screen_size_meters),
            monitor_name=config.monitor_name,
            audio_speaker=config.audio_speaker,
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    if args.command == "demo-plr":
        warn_if_config_missing()
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
            screen_distance_meters=config.screen_distance_meters,
            screen_resolution_pixels=parse_window_size(config.screen_resolution),
            screen_size_meters=parse_float_pair(config.screen_size_meters),
            monitor_name=config.monitor_name,
            audio_speaker=config.audio_speaker,
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    if args.command == "run-plr":
        warn_if_config_missing()
        runner = run_pupillary_light_reflex_runner
        if runner is None:
            from aria_et.psychopy.pupillary_light_reflex import (
                run_pupillary_light_reflex_session,
            )

            runner = run_pupillary_light_reflex_session

        return runner(
            tracker=args.tracker,
            tracker_address=args.address,
            output_dir=args.output or default_sourcedata_root(config),
            subject=args.subject,
            session=args.session,
            run=args.run,
            fullscreen=args.fullscreen,
            screen=args.screen,
            window_size=parse_window_size(args.size),
            screen_distance_meters=args.screen_distance_meters,
            screen_resolution_pixels=parse_window_size(args.screen_resolution),
            screen_size_meters=parse_float_pair(args.screen_size_meters),
            monitor_name=config.monitor_name,
            audio_speaker=config.audio_speaker,
            play_sound=not args.no_sound,
            trial_limit=args.trial_limit,
            debug_render=args.debug_render,
        )

    raise ValueError(f"Unsupported command: {args.command}")


def _add_run_presentation_arguments(
    parser: argparse.ArgumentParser,
    config: AriaEtConfig,
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
        "--output-dir",
        dest="output",
        default=None,
        help=(
            "Root directory where session artifacts will be written. "
            f"Defaults to {config.data_root / 'sourcedata'}."
        ),
    )
    parser.add_argument(
        "--subject",
        required=True,
        help="BIDS subject label without the sub- prefix.",
    )
    parser.add_argument(
        "--session",
        default=None,
        help="Optional BIDS session label without the ses- prefix.",
    )
    parser.add_argument(
        "--run",
        default=None,
        help="Optional BIDS run label without the run- prefix. Defaults to the next available run.",
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
    _add_screen_argument(parser, config)
    parser.add_argument(
        "--size",
        default="1024x768",
        help="Window size for --windowed mode, formatted as WIDTHxHEIGHT.",
    )
    parser.add_argument(
        "--screen-distance-meters",
        type=float,
        default=config.screen_distance_meters,
        help="Participant eye-to-screen distance in meters for BIDS metadata.",
    )
    parser.add_argument(
        "--screen-resolution",
        default=config.screen_resolution,
        help="Stimulus screen resolution in pixels, formatted as WIDTHxHEIGHT.",
    )
    parser.add_argument(
        "--screen-size-meters",
        default=config.screen_size_meters,
        help="Stimulus screen physical size in meters, formatted as WIDTHxHEIGHT.",
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


def default_data_root(config: AriaEtConfig | None = None) -> Path:
    return (config or load_config()).data_root


def default_sourcedata_root(config: AriaEtConfig | None = None) -> Path:
    return default_data_root(config) / "sourcedata"


def default_bids_root(config: AriaEtConfig | None = None) -> Path:
    return default_data_root(config) / "bids"


def calibration_artifact_root(
    *,
    output_dir: str | Path,
    subject: str,
    session: str,
) -> Path:
    from aria_et.session import bids_subject_session_dir

    return (
        bids_subject_session_dir(output_dir, subject=subject, session=session)
        / "calibrations"
    )


def init_config_file(path: str | Path | None = None, *, force: bool = False) -> int:
    config_path = Path(path).expanduser() if path is not None else default_config_path()
    if config_path.exists() and not force:
        print(
            f"ARIA-ET config already exists at {config_path}. "
            "Use --force to overwrite it.",
            file=sys.stderr,
        )
        return 1

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(default_config_text(), encoding="utf-8")
    print(f"Wrote ARIA-ET config to {config_path}.")
    return 0


def warn_if_config_missing(path: str | Path | None = None) -> None:
    config_path = Path(path).expanduser() if path is not None else default_config_path()
    if config_path.exists():
        return
    print(
        f"No ARIA-ET config found at {config_path}. Using built-in EIZO defaults. "
        "Run `aria-et init-config` to persist lab display/audio settings.",
        file=sys.stderr,
    )


def _add_screen_argument(parser: argparse.ArgumentParser, config: AriaEtConfig) -> None:
    parser.add_argument(
        "--screen",
        type=int,
        default=config.psychopy_screen,
        help=(
            "PsychoPy display index. Defaults to the configured EIZO "
            "stimulus display."
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


def parse_float_pair(value: str) -> tuple[float, float]:
    try:
        width, height = value.lower().split("x", maxsplit=1)
        return float(width), float(height)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Expected pair formatted as WIDTHxHEIGHT: {value}"
        ) from error


if __name__ == "__main__":
    sys.exit(main())
