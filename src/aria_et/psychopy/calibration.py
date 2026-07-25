"""PsychoPy adapter for calibration presentation."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib.resources import as_file
from importlib.resources.abc import Traversable
from typing import Protocol

from aria_et.calibration import build_pikachu_calibration_sequence
from aria_et.calibration import CalibrationPoint, CalibrationSequence, NormalizedPoint
from aria_et.runtime import (
    CalibrationRunResult,
    Clock,
    EventSink,
    PresentedCalibrationPoint,
    RuntimeEvent,
)


class WindowLike(Protocol):
    size: Sequence[float]
    clientSize: Sequence[float]

    def flip(self) -> None:
        """Present the next frame."""


class DrawableLike(Protocol):
    def draw(self) -> None:
        """Draw the object into the current PsychoPy frame."""


class SoundLike(Protocol):
    def play(self) -> None:
        """Start sound playback."""


ImageFactory = Callable[[WindowLike, str, tuple[float, float], tuple[float, float]], DrawableLike]
SoundFactory = Callable[[str], SoundLike]
Wait = Callable[[float], None]
AbortCheck = Callable[[], bool]
AdvanceCheck = Callable[[], bool]
StatusSink = Callable[[str], None]
RenderStatus = Callable[[str], None]


@dataclass(frozen=True)
class PsychoPyCalibrationPresenter:
    window: WindowLike
    image_factory: ImageFactory | None = None
    sound_factory: SoundFactory | None = None
    wait: Wait | None = None
    point_duration_seconds: float = 1.0
    frame_duration_seconds: float = 1 / 30
    image_size_pixels: tuple[float, float] = (120, 120)
    play_sound: bool = True
    abort_requested: AbortCheck | None = None
    advance_requested: AdvanceCheck | None = None
    render_status: RenderStatus | None = None

    def present(
        self,
        sequence: CalibrationSequence,
        clock: Clock,
        event_sink: EventSink,
    ) -> CalibrationRunResult:
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "calibration.started",
                started_at,
                {"sequence_id": sequence.sequence_id},
            )
        )

        presented_points = []
        aborted = False
        for point in sequence.points:
            if self._abort_requested():
                aborted = True
                break

            presented_point = self._present_point(point, clock, event_sink)
            if presented_point is None:
                aborted = True
                break

            presented_points.append(presented_point)

        ended_at = clock.now()
        if aborted:
            event_sink.emit(
                RuntimeEvent(
                    "calibration.aborted",
                    ended_at,
                    {
                        "sequence_id": sequence.sequence_id,
                        "point_count": len(presented_points),
                    },
                )
            )

        event_sink.emit(
            RuntimeEvent(
                "calibration.ended",
                ended_at,
                {
                    "sequence_id": sequence.sequence_id,
                    "point_count": len(presented_points),
                },
            )
        )

        return CalibrationRunResult(
            sequence_id=sequence.sequence_id,
            presented_points=tuple(presented_points),
            started_at=started_at,
            ended_at=ended_at,
        )

    def _present_point(
        self,
        point: CalibrationPoint,
        clock: Clock,
        event_sink: EventSink,
    ) -> PresentedCalibrationPoint | None:
        started_at = clock.now()
        window_position = self._to_window_position(point.target.position)
        event_sink.emit(
            RuntimeEvent(
                "calibration.point.started",
                started_at,
                {
                    "label": point.target.label,
                    "x": point.target.position.x,
                    "y": point.target.position.y,
                    "window_x": window_position[0],
                    "window_y": window_position[1],
                },
            )
        )

        self._play_sound(point.stimulus.sound)
        if not self._present_stimulus(point):
            return None
        if not self._wait_for_advance():
            return None

        ended_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "calibration.point.ended",
                ended_at,
                {"label": point.target.label},
            )
        )

        return PresentedCalibrationPoint(
            label=point.target.label,
            position=point.target.position,
            started_at=started_at,
            ended_at=ended_at,
        )

    def _present_stimulus(self, point: CalibrationPoint) -> bool:
        return self._draw_frame_animation(point)

    def _draw_frame_animation(self, point: CalibrationPoint) -> bool:
        position = self._to_window_position(point.target.position)
        frames = point.stimulus.animation_frames
        if not frames:
            raise ValueError("Calibration stimulus must include frames or a movie.")
        frame_count = max(1, round(self.point_duration_seconds / self.frame_duration_seconds))
        self._render_status(
            f"Animation started: {point.target.label} "
            f"frame_count={frame_count} frame_duration={self.frame_duration_seconds}"
        )

        for frame_index in range(frame_count):
            if self._abort_requested():
                self._render_status(
                    f"Animation aborted before frame: {point.target.label} "
                    f"frame={frame_index + 1}/{frame_count}"
                )
                return False

            frame = frames[frame_index % len(frames)]
            self._render_status(
                f"Frame image create: {point.target.label} frame={frame_index + 1}/{frame_count}"
            )
            with as_file(frame) as frame_path:
                image = self._image_factory()(
                    self.window,
                    str(frame_path),
                    position,
                    self.image_size_pixels,
                )
                self._render_status(
                    f"Frame draw: {point.target.label} frame={frame_index + 1}/{frame_count}"
                )
                image.draw()
            self._render_status(
                f"Frame flip: {point.target.label} frame={frame_index + 1}/{frame_count}"
            )
            self.window.flip()
            self._render_status(
                f"Frame wait: {point.target.label} frame={frame_index + 1}/{frame_count}"
            )
            self._wait()(self.frame_duration_seconds)
            self._render_status(
                f"Frame done: {point.target.label} frame={frame_index + 1}/{frame_count}"
            )

        self._render_status(f"Animation ended: {point.target.label}")
        return True

    def _play_sound(self, sound: Traversable | None) -> None:
        if not self.play_sound or sound is None:
            return

        with as_file(sound) as sound_path:
            self._sound_factory()(str(sound_path)).play()

    def _to_window_position(self, point: NormalizedPoint) -> tuple[float, float]:
        width, height = self._coordinate_size()
        return (
            (point.x - 0.5) * width,
            (0.5 - point.y) * height,
        )

    def _coordinate_size(self) -> Sequence[float]:
        return getattr(self.window, "clientSize", self.window.size)

    def _image_factory(self) -> ImageFactory:
        if self.image_factory is not None:
            return self.image_factory

        from psychopy import visual

        return lambda window, image, pos, size: visual.ImageStim(
            window,
            image=image,
            pos=pos,
            size=size,
            units="pix",
        )

    def _sound_factory(self) -> SoundFactory:
        if self.sound_factory is not None:
            return self.sound_factory

        from psychopy import sound

        return lambda path: sound.Sound(path)

    def _wait(self) -> Wait:
        if self.wait is not None:
            return self.wait

        from psychopy import core

        return core.wait

    def _abort_requested(self) -> bool:
        return self.abort_requested is not None and self.abort_requested()

    def _wait_for_advance(self) -> bool:
        if self.advance_requested is None:
            return True

        self._render_status("Waiting for advance")
        while not self.advance_requested():
            if self._abort_requested():
                self._render_status("Advance wait aborted")
                return False
            self._wait()(self.frame_duration_seconds)

        self._render_status("Advance received")
        return True

    def _render_status(self, message: str) -> None:
        if self.render_status is not None:
            self.render_status(message)


@dataclass
class PsychoPyClock:
    psychopy_clock: object

    def now(self) -> float:
        return self.psychopy_clock.getTime()


@dataclass
class StatusLoggingEventSink:
    delegate: EventSink
    status: StatusSink

    def emit(self, event: RuntimeEvent) -> None:
        self.delegate.emit(event)
        if event.name == "calibration.started":
            self.status(f"Calibration started: {event.payload['sequence_id']}")
        elif event.name == "calibration.point.started":
            self.status(
                "Point started: "
                f"{event.payload['label']} "
                f"normalized=({event.payload['x']}, {event.payload['y']}) "
                f"window=({event.payload['window_x']}, {event.payload['window_y']})"
            )
        elif event.name == "calibration.point.ended":
            self.status(f"Point ended: {event.payload['label']}")
        elif event.name == "calibration.aborted":
            self.status(
                "Calibration aborted after "
                f"{event.payload['point_count']} completed point(s)."
            )
        elif event.name == "calibration.ended":
            self.status(
                "Calibration ended after "
                f"{event.payload['point_count']} completed point(s)."
            )


def run_pikachu_calibration_demo(
    *,
    fullscreen: bool = True,
    window_size: tuple[int, int] = (1024, 768),
    play_sound: bool = True,
    point_duration_seconds: float = 1.0,
    advance_on_space: bool = False,
    debug_render: bool = False,
    status_sink: StatusSink | None = None,
) -> int:
    status = status_sink or (lambda message: print(message, file=sys.stderr, flush=True))

    status("Importing PsychoPy...")
    from psychopy import core, event, visual

    from aria_et.runtime import RecordingEventSink

    status(
        "Opening PsychoPy window "
        f"({window_size[0]}x{window_size[1]}, fullscreen={fullscreen})..."
    )
    window = visual.Window(
        size=window_size,
        fullscr=fullscreen,
        units="pix",
        color="black",
    )
    status(
        "PsychoPy window sizes: "
        f"size={tuple(window.size)} "
        f"clientSize={tuple(getattr(window, 'clientSize', ())) or 'unavailable'}"
    )
    try:
        if advance_on_space:
            status("Running Pikachu calibration. Press Space for each point; Escape stops.")
        else:
            status("Running Pikachu calibration. Press Escape to stop.")

        event.clearEvents()
        abort_requested = lambda: bool(event.getKeys(keyList=["escape"]))
        advance_requested = None
        if advance_on_space:
            advance_requested = lambda: bool(event.getKeys(keyList=["space"]))

        presenter = PsychoPyCalibrationPresenter(
            window=window,
            play_sound=play_sound,
            point_duration_seconds=point_duration_seconds,
            abort_requested=abort_requested,
            advance_requested=advance_requested,
            render_status=status if debug_render else None,
        )
        presenter.present(
            build_pikachu_calibration_sequence(),
            PsychoPyClock(core.Clock()),
            StatusLoggingEventSink(RecordingEventSink(), status),
        )
        status("Calibration demo finished.")
    finally:
        status("Closing PsychoPy window...")
        window.close()

    return 0
