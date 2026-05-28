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
        if not self._draw_animation(point):
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

    def _draw_animation(self, point: CalibrationPoint) -> bool:
        position = self._to_window_position(point.target.position)
        frames = point.stimulus.animation_frames
        frame_count = max(1, round(self.point_duration_seconds / self.frame_duration_seconds))

        for frame_index in range(frame_count):
            if self._abort_requested():
                return False

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

        return True

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

    def _abort_requested(self) -> bool:
        return self.abort_requested is not None and self.abort_requested()

    def _wait_for_advance(self) -> bool:
        if self.advance_requested is None:
            return True

        while not self.advance_requested():
            if self._abort_requested():
                return False
            self._wait()(self.frame_duration_seconds)

        return True


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
    advance_on_space: bool = False,
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
    try:
        if advance_on_space:
            status("Running Pikachu calibration. Press Space for each point; Escape stops.")
        else:
            status("Running Pikachu calibration. Press Escape to stop.")

        event.clearEvents()
        presenter = PsychoPyCalibrationPresenter(
            window=window,
            play_sound=play_sound,
            point_duration_seconds=point_duration_seconds,
            abort_requested=lambda: bool(event.getKeys(keyList=["escape"])),
            advance_requested=(
                lambda: bool(event.getKeys(keyList=["space"]))
                if advance_on_space
                else None
            ),
        )
        presenter.present(
            build_pikachu_calibration_sequence(),
            PsychoPyClock(core.Clock()),
            RecordingEventSink(),
        )
        status("Calibration demo finished.")
    finally:
        status("Closing PsychoPy window...")
        window.close()

    return 0
