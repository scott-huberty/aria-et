"""PsychoPy adapter for Pupillary Light Reflex presentation."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from importlib.resources import as_file
from importlib.resources.abc import Traversable
from typing import Protocol

from aria_et.pupillary_light_reflex import (
    PupillaryLightReflexSequence,
    PupillaryLightReflexTrial,
    build_pupillary_light_reflex_sequence,
)
from aria_et.runtime import Clock, EventSink, RuntimeEvent


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


ImageFactory = Callable[[WindowLike, str], DrawableLike]
SoundFactory = Callable[[str], SoundLike]
Wait = Callable[[float], None]
StatusSink = Callable[[str], None]


@dataclass(frozen=True)
class PresentedPupillaryLightReflexTrial:
    trial_id: str
    block_id: str
    stimulus_id: str
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class PupillaryLightReflexRunResult:
    sequence_id: str
    presented_trials: tuple[PresentedPupillaryLightReflexTrial, ...]
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class PsychoPyPupillaryLightReflexPresenter:
    window: WindowLike
    image_factory: ImageFactory | None = None
    sound_factory: SoundFactory | None = None
    wait: Wait | None = None
    play_sound: bool = True
    trial_limit: int | None = None
    frame_duration_seconds: float = 1 / 30
    render_status: StatusSink | None = None
    _active_sounds: list[SoundLike] = field(default_factory=list, init=False, repr=False)

    def present(
        self,
        sequence: PupillaryLightReflexSequence,
        clock: Clock,
        event_sink: EventSink,
    ) -> PupillaryLightReflexRunResult:
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "pupillary-light-reflex.started",
                started_at,
                {"sequence_id": sequence.sequence_id},
            )
        )

        presented_trials = tuple(
            self._present_trial(block.block_id, trial, clock, event_sink)
            for block in self._selected_blocks(sequence)
            for trial in block.trials
        )

        ended_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "pupillary-light-reflex.ended",
                ended_at,
                {
                    "sequence_id": sequence.sequence_id,
                    "trial_count": len(presented_trials),
                },
            )
        )

        return PupillaryLightReflexRunResult(
            sequence_id=sequence.sequence_id,
            presented_trials=presented_trials,
            started_at=started_at,
            ended_at=ended_at,
        )

    def _present_trial(
        self,
        block_id: str,
        trial: PupillaryLightReflexTrial,
        clock: Clock,
        event_sink: EventSink,
    ) -> PresentedPupillaryLightReflexTrial:
        self._render_status(f"PLR trial preload: {trial.trial_id} {trial.stimulus_id}")
        images = self._prepare_images(trial.stimulus.frames)
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "pupillary-light-reflex.trial.started",
                started_at,
                {
                    "trial_id": trial.trial_id,
                    "block_id": block_id,
                    "block_number": trial.block_number,
                    "sequence_trial_number": trial.sequence_trial_number,
                    "stimulus_id": trial.stimulus_id,
                    "sound": trial.stimulus.sound.name,
                    "frame_count": trial.frame_count,
                    "flash_frame_start": trial.flash_frame_start,
                    "flash_frame_count": trial.flash_frame_count,
                },
            )
        )

        self._render_status(f"PLR trial: {trial.trial_id} {trial.stimulus_id}")
        self._play_sound(trial.stimulus.sound)
        self._draw_frames(trial, images, clock, event_sink)

        ended_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "pupillary-light-reflex.trial.ended",
                ended_at,
                {"trial_id": trial.trial_id},
            )
        )

        return PresentedPupillaryLightReflexTrial(
            trial_id=trial.trial_id,
            block_id=block_id,
            stimulus_id=trial.stimulus_id,
            started_at=started_at,
            ended_at=ended_at,
        )

    def _prepare_images(self, frames: tuple[Traversable, ...]) -> tuple[DrawableLike, ...]:
        images = []
        for frame in frames:
            with as_file(frame) as frame_path:
                images.append(self._image_factory()(self.window, str(frame_path)))
        return tuple(images)

    def _draw_frames(
        self,
        trial: PupillaryLightReflexTrial,
        images: tuple[DrawableLike, ...],
        clock: Clock,
        event_sink: EventSink,
    ) -> None:
        flash_start = trial.flash_frame_start
        flash_end = trial.flash_frame_start + trial.flash_frame_count - 1
        for frame_index, image in enumerate(images, start=1):
            image.draw()
            self.window.flip()
            timestamp = clock.now()
            if flash_start <= frame_index <= flash_end:
                event_sink.emit(
                    RuntimeEvent(
                        "pupillary-light-reflex.flash-frame.presented",
                        timestamp,
                        {
                            "trial_id": trial.trial_id,
                            "stimulus_id": trial.stimulus_id,
                            "frame_index": frame_index,
                            "flash_frame_index": frame_index - flash_start + 1,
                        },
                    )
                )
            self._wait()(self.frame_duration_seconds)

    def _play_sound(self, sound: Traversable) -> None:
        if not self.play_sound:
            return

        with as_file(sound) as sound_path:
            sound_object = self._sound_factory()(str(sound_path))
            sound_object.play()
            self._active_sounds.append(sound_object)

    def _selected_blocks(
        self,
        sequence: PupillaryLightReflexSequence,
    ):
        if self.trial_limit is None:
            return sequence.blocks
        return sequence.blocks[: self.trial_limit]

    def _image_factory(self) -> ImageFactory:
        if self.image_factory is not None:
            return self.image_factory

        from psychopy import visual

        return lambda window, image: visual.ImageStim(
            window,
            image=image,
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
        if event.name == "pupillary-light-reflex.started":
            self.status(
                f"Pupillary Light Reflex started: {event.payload['sequence_id']}"
            )
        elif event.name == "pupillary-light-reflex.trial.started":
            self.status(
                "PLR trial started: "
                f"{event.payload['trial_id']} "
                f"{event.payload['block_id']} "
                f"{event.payload['stimulus_id']} "
                f"{event.payload['sound']}"
            )
        elif event.name == "pupillary-light-reflex.trial.ended":
            self.status(f"PLR trial ended: {event.payload['trial_id']}")
        elif event.name == "pupillary-light-reflex.ended":
            self.status(
                "Pupillary Light Reflex ended after "
                f"{event.payload['trial_count']} completed trial(s)."
            )


def run_pupillary_light_reflex_demo(
    *,
    fullscreen: bool = False,
    window_size: tuple[int, int] = (1024, 768),
    play_sound: bool = True,
    trial_limit: int | None = None,
    debug_render: bool = False,
    status_sink: StatusSink | None = None,
) -> int:
    status = status_sink or (lambda message: print(message, file=sys.stderr, flush=True))

    status("Importing PsychoPy...")
    from psychopy import core, visual

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
        status("Running Pupillary Light Reflex demo.")
        presenter = PsychoPyPupillaryLightReflexPresenter(
            window=window,
            play_sound=play_sound,
            trial_limit=trial_limit,
            render_status=status if debug_render else None,
        )
        presenter.present(
            build_pupillary_light_reflex_sequence(),
            PsychoPyClock(core.Clock()),
            StatusLoggingEventSink(RecordingEventSink(), status),
        )
        status("Pupillary Light Reflex demo finished.")
    finally:
        status("Closing PsychoPy window...")
        window.close()

    return 0
