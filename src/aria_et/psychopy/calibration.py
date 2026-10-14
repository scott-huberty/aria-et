"""Child-friendly calibration through DeToX, followed by a validation step.

DeToX (``dvst-detox``) provides the positioning screen and the infant-friendly
calibration procedure: animated targets, operator-driven collection, a results
view, and re-collection of individual points. aria-et resolves the tracker,
opens the PsychoPy window on the configured stimulus display, runs a
Titta-style validation after the calibration is accepted, and saves the applied
calibration with its quality so runs can record which calibration was in effect.
"""

from __future__ import annotations

import importlib
import math
import random
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from aria_et.calibration import (
    DEFAULT_ANIMATION,
    DEFAULT_CALIBRATION_POINTS,
    DEFAULT_SHOW_POSITIONING,
    DEFAULT_SHUFFLE_POINTS,
    DEFAULT_VALIDATION_POINTS,
    DETOX_EYE_COLORS,
    RESULTS_VISUALIZATION_STYLE,
    VALIDATION_COLLECT_SECONDS,
)
from aria_et.calibration_quality import (
    EYES,
    PASS_MARK,
    adcs_to_ucs,
    describe_tolerance,
    gaze_on_display,
    point_quality,
    quality_table,
    summarize,
    tolerance_mark,
    tolerance_verdict,
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
    extra_metadata: dict[str, object] = {}
    try:
        controller = detox.ETracker(window, etracker_id=tracker_index)
        if controller.eyetracker.serial_number != eyetracker.serial_number:
            error(
                "DeToX connected to tracker "
                f"{controller.eyetracker.serial_number}, expected "
                f"{eyetracker.serial_number}."
            )
            return 3
        # DeToX discards the calibration result; keep it for the point positions.
        recorder = _RecordingCalibration(controller.calibration)
        controller.calibration = recorder
        succeeded = _calibrate_validate_review(
            window,
            controller=controller,
            recorder=recorder,
            eyetracker=eyetracker,
            tobii_research=tobii_research,
            detox=detox,
            import_module=import_module,
            status=status,
            play_sound=play_sound,
            calibration_points=calibration_points,
            shuffle=shuffle,
            animation=animation,
            show_positioning=show_positioning,
            extra_metadata=extra_metadata,
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
            extra_metadata=extra_metadata,
        )
    except OSError as error_message:
        error(
            f"Calibration completed, but saving calibration data failed: {error_message}"
        )
        return 4

    status(f"Saved calibration data to {artifact_dir}.")
    return 0


def _calibrate_validate_review(
    window,
    *,
    controller,
    recorder: _RecordingCalibration,
    eyetracker,
    tobii_research,
    detox,
    import_module: ImportModule,
    status: StatusSink,
    play_sound: bool,
    calibration_points: int,
    shuffle: bool,
    animation: str,
    show_positioning: bool,
    extra_metadata: dict[str, object],
) -> bool:
    """Calibrate, validate and show the results until the operator accepts.

    On the results screen the operator can accept, re-validate, or
    re-calibrate. The calibration is applied on the tracker as soon as DeToX
    accepts it, so whatever is accepted here is what gets saved. If a
    re-calibration is aborted, the previous calibration is still the active
    one, so its results are shown again. Returns False only if the first
    calibration never succeeded (nothing to save).
    """
    animation_settings = _detox_animation_settings(import_module)
    colors = _detox_colors(import_module)
    calibration_attempts = 0
    validation_attempts = 0
    shown = None  # (calibration point metadata, validation, gaze) on screen
    action = "recalibrate"
    while True:
        if action == "recalibrate":
            calibrated = _run_detox_calibration(
                controller,
                status=status,
                play_sound=play_sound,
                calibration_points=calibration_points,
                shuffle=shuffle,
                animation=animation,
                show_positioning=show_positioning,
            )
            if calibrated:
                calibration_attempts += 1
                point_metadata = recorder.point_metadata()
                action = "revalidate"
            elif shown is None:
                return False
            else:
                status(
                    "Re-calibration aborted; the previous calibration is still "
                    "active on the tracker."
                )
        if action == "revalidate":
            # Validate at the calibration's own positions, so both steps cover
            # the same area; fall back to DeToX's default layout if unknown.
            validation_points = [
                tuple(point) for point in point_metadata["positions_adcs"]
            ] or DEFAULT_VALIDATION_POINTS
            gaze: list[dict] = []
            validation = run_validation(
                window,
                eyetracker=eyetracker,
                tobii_research=tobii_research,
                stimulus_dir=_detox_stimulus_dir(detox),
                play_sound=play_sound,
                status=status,
                animation=animation,
                animation_settings=animation_settings,
                points=validation_points,
                gaze_out=gaze,
            )
            validation_attempts += 1
            status(describe_validation(validation))
            if validation.get("tolerance"):
                status(describe_tolerance(validation["tolerance"]))
            shown = (point_metadata, validation, gaze)
        point_metadata, validation, gaze = shown
        action = show_validation_results(
            window, validation=validation, gaze=gaze, colors=colors
        )
        if action == "accept":
            break
    extra_metadata.update(
        calibration_points=point_metadata,
        validation=validation,
        calibration_attempts=calibration_attempts,
        validation_attempts=validation_attempts,
    )
    return True


# Tolerance line colours on the results screen (rgb255): calm green / amber.
TOLERANCE_PASS_COLOR = (120, 200, 120)
TOLERANCE_FAIL_COLOR = (240, 170, 80)

# Footer on the results screen. Escape also accepts: the calibration is already
# active on the tracker, so it has to be recorded.
RESULTS_KEYS_HINT = "Space: accept      V: re-validate      C: re-calibrate"
_RESULTS_KEYS = {
    "space": "accept",
    "return": "accept",
    "escape": "accept",
    "v": "revalidate",
    "c": "recalibrate",
}


def show_validation_results(window, *, validation, gaze, colors) -> str:
    """Titta-style results: targets, gaze per eye, and the quality table.

    Waits for a key and returns "accept", "revalidate" or "recalibrate".
    """
    from psychopy import event, visual

    stimuli = _results_stimuli(window, visual, validation, gaze, colors)
    event.clearEvents()
    while True:
        for stimulus in stimuli:
            stimulus.draw()
        window.flip()
        for key in event.getKeys(keyList=list(_RESULTS_KEYS)):
            return _RESULTS_KEYS[key]


def _results_stimuli(window, visual, validation, gaze, colors) -> list:
    width, height = window.size

    def to_pix(point):
        return ((point[0] - 0.5) * width, (0.5 - point[1]) * height)

    def text(message, pos, *, color=(230, 230, 230), size=0.022):
        return visual.TextStim(
            window,
            text=message,
            pos=pos,
            height=size * height,
            color=color,
            colorSpace="rgb255",
            units="pix",
            # PsychoPy's default wrap width is narrower than the footer line.
            wrapWidth=0.9 * width,
        )

    stimuli = []
    # Gaze: one element array per eye, so thousands of dots draw quickly.
    for eye in EYES:
        positions = [to_pix(xy) for target in gaze for xy in target[eye]]
        if not positions:
            continue
        red, green, blue, alpha = colors[eye]
        stimuli.append(
            visual.ElementArrayStim(
                window,
                units="pix",
                nElements=len(positions),
                xys=positions,
                sizes=0.005 * height,
                elementTex=None,
                elementMask="circle",
                colors=(red, green, blue),
                colorSpace="rgb255",
                opacities=alpha / 255,
            )
        )

    # Target markers on top of the gaze: a hollow ring (dots stay visible
    # inside it) with a centre dot, so the target shows even under a cloud.
    for point in validation.get("points_adcs") or ():
        stimuli.append(
            visual.Circle(
                window,
                radius=0.02 * height,
                pos=to_pix(point),
                lineColor=(235, 235, 235),
                lineWidth=2,
                fillColor=None,
                colorSpace="rgb255",
                units="pix",
            )
        )
        stimuli.append(
            visual.Circle(
                window,
                radius=0.003 * height,
                pos=to_pix(point),
                fillColor=(235, 235, 235),
                lineColor=None,
                colorSpace="rgb255",
                units="pix",
            )
        )

    # Quality table, laid out like Titta's.
    summary = validation.get("summary")
    # Above the centre target (gaze clouds sit there) and inside the corner
    # targets, which are 10% in from each edge.
    top = 0.33 * height
    if summary:
        verdict = tolerance_verdict(summary)
        # Columns: metric label, then mean and worst for each eye.
        label_x = -0.26 * width
        value_x = {
            ("left", 0): -0.10 * width,
            ("left", 1): -0.02 * width,
            ("right", 0): 0.10 * width,
            ("right", 1): 0.18 * width,
        }
        row_step = 0.04 * height
        for eye in EYES:
            color = tuple(colors[eye][:3])
            centre = (value_x[(eye, 0)] + value_x[(eye, 1)]) / 2
            stimuli.append(text(f"{eye.capitalize()} eye", (centre, top), color=color))
            for column, heading in enumerate(("Mean", "Worst")):
                stimuli.append(
                    text(
                        heading,
                        (value_x[(eye, column)], top - row_step),
                        color=(170, 170, 170),
                        size=0.018,
                    )
                )
        for row, (label, values) in enumerate(quality_table(summary)):
            y = top - (row + 2) * row_step
            stimuli.append(text(label, (label_x, y)))
            for eye in EYES:
                color = tuple(colors[eye][:3])
                for column, value in enumerate(values[eye]):
                    stimuli.append(
                        text(value, (value_x[(eye, column)], y), color=color)
                    )
            if row == 0:
                # Within / above the tolerance, next to each eye's worst accuracy.
                for eye in EYES:
                    mark = tolerance_mark(verdict, eye)
                    if mark:
                        stimuli.append(
                            text(
                                mark,
                                (value_x[(eye, 1)] + 0.035 * width, y),
                                color=TOLERANCE_PASS_COLOR
                                if mark == PASS_MARK
                                else TOLERANCE_FAIL_COLOR,
                                size=0.028,
                            )
                        )
        stimuli.append(
            text(
                describe_tolerance(verdict, recalibrate_key="C"),
                (0, top - 5.3 * row_step),
                color=TOLERANCE_PASS_COLOR
                if verdict["passed"]
                else TOLERANCE_FAIL_COLOR,
                size=0.026,
            )
        )
        if validation.get("status") == "partial":
            collected = len(validation.get("points") or ())
            planned = len(validation.get("points_adcs") or ()) or collected
            stimuli.append(
                text(
                    f"Partial validation: {collected} of {planned} targets.",
                    (0, top - 6.3 * row_step),
                )
            )
    else:
        stimuli.append(
            text("Validation skipped: no calibration quality to show.", (0, top))
        )
    stimuli.append(text(RESULTS_KEYS_HINT, (0, -0.44 * height)))
    return stimuli


class DetoxColorDefaults:
    """DeToX 0.2.1's ``ETSettings.colors`` eye colours (RGBA, 0-255).

    Only used if DeToX's own settings can't be read.
    """

    left_eye = DETOX_EYE_COLORS["left"]
    right_eye = DETOX_EYE_COLORS["right"]


def _detox_colors(import_module: ImportModule) -> dict[str, tuple]:
    """Eye colours for the gaze dots, matching DeToX's calibration results."""
    try:
        settings = import_module("DeToX.ETSettings").colors
    except (ImportError, AttributeError):
        settings = DetoxColorDefaults()
    return {eye: tuple(getattr(settings, f"{eye}_eye")) for eye in EYES}


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


class _RecordingCalibration:
    """Wraps Tobii's ``ScreenBasedCalibration`` to keep the last computed result.

    DeToX calls ``compute_and_apply()`` internally and drops the result; this
    proxy records it so the calibration point positions can be saved.
    """

    def __init__(self, calibration):
        self._calibration = calibration
        self.result = None

    def compute_and_apply(self):
        self.result = self._calibration.compute_and_apply()
        return self.result

    def __getattr__(self, name):
        return getattr(self._calibration, name)

    def point_metadata(self) -> dict[str, object]:
        points = getattr(self.result, "calibration_points", None) or ()
        positions = [
            [float(value) for value in point.position_on_display_area]
            for point in points
        ]
        return {"count": len(positions), "positions_adcs": positions}


def run_validation(
    window,
    *,
    eyetracker,
    tobii_research,
    stimulus_dir: Path | None,
    play_sound: bool,
    status: StatusSink,
    animation: str = DEFAULT_ANIMATION,
    animation_settings: object | None = None,
    points=DEFAULT_VALIDATION_POINTS,
    settle_seconds: float | None = None,
    collect_seconds: float = VALIDATION_COLLECT_SECONDS,
    rng: random.Random | None = None,
    gaze_out: list | None = None,
) -> dict[str, object]:
    """Show validation targets, record gaze at each, and compute quality.

    The operator presses Space when the child looks at the target; gaze is then
    recorded for ``collect_seconds`` after a settle. The settle defaults to
    DeToX's ``focus_time``, the wait its calibration uses before collecting, and
    the attention sound fades out over it as in DeToX. Escape stops the
    validation; the calibration is kept either way. Targets are animated the
    same way as DeToX's calibration targets (``animation`` and DeToX's
    ``ETSettings.animation``), so the child sees the same thing in both steps.

    If ``gaze_out`` is given, each collected target's valid on-screen gaze
    positions are appended to it, for the results screen. They aren't part of
    the returned record, which is what gets saved.
    """
    from psychopy import core, event, sound, visual

    animation_settings = animation_settings or DetoxAnimationDefaults()
    if settle_seconds is None:
        settle_seconds = animation_settings.focus_time

    order = list(points)
    (rng or random.Random()).shuffle(order)
    images = sorted(stimulus_dir.glob("*.png")) if stimulus_dir else []
    collector = _GazeCollector()
    display_area = eyetracker.get_display_area()
    gaze_stream = tobii_research.EYETRACKER_GAZE_DATA
    attention_sound = _load_sound(
        sound, stimulus_dir, enabled=play_sound, status=status
    )
    record: dict[str, object] = {
        "points_adcs": [list(point) for point in points],
        "settle_seconds": settle_seconds,
        "collect_seconds": collect_seconds,
    }
    results = []

    eyetracker.subscribe_to(gaze_stream, collector.add, as_dictionary=True)
    try:
        if not _show_instructions(window, visual, event):
            record.update(status="skipped", points=[], summary=None)
            return record
        for index, point in enumerate(order):
            target = _Target(
                window,
                visual,
                core,
                point,
                images,
                index,
                animation=animation,
                settings=animation_settings,
            )
            if attention_sound is not None:
                attention_sound.play()
            try:
                if not _wait_for_space(window, target, event):
                    break
                status(f"Validation: collecting at {point}")
                # Like DeToX: fade the sound out while the eyes settle, so
                # recording starts in silence.
                _animate(
                    window,
                    target,
                    core,
                    settle_seconds,
                    on_progress=_sound_fader(attention_sound),
                )
                _stop_sound(attention_sound)
                collector.start()
                _animate(window, target, core, collect_seconds)
                samples = collector.stop()
            finally:
                _stop_sound(attention_sound)
            target_ucs = adcs_to_ucs(point, display_area)
            if gaze_out is not None:
                gaze_out.append(
                    {
                        "target_adcs": list(point),
                        **{eye: gaze_on_display(samples, eye) for eye in EYES},
                    }
                )
            results.append(
                {
                    "target_adcs": list(point),
                    **{eye: point_quality(samples, target_ucs, eye) for eye in EYES},
                }
            )
    finally:
        eyetracker.unsubscribe_from(gaze_stream, collector.add)

    if not results:
        status_text = "skipped"
    elif len(results) < len(order):
        status_text = "partial"
    else:
        status_text = "complete"
    record.update(
        status=status_text,
        points=[
            {
                "target_adcs": result["target_adcs"],
                **{eye: result[eye].as_dict() for eye in EYES},
            }
            for result in results
        ],
        summary=summarize(results) if results else None,
    )
    record["tolerance"] = tolerance_verdict(record["summary"])
    return record


def describe_validation(validation: dict[str, object]) -> str:
    """One-line validation summary for the console and GUI log."""
    summary = validation.get("summary")
    if not summary:
        return f"Validation {validation.get('status', 'skipped')}."
    parts = []
    for label, key, scale, unit in (
        ("accuracy", "accuracy_deg", 1, "°"),
        ("precision", "precision_rms_deg", 1, "°"),
        ("data loss", "data_loss", 100, "%"),
    ):
        values = [summary[eye][key] for eye in EYES]
        text = " ".join(
            f"{eye[0].upper()} {'n/a' if value is None else f'{value * scale:.2f}{unit}'}"
            for eye, value in zip(EYES, values)
        )
        parts.append(f"{label} {text}")
    return f"Validation {validation['status']}: " + "; ".join(parts) + "."


class _GazeCollector:
    """Buffers gaze samples from the Tobii callback thread while recording."""

    def __init__(self):
        self._lock = threading.Lock()
        self._recording = False
        self._samples: list[dict] = []

    def add(self, sample: dict) -> None:
        with self._lock:
            if self._recording:
                self._samples.append(sample)

    def start(self) -> None:
        with self._lock:
            self._samples = []
            self._recording = True

    def stop(self) -> list[dict]:
        with self._lock:
            self._recording = False
            samples, self._samples = self._samples, []
        return samples


class DetoxAnimationDefaults:
    """DeToX 0.2.1's ``ETSettings.animation`` defaults ("big" stimulus preset).

    Only used if DeToX's own settings can't be read; normally the live settings
    object is passed so validation follows any tuning of the calibration.
    """

    focus_time = 0.5
    zoom_speed = 6.0
    min_zoom_size_big = 0.05
    max_zoom_size_big = 0.16
    trill_size_big = 0.14
    trill_rotation_range = 20
    trill_cycle_duration = 1.5
    trill_active_duration = 1.1
    trill_frequency = 3.0


class _Target:
    """A validation target animated exactly like DeToX's calibration targets.

    Mirrors ``BaseCalibrationSession._animate`` for the "big" stimulus preset
    that ``ETracker.calibrate()`` uses: sizes are fractions of screen height,
    "zoom" oscillates between the min and max size as
    ``(cos(t * zoom_speed) + 1) / 2``, and "trill" rotates the target at a fixed
    size with pauses. Drawn in pix units at an ADCS position.
    """

    def __init__(
        self, window, visual, core, point, images, index, *, animation, settings
    ):
        width, height = window.size
        position = ((point[0] - 0.5) * width, (0.5 - point[1]) * height)
        self._height = height
        self._animation = animation
        self._settings = settings
        self._clock = core.Clock()
        start_size = settings.max_zoom_size_big * height
        if images:
            self._stim = visual.ImageStim(
                window,
                image=str(images[index % len(images)]),
                pos=position,
                size=start_size,
                units="pix",
                interpolate=True,
            )
        else:
            self._stim = visual.Circle(
                window,
                radius=0.5,
                size=start_size,
                pos=position,
                fillColor="white",
                units="pix",
            )

    def draw(self) -> None:
        settings = self._settings
        elapsed = self._clock.getTime()
        if self._animation == "trill":
            self._stim.size = settings.trill_size_big * self._height
            cycle_position = elapsed % settings.trill_cycle_duration
            if cycle_position < settings.trill_active_duration:
                trill_time = cycle_position * settings.trill_frequency * 2 * math.pi
                self._stim.ori = math.sin(trill_time) * settings.trill_rotation_range
            else:
                self._stim.ori = 0
        else:
            oscillation = (math.cos(elapsed * settings.zoom_speed) + 1) / 2
            minimum = settings.min_zoom_size_big * self._height
            maximum = settings.max_zoom_size_big * self._height
            self._stim.size = minimum + oscillation * (maximum - minimum)
        self._stim.draw()


def _show_instructions(window, visual, event) -> bool:
    text = visual.TextStim(
        window,
        text=(
            "Validation\n\n"
            "Press Space when the child looks at each animal.\n"
            "Press Escape to skip validation (the calibration is kept).\n\n"
            "Press Space to start."
        ),
        color="white",
        height=0.03 * window.size[1],
        units="pix",
    )
    event.clearEvents()
    while True:
        text.draw()
        window.flip()
        keys = event.getKeys(keyList=["space", "escape"])
        if "escape" in keys:
            return False
        if "space" in keys:
            return True


def _wait_for_space(window, target: _Target, event) -> bool:
    event.clearEvents()
    while True:
        target.draw()
        window.flip()
        keys = event.getKeys(keyList=["space", "escape"])
        if "escape" in keys:
            return False
        if "space" in keys:
            return True


def _animate(
    window,
    target: _Target,
    core,
    seconds: float,
    on_progress: Callable[[float], None] | None = None,
) -> None:
    """Keep the target animating for ``seconds``; report progress from 0 to 1."""
    clock = core.Clock()
    while (elapsed := clock.getTime()) < seconds:
        if on_progress is not None:
            on_progress(elapsed / seconds)
        target.draw()
        window.flip()


def _sound_fader(attention_sound) -> Callable[[float], None] | None:
    if attention_sound is None:
        return None
    return lambda progress: attention_sound.setVolume(max(0.0, 1.0 - progress))


def _stop_sound(attention_sound) -> None:
    """Stop, and reset the volume for the next target (as DeToX does)."""
    if attention_sound is None:
        return
    attention_sound.stop()
    attention_sound.setVolume(1.0)


def _load_sound(sound, stimulus_dir: Path | None, *, enabled: bool, status):
    if not enabled or stimulus_dir is None:
        return None
    path = stimulus_dir / "CalibrationSound.wav"
    if not path.exists():
        return None
    try:
        return sound.Sound(str(path), loops=-1)
    except Exception as error:  # noqa: BLE001 - audio backends fail many ways
        status(f"Validation sound unavailable ({error}); continuing without it.")
        return None


def _detox_animation_settings(import_module: ImportModule):
    """DeToX's live animation settings, or None to use the bundled defaults."""
    try:
        return import_module("DeToX.ETSettings").animation
    except (ImportError, AttributeError):
        return None


def _detox_stimulus_dir(detox) -> Path | None:
    module_file = getattr(detox, "__file__", None)
    if module_file is None:
        return None
    stimuli = Path(module_file).parent / "stimuli"
    return stimuli if stimuli.is_dir() else None


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
