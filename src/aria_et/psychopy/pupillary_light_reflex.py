"""PsychoPy adapter for Pupillary Light Reflex presentation."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib.resources import as_file
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
    movie_factory: MovieFactory | None = None
    wait: Wait | None = None
    play_sound: bool = True
    trial_limit: int | None = None
    frame_duration_seconds: float = 1 / 30
    render_status: StatusSink | None = None

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
                    "video": trial.stimulus.video.name,
                    "frame_count": trial.frame_count,
                    "flash_frame_count": trial.flash_frame_count,
                },
            )
        )

        self._render_status(f"PLR trial: {trial.trial_id} {trial.stimulus.video.name}")
        with as_file(trial.stimulus.video) as video_path:
            movie = self._movie_factory()(self.window, str(video_path), self.play_sound)
            movie.play()
            try:
                self._draw_for_duration(movie, trial.presentation_seconds)
            finally:
                movie.stop()

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

    def _draw_for_duration(self, movie: MovieLike, duration_seconds: float) -> None:
        remaining_seconds = duration_seconds
        while remaining_seconds > 0:
            frame_seconds = min(self.frame_duration_seconds, remaining_seconds)
            movie.draw()
            self.window.flip()
            self._wait()(frame_seconds)
            remaining_seconds -= frame_seconds

    def _selected_blocks(
        self,
        sequence: PupillaryLightReflexSequence,
    ):
        if self.trial_limit is None:
            return sequence.blocks
        return sequence.blocks[: self.trial_limit]

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
                f"{event.payload['video']}"
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
