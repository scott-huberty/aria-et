"""PsychoPy adapter for calibration presentation."""

from __future__ import annotations

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

        presented_points = tuple(
            self._present_point(point, clock, event_sink) for point in sequence.points
        )

        ended_at = clock.now()
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
            presented_points=presented_points,
            started_at=started_at,
            ended_at=ended_at,
        )

    def _present_point(
        self,
        point: CalibrationPoint,
        clock: Clock,
        event_sink: EventSink,
    ) -> PresentedCalibrationPoint:
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "calibration.point.started",
                started_at,
                {
                    "label": point.target.label,
                    "x": point.target.position.x,
                    "y": point.target.position.y,
                },
            )
        )

        self._play_sound(point.stimulus.sound)
        self._draw_animation(point)

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

    def _draw_animation(self, point: CalibrationPoint) -> None:
        position = self._to_window_position(point.target.position)
        frames = point.stimulus.animation_frames
        frame_count = max(1, round(self.point_duration_seconds / self.frame_duration_seconds))

        for frame_index in range(frame_count):
            frame = frames[frame_index % len(frames)]
            with as_file(frame) as frame_path:
                image = self._image_factory()(
                    self.window,
                    str(frame_path),
                    position,
                    self.image_size_pixels,
                )
                image.draw()
            self.window.flip()
            self._wait()(self.frame_duration_seconds)

    def _play_sound(self, sound: Traversable) -> None:
        if not self.play_sound:
            return

        with as_file(sound) as sound_path:
            self._sound_factory()(str(sound_path)).play()

    def _to_window_position(self, point: NormalizedPoint) -> tuple[float, float]:
        width, height = self.window.size
        return (
            (point.x - 0.5) * width,
            (0.5 - point.y) * height,
        )

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


@dataclass
class PsychoPyClock:
    psychopy_clock: object

    def now(self) -> float:
        return self.psychopy_clock.getTime()


def run_pikachu_calibration_demo(
    *,
    fullscreen: bool = True,
    window_size: tuple[int, int] = (1024, 768),
    play_sound: bool = True,
    point_duration_seconds: float = 1.0,
) -> int:
    from psychopy import core, visual

    from aria_et.runtime import RecordingEventSink

    window = visual.Window(
        size=window_size,
        fullscr=fullscreen,
        units="pix",
        color="black",
    )
    try:
        presenter = PsychoPyCalibrationPresenter(
            window=window,
            play_sound=play_sound,
            point_duration_seconds=point_duration_seconds,
        )
        presenter.present(
            build_pikachu_calibration_sequence(),
            PsychoPyClock(core.Clock()),
            RecordingEventSink(),
        )
    finally:
        window.close()

    return 0
