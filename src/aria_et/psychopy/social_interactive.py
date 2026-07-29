"""PsychoPy adapter for Social Interactive presentation."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib.resources import as_file
from typing import Protocol

from aria_et.runtime import Clock, EventSink, RuntimeEvent
from aria_et.social_interactive import (
    SocialInteractiveSequence,
    SocialInteractiveTrial,
    build_social_interactive_sequence,
)


class WindowLike(Protocol):
    size: Sequence[float]

    def flip(self) -> None:
        """Present the next frame."""


class MovieLike(Protocol):
    def play(self) -> None:
        """Start movie playback."""

    def draw(self) -> None:
        """Draw the current movie frame."""

    def stop(self) -> None:
        """Stop movie playback."""


MovieFactory = Callable[[WindowLike, str, bool], MovieLike]
Wait = Callable[[float], None]
StatusSink = Callable[[str], None]


@dataclass(frozen=True)
class PresentedSocialInteractiveTrial:
    trial_id: str
    block_id: str
    play_condition: str
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class SocialInteractiveRunResult:
    sequence_id: str
    presented_trials: tuple[PresentedSocialInteractiveTrial, ...]
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class PsychoPySocialInteractivePresenter:
    window: WindowLike
    movie_factory: MovieFactory | None = None
    wait: Wait | None = None
    play_sound: bool = True
    trial_limit: int | None = None
    frame_duration_seconds: float = 1 / 30
    render_status: StatusSink | None = None

    def present(
        self,
        sequence: SocialInteractiveSequence,
        clock: Clock,
        event_sink: EventSink,
    ) -> SocialInteractiveRunResult:
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "social-interactive.started",
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
                "social-interactive.ended",
                ended_at,
                {
                    "sequence_id": sequence.sequence_id,
                    "trial_count": len(presented_trials),
                },
            )
        )

        return SocialInteractiveRunResult(
            sequence_id=sequence.sequence_id,
            presented_trials=presented_trials,
            started_at=started_at,
            ended_at=ended_at,
        )

    def _present_trial(
        self,
        trial: SocialInteractiveTrial,
        clock: Clock,
        event_sink: EventSink,
    ) -> PresentedSocialInteractiveTrial:
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "social-interactive.trial.started",
                started_at,
                {
                    "trial_id": trial.trial_id,
                    "block_id": f"SI-B{trial.block_number}",
                    "block_number": trial.block_number,
                    "block_trial_number": trial.block_trial_number,
                    "sequence_trial_number": trial.sequence_trial_number,
                    "source_id": trial.source_id,
                    "play_condition": trial.play_condition,
                    "video": trial.stimulus.video.name,
                },
            )
        )

        self._wait()(trial.fixation_seconds)
        self._render_status(f"SI trial: {trial.trial_id} {trial.stimulus.video.name}")
        with as_file(trial.stimulus.video) as video_path:
            movie = self._movie_factory()(self.window, str(video_path), self.play_sound)
            movie.play()
            try:
                self._draw_for_duration(movie, trial.presentation_seconds)
            finally:
                movie.stop()
        self._wait()(trial.post_blank_seconds)

        ended_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "social-interactive.trial.ended",
                ended_at,
                {"trial_id": trial.trial_id},
            )
        )

        return PresentedSocialInteractiveTrial(
            trial_id=trial.trial_id,
            block_id=f"SI-B{trial.block_number}",
            play_condition=trial.play_condition,
            started_at=started_at,
            ended_at=ended_at,
        )

    def _draw_for_duration(self, movie: MovieLike, duration_seconds: float) -> None:
        remaining_seconds = duration_seconds
        while remaining_seconds > 0:
            frame_seconds = min(self.frame_duration_seconds, remaining_seconds)
            movie.draw()
            self.window.flip()
            self._wait()(frame_seconds)
            remaining_seconds -= frame_seconds

    def _selected_trials(
        self,
        sequence: SocialInteractiveSequence,
    ) -> tuple[SocialInteractiveTrial, ...]:
        if self.trial_limit is None:
            return sequence.trials
        return sequence.trials[: self.trial_limit]

    def _movie_factory(self) -> MovieFactory:
        if self.movie_factory is not None:
            return self.movie_factory

        from psychopy import visual

        return lambda window, movie, play_sound: visual.MovieStim(
            window,
            filename=movie,
            noAudio=not play_sound,
        )

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
        if event.name == "social-interactive.started":
            self.status(f"Social Interactive started: {event.payload['sequence_id']}")
        elif event.name == "social-interactive.trial.started":
            self.status(
                "SI trial started: "
                f"{event.payload['trial_id']} "
                f"{event.payload['block_id']} "
                f"{event.payload['play_condition']} "
                f"{event.payload['video']}"
            )
        elif event.name == "social-interactive.trial.ended":
            self.status(f"SI trial ended: {event.payload['trial_id']}")
        elif event.name == "social-interactive.ended":
            self.status(
                "Social Interactive ended after "
                f"{event.payload['trial_count']} completed trial(s)."
            )


def run_social_interactive_demo(
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
        status("Running Social Interactive demo.")
        presenter = PsychoPySocialInteractivePresenter(
            window=window,
            play_sound=play_sound,
            trial_limit=trial_limit,
            render_status=status if debug_render else None,
        )
        presenter.present(
            build_social_interactive_sequence(),
            PsychoPyClock(core.Clock()),
            StatusLoggingEventSink(RecordingEventSink(), status),
        )
        status("Social Interactive demo finished.")
    finally:
        status("Closing PsychoPy window...")
        window.close()

    return 0
