"""PsychoPy adapter for Pupillary Light Reflex presentation."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from importlib.resources import as_file
from importlib.abc import Traversable
from random import Random
from typing import Protocol

from aria_et.assets import gap_overlap_reward_calibration_assets
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
    inter_trial_attention_seconds: float = 1.0
    render_status: StatusSink | None = None
    _active_sounds: list[SoundLike] = field(default_factory=list, init=False, repr=False)

    def present(
        self,
        sequence: PupillaryLightReflexSequence,
        clock: Clock,
        event_sink: EventSink,
    ) -> PupillaryLightReflexRunResult:
        selected_blocks = self._selected_blocks(sequence)
        image_cache = self._prepare_image_cache(selected_blocks)
        attention_cues = self._prepare_attention_cues(max(0, len(selected_blocks) - 1))
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "pupillary-light-reflex.started",
                started_at,
                {"sequence_id": sequence.sequence_id},
            )
        )

        presented_trials = []
        for block_index, block in enumerate(selected_blocks):
            if block_index > 0 and attention_cues:
                self._present_attention_cue(
                    attention_cues[block_index - 1],
                    clock,
                    event_sink,
                )
            for trial in block.trials:
                presented_trials.append(
                    self._present_trial(
                        block.block_id,
                        trial,
                        image_cache,
                        clock,
                        event_sink,
                    )
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
            presented_trials=tuple(presented_trials),
            started_at=started_at,
            ended_at=ended_at,
        )

    def _present_trial(
        self,
        block_id: str,
        trial: PupillaryLightReflexTrial,
        image_cache: dict[str, tuple[DrawableLike, ...]],
        clock: Clock,
        event_sink: EventSink,
    ) -> PresentedPupillaryLightReflexTrial:
        images = image_cache[trial.stimulus_id]
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

    def _prepare_image_cache(
        self,
        blocks,
    ) -> dict[str, tuple[DrawableLike, ...]]:
        cache = {}
        for block in blocks:
            for trial in block.trials:
                if trial.stimulus_id in cache:
                    continue
                self._render_status(f"PLR preload: {trial.stimulus_id}")
                cache[trial.stimulus_id] = self._prepare_images(trial.stimulus.frames)
        return cache

    def _prepare_attention_cues(
        self,
        cue_count: int,
    ) -> tuple[tuple[tuple[DrawableLike, ...], Traversable], ...]:
        if cue_count == 0 or self.inter_trial_attention_seconds <= 0:
            return ()

        randomizer = Random()
        assets = gap_overlap_reward_calibration_assets()
        cues = []
        for _ in range(cue_count):
            animation = randomizer.choice(assets.animations)
            sound = randomizer.choice(assets.sounds)
            cues.append((self._prepare_images(animation.frames), sound))
        return tuple(cues)

    def _present_attention_cue(
        self,
        cue: tuple[tuple[DrawableLike, ...], Traversable],
        clock: Clock,
        event_sink: EventSink,
    ) -> None:
        frames, sound = cue
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "pupillary-light-reflex.attention-cue.started",
                started_at,
                {
                    "duration_seconds": self.inter_trial_attention_seconds,
                    "sound": sound.name,
                },
            )
        )
        self._play_sound(sound)
        self._draw_for_duration(frames, self.inter_trial_attention_seconds)
        event_sink.emit(
            RuntimeEvent(
                "pupillary-light-reflex.attention-cue.ended",
                clock.now(),
                {"duration_seconds": self.inter_trial_attention_seconds},
            )
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

    def _draw_for_duration(
        self,
        images: tuple[DrawableLike, ...],
        duration_seconds: float,
    ) -> None:
        frame_count = max(1, round(duration_seconds / self.frame_duration_seconds))
        for frame_index in range(frame_count):
            images[frame_index % len(images)].draw()
            self.window.flip()
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
    screen: int = 1,
    window_size: tuple[int, int] = (1024, 768),
    play_sound: bool = True,
    trial_limit: int | None = None,
    inter_trial_attention_seconds: float = 1.0,
    debug_render: bool = False,
    status_sink: StatusSink | None = None,
) -> int:
    status = status_sink or (lambda message: print(message, file=sys.stderr, flush=True))

    status("Importing PsychoPy...")
    from psychopy import core, visual

    from aria_et.runtime import RecordingEventSink

    status(
        "Opening PsychoPy window "
        f"({window_size[0]}x{window_size[1]}, fullscreen={fullscreen}, screen={screen})..."
    )
    window = visual.Window(
        size=window_size,
        fullscr=fullscreen,
        screen=screen,
        units="pix",
        color="black",
    )
    try:
        status("Running Pupillary Light Reflex demo.")
        presenter = PsychoPyPupillaryLightReflexPresenter(
            window=window,
            play_sound=play_sound,
            trial_limit=trial_limit,
            inter_trial_attention_seconds=inter_trial_attention_seconds,
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


def run_pupillary_light_reflex_session(
    *,
    tracker: str,
    tracker_address: str | None = None,
    output_dir: str,
    subject: str,
    session: str | None = None,
    run: str | None = None,
    fullscreen: bool = False,
    screen: int = 1,
    window_size: tuple[int, int] = (1024, 768),
    screen_distance_meters: float = 0.65,
    screen_resolution_pixels: tuple[int, int] = (1920, 1080),
    screen_size_meters: tuple[float, float] = (0.527, 0.296),
    play_sound: bool = True,
    trial_limit: int | None = None,
    inter_trial_attention_seconds: float = 1.0,
    debug_render: bool = False,
    status_sink: StatusSink | None = None,
) -> int:
    from aria_et.session import run_recording_session

    status = status_sink or (lambda message: print(message, file=sys.stderr, flush=True))

    def present(event_sink: EventSink) -> None:
        status("Importing PsychoPy...")
        from psychopy import core, visual

        status(
            "Opening PsychoPy window "
            f"({window_size[0]}x{window_size[1]}, fullscreen={fullscreen}, screen={screen})..."
        )
        window = visual.Window(
            size=window_size,
            fullscr=fullscreen,
            screen=screen,
            units="pix",
            color="black",
        )
        try:
            status("Running Pupillary Light Reflex session.")
            presenter = PsychoPyPupillaryLightReflexPresenter(
                window=window,
                play_sound=play_sound,
                trial_limit=trial_limit,
                inter_trial_attention_seconds=inter_trial_attention_seconds,
                render_status=status if debug_render else None,
            )
            presenter.present(
                build_pupillary_light_reflex_sequence(),
                PsychoPyClock(core.Clock()),
                StatusLoggingEventSink(event_sink, status),
            )
            status("Pupillary Light Reflex session finished.")
        finally:
            status("Closing PsychoPy window...")
            window.close()

    return run_recording_session(
        task_id="pupillary-light-reflex",
        tracker=tracker,
        tracker_address=tracker_address,
        output_dir=output_dir,
        bids=_bids_metadata(subject, session, run),
        stimulus_display=_stimulus_display_metadata(
            screen=screen,
            fullscreen=fullscreen,
            window_size=window_size,
            screen_distance_meters=screen_distance_meters,
            screen_resolution_pixels=screen_resolution_pixels,
            screen_size_meters=screen_size_meters,
        ),
        present=present,
    )


def _bids_metadata(subject: str, session: str | None, run: str | None):
    from aria_et.session import BidsSessionMetadata

    return BidsSessionMetadata(subject=subject, session=session, run=run)


def _stimulus_display_metadata(
    *,
    screen: int,
    fullscreen: bool,
    window_size: tuple[int, int],
    screen_distance_meters: float,
    screen_resolution_pixels: tuple[int, int],
    screen_size_meters: tuple[float, float],
):
    from aria_et.session import StimulusDisplayMetadata

    return StimulusDisplayMetadata(
        screen_distance_meters=screen_distance_meters,
        screen_resolution_pixels=screen_resolution_pixels,
        screen_size_meters=screen_size_meters,
        psychopy_screen=screen,
        fullscreen=fullscreen,
        window_size_pixels=window_size,
    )
