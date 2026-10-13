"""Child-friendly calibration through DeToX.

DeToX (``dvst-detox``) provides the positioning screen and the infant-friendly
calibration procedure: animated targets, operator-driven collection, a results
view, and re-collection of individual points. aria-et resolves the tracker,
opens the PsychoPy window on the configured stimulus display, and saves the
applied calibration so runs can record which calibration was in effect.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from pathlib import Path

from aria_et.calibration import (
    DEFAULT_ANIMATION,
    DEFAULT_CALIBRATION_POINTS,
    DEFAULT_SHOW_POSITIONING,
    DEFAULT_SHUFFLE_POINTS,
    RESULTS_VISUALIZATION_STYLE,
)

StatusSink = Callable[[str], None]
ImportModule = Callable[[str], object]

CALIBRATION_METHOD = "child-friendly-detox"


def run_child_friendly_eyetracker_calibration(
    *,
    address: str | None = None,
    serial_number: str | None = None,
    screen: int = 1,
    calibration_output_dir: str | Path = "calibrations",
    fullscreen: bool = True,
    window_size: tuple[int, int] = (1024, 768),
    screen_distance_meters: float = 0.65,
    screen_resolution_pixels: tuple[int, int] = (1920, 1080),
    screen_size_meters: tuple[float, float] = (0.527, 0.296),
    monitor_name: str = "EIZO_EV2480",
    audio_speaker: str | None = None,
    play_sound: bool = True,
    calibration_points: int = DEFAULT_CALIBRATION_POINTS,
    shuffle: bool = DEFAULT_SHUFFLE_POINTS,
    animation: str = DEFAULT_ANIMATION,
    show_positioning: bool = DEFAULT_SHOW_POSITIONING,
    import_module: ImportModule = importlib.import_module,
    status_sink: StatusSink | None = None,
    error_sink: StatusSink | None = None,
) -> int:
    from aria_et.eyetracker import (
        TobiiSdkUnavailableError,
        TobiiTrackerUnavailableError,
        _open_tracker_after_calibration,
        load_tobii_research,
        save_current_calibration,
    )

    status = status_sink or (
        lambda message: print(message, file=sys.stderr, flush=True)
    )
    error = error_sink or (lambda message: print(message, file=sys.stderr))

    if address is not None and serial_number is not None:
        error("Use either --address or --serial-number, not both.")
        return 51

    try:
        tobii_research = load_tobii_research(import_module=import_module)
        eyetracker = _open_tracker_after_calibration(
            address=address,
            serial_number=serial_number,
            import_module=import_module,
        )
        # DeToX selects its tracker by position in Tobii's discovery list.
        tracker_index = _discovery_index(tobii_research, eyetracker)
    except TobiiSdkUnavailableError as error_message:
        error(str(error_message))
        return 2
    except TobiiTrackerUnavailableError as error_message:
        error(str(error_message))
        return 3

    detox = import_module("DeToX")
    window = _open_calibration_window(
        status=status,
        fullscreen=fullscreen,
        screen=screen,
        window_size=window_size,
        screen_distance_meters=screen_distance_meters,
        screen_resolution_pixels=screen_resolution_pixels,
        screen_size_meters=screen_size_meters,
        monitor_name=monitor_name,
        audio_speaker=audio_speaker,
    )
    try:
        controller = detox.ETracker(window, etracker_id=tracker_index)
        if controller.eyetracker.serial_number != eyetracker.serial_number:
            error(
                "DeToX connected to tracker "
                f"{controller.eyetracker.serial_number}, expected "
                f"{eyetracker.serial_number}."
            )
            return 3
        succeeded = _run_detox_calibration(
            controller,
            status=status,
            play_sound=play_sound,
            calibration_points=calibration_points,
            shuffle=shuffle,
            animation=animation,
            show_positioning=show_positioning,
        )
    finally:
        status("Closing PsychoPy window...")
        window.close()

    if not succeeded:
        error("Calibration was aborted or did not succeed; nothing was saved.")
        return 31

    try:
        artifact_dir = save_current_calibration(
            eyetracker=eyetracker,
            output_dir=calibration_output_dir,
            method=CALIBRATION_METHOD,
            screen=screen,
        )
    except OSError as error_message:
        error(
            f"Calibration completed, but saving calibration data failed: {error_message}"
        )
        return 4

    status(f"Saved calibration data to {artifact_dir}.")
    return 0


def run_child_friendly_calibration_demo(
    *,
    fullscreen: bool = True,
    screen: int = 1,
    window_size: tuple[int, int] = (1024, 768),
    screen_distance_meters: float = 0.65,
    screen_resolution_pixels: tuple[int, int] = (1920, 1080),
    screen_size_meters: tuple[float, float] = (0.527, 0.296),
    monitor_name: str = "EIZO_EV2480",
    audio_speaker: str | None = None,
    play_sound: bool = True,
    calibration_points: int = DEFAULT_CALIBRATION_POINTS,
    shuffle: bool = DEFAULT_SHUFFLE_POINTS,
    animation: str = DEFAULT_ANIMATION,
    show_positioning: bool = DEFAULT_SHOW_POSITIONING,
    import_module: ImportModule = importlib.import_module,
    status_sink: StatusSink | None = None,
) -> int:
    """Preview the calibration without a tracker; the mouse stands in for gaze."""
    status = status_sink or (
        lambda message: print(message, file=sys.stderr, flush=True)
    )
    detox = import_module("DeToX")
    window = _open_calibration_window(
        status=status,
        fullscreen=fullscreen,
        screen=screen,
        window_size=window_size,
        screen_distance_meters=screen_distance_meters,
        screen_resolution_pixels=screen_resolution_pixels,
        screen_size_meters=screen_size_meters,
        monitor_name=monitor_name,
        audio_speaker=audio_speaker,
    )
    try:
        controller = detox.ETracker(window, simulate=True)
        _run_detox_calibration(
            controller,
            status=status,
            play_sound=play_sound,
            calibration_points=calibration_points,
            shuffle=shuffle,
            animation=animation,
            show_positioning=show_positioning,
        )
        status("Calibration demo finished.")
    finally:
        status("Closing PsychoPy window...")
        window.close()
    return 0


def _run_detox_calibration(
    controller,
    *,
    status: StatusSink,
    play_sound: bool,
    calibration_points: int,
    shuffle: bool,
    animation: str,
    show_positioning: bool,
) -> bool:
    if show_positioning:
        status("Positioning: adjust the child, then press Space to continue.")
        controller.show_status()
    status(
        f"Running DeToX calibration ({calibration_points} points). Number keys "
        "select a point, Space collects, Enter shows results, Escape aborts."
    )
    return bool(
        controller.calibrate(
            calibration_points=calibration_points,
            shuffle=shuffle,
            audio=play_sound,
            anim_type=animation,
            visualization_style=RESULTS_VISUALIZATION_STYLE,
        )
    )


def _discovery_index(tobii_research, eyetracker) -> int:
    from aria_et.eyetracker import TobiiTrackerUnavailableError

    for index, candidate in enumerate(tobii_research.find_all_eyetrackers()):
        if candidate.serial_number == eyetracker.serial_number:
            return index
    raise TobiiTrackerUnavailableError(
        f"Tracker {eyetracker.serial_number} is not visible to discovery, which "
        "DeToX needs to connect to it."
    )


def _open_calibration_window(*, status: StatusSink, **window_options):
    status("Importing PsychoPy...")
    from psychopy import monitors, prefs, visual

    from aria_et.psychopy.environment import effective_window_size, open_window

    effective_size = effective_window_size(
        fullscreen=window_options["fullscreen"],
        window_size=window_options["window_size"],
        screen_resolution_pixels=window_options["screen_resolution_pixels"],
    )
    status(
        "Opening PsychoPy window "
        f"({effective_size[0]}x{effective_size[1]}, "
        f"fullscreen={window_options['fullscreen']}, "
        f"screen={window_options['screen']})..."
    )
    return open_window(
        visual_module=visual,
        monitors_module=monitors,
        prefs_module=prefs,
        **window_options,
    )
