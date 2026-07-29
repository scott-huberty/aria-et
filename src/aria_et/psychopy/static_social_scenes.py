"""PsychoPy adapter for Static Social Scenes / Visual Search presentation."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from importlib.resources import as_file
from typing import Protocol

from aria_et.runtime import Clock, EventSink, RuntimeEvent
from aria_et.static_social_scenes import (
    StaticSocialScenesSequence,
    StaticSocialScenesTrial,
    build_static_social_scenes_sequence,
)


class WindowLike(Protocol):
    size: Sequence[float]
    color: str | tuple[float, float, float]

    def flip(self) -> None:
        """Present the next frame."""


class DrawableLike(Protocol):
    def draw(self) -> None:
        """Draw the object into the current PsychoPy frame."""


class SoundLike(Protocol):
    def play(self) -> None:
        """Start sound playback."""

    def stop(self) -> None:
        """Stop sound playback."""


ImageFactory = Callable[[WindowLike, str], DrawableLike]
SoundFactory = Callable[[str], SoundLike]
Wait = Callable[[float], None]
StatusSink = Callable[[str], None]


@dataclass(frozen=True)
class PresentedStaticSocialScenesTrial:
    trial_id: str
    trial_type: str
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class StaticSocialScenesRunResult:
    sequence_id: str
    presented_trials: tuple[PresentedStaticSocialScenesTrial, ...]
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class PsychoPyStaticSocialScenesPresenter:
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
        sequence: StaticSocialScenesSequence,
        clock: Clock,
        event_sink: EventSink,
    ) -> StaticSocialScenesRunResult:
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "static-social-scenes.started",
                started_at,
                {"sequence_id": sequence.sequence_id},
            )
        )

        presented_trials = tuple(
            self._present_trial(trial, clock, event_sink)
            for trial in self._selected_trials(sequence)
        )

        ended_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "static-social-scenes.ended",
                ended_at,
                {
                    "sequence_id": sequence.sequence_id,
                    "trial_count": len(presented_trials),
                },
            )
        )

        return StaticSocialScenesRunResult(
            sequence_id=sequence.sequence_id,
            presented_trials=presented_trials,
            started_at=started_at,
            ended_at=ended_at,
        )

    def _present_trial(
        self,
        trial: StaticSocialScenesTrial,
        clock: Clock,
        event_sink: EventSink,
    ) -> PresentedStaticSocialScenesTrial:
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "static-social-scenes.trial.started",
                started_at,
                {
                    "trial_id": trial.trial_id,
                    "trial_type": trial.trial_type,
                    "image": trial.stimulus.image.name,
                    "soundtrack": trial.stimulus.soundtrack.name,
                    "background_rgb": trial.background_rgb,
                },
            )
        )

        try:
            self.window.color = _psychopy_rgb(trial.background_rgb)
            self.window.flip()
            self._wait()(trial.preblank_seconds)
            self._wait()(trial.fixation_seconds)
            self._play_soundtrack(trial)
            self._render_status(f"SS trial: {trial.trial_id} {trial.stimulus.image.name}")
            with as_file(trial.stimulus.image) as image_path:
                image = self._image_factory()(self.window, str(image_path))
                self._draw_for_duration(image, trial.presentation_seconds)
            self._wait()(trial.post_blank_seconds)
        finally:
            self._stop_active_sounds()

        ended_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "static-social-scenes.trial.ended",
                ended_at,
                {"trial_id": trial.trial_id},
            )
        )

        return PresentedStaticSocialScenesTrial(
            trial_id=trial.trial_id,
            trial_type=trial.trial_type,
            started_at=started_at,
            ended_at=ended_at,
        )

    def _draw_for_duration(self, drawable: DrawableLike, duration_seconds: float) -> None:
        remaining_seconds = duration_seconds
        while remaining_seconds > 0:
            frame_seconds = min(self.frame_duration_seconds, remaining_seconds)
            drawable.draw()
            self.window.flip()
            self._wait()(frame_seconds)
            remaining_seconds -= frame_seconds

    def _play_soundtrack(self, trial: StaticSocialScenesTrial) -> None:
        if not self.play_sound:
            return

        with as_file(trial.stimulus.soundtrack) as soundtrack_path:
            sound_object = self._sound_factory()(str(soundtrack_path))
            sound_object.play()
            self._active_sounds.append(sound_object)

    def _stop_active_sounds(self) -> None:
        for sound_object in self._active_sounds:
            sound_object.stop()
        self._active_sounds.clear()

    def _selected_trials(
        self,
        sequence: StaticSocialScenesSequence,
    ) -> tuple[StaticSocialScenesTrial, ...]:
        if self.trial_limit is None:
            return sequence.trials
        return sequence.trials[: self.trial_limit]

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
        if event.name == "static-social-scenes.started":
            self.status(f"Static Social Scenes started: {event.payload['sequence_id']}")
        elif event.name == "static-social-scenes.trial.started":
            self.status(
                "SS trial started: "
                f"{event.payload['trial_id']} "
                f"{event.payload['trial_type']} "
                f"{event.payload['image']}"
            )
        elif event.name == "static-social-scenes.trial.ended":
            self.status(f"SS trial ended: {event.payload['trial_id']}")
        elif event.name == "static-social-scenes.ended":
            self.status(
                "Static Social Scenes ended after "
                f"{event.payload['trial_count']} completed trial(s)."
            )


def run_static_social_scenes_demo(
    *,
    fullscreen: bool = False,
    screen: int = 1,
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
        status("Running Static Social Scenes demo.")
        presenter = PsychoPyStaticSocialScenesPresenter(
            window=window,
            play_sound=play_sound,
            trial_limit=trial_limit,
            render_status=status if debug_render else None,
        )
        presenter.present(
            build_static_social_scenes_sequence(),
            PsychoPyClock(core.Clock()),
            StatusLoggingEventSink(RecordingEventSink(), status),
        )
        status("Static Social Scenes demo finished.")
    finally:
        status("Closing PsychoPy window...")
        window.close()

    return 0


def run_static_social_scenes_session(
    *,
    tracker: str,
    tracker_address: str | None = None,
    output_dir: str,
    fullscreen: bool = False,
    screen: int = 1,
    window_size: tuple[int, int] = (1024, 768),
    play_sound: bool = True,
    trial_limit: int | None = None,
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
            status("Running Static Social Scenes session.")
            presenter = PsychoPyStaticSocialScenesPresenter(
                window=window,
                play_sound=play_sound,
                trial_limit=trial_limit,
                render_status=status if debug_render else None,
            )
            presenter.present(
                build_static_social_scenes_sequence(),
                PsychoPyClock(core.Clock()),
                StatusLoggingEventSink(event_sink, status),
            )
            status("Static Social Scenes session finished.")
        finally:
            status("Closing PsychoPy window...")
            window.close()

    return run_recording_session(
        task_id="static-social-scenes",
        tracker=tracker,
        tracker_address=tracker_address,
        output_dir=output_dir,
        present=present,
    )


def _psychopy_rgb(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple((channel / 127.5) - 1 for channel in rgb)
