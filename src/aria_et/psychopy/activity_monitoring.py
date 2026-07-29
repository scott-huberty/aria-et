"""PsychoPy adapter for Activity Monitoring presentation."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from importlib.resources import as_file
from typing import Protocol

from aria_et.activity_monitoring import (
    ActivityMonitoringSequence,
    ActivityMonitoringTrial,
    build_activity_monitoring_sequence,
)
from aria_et.runtime import Clock, EventSink, RuntimeEvent


class WindowLike(Protocol):
    size: Sequence[float]
    color: str | tuple[float, float, float]

    def flip(self) -> None:
        """Present the next frame."""


class DrawableLike(Protocol):
    def draw(self) -> None:
        """Draw the object into the current PsychoPy frame."""


class MovieLike(Protocol):
    def play(self) -> None:
        """Start movie playback."""

    def draw(self) -> None:
        """Draw the current movie frame."""

    def stop(self) -> None:
        """Stop movie playback."""


class SoundLike(Protocol):
    def play(self) -> None:
        """Start sound playback."""

    def stop(self) -> None:
        """Stop sound playback."""


ImageFactory = Callable[[WindowLike, str], DrawableLike]
MovieFactory = Callable[[WindowLike, str], MovieLike]
SoundFactory = Callable[[str], SoundLike]
Wait = Callable[[float], None]
StatusSink = Callable[[str], None]


@dataclass(frozen=True)
class PresentedActivityMonitoringTrial:
    trial_id: str
    media_type: str
    gaze_condition: str
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class ActivityMonitoringRunResult:
    sequence_id: str
    presented_trials: tuple[PresentedActivityMonitoringTrial, ...]
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class PsychoPyActivityMonitoringPresenter:
    window: WindowLike
    image_factory: ImageFactory | None = None
    movie_factory: MovieFactory | None = None
    sound_factory: SoundFactory | None = None
    wait: Wait | None = None
    play_sound: bool = True
    trial_limit: int | None = None
    frame_duration_seconds: float = 1 / 30
    inter_trial_interval_seconds: float = 1.0
    render_status: StatusSink | None = None
    _active_sounds: list[SoundLike] = field(default_factory=list, init=False, repr=False)

    def present(
        self,
        sequence: ActivityMonitoringSequence,
        clock: Clock,
        event_sink: EventSink,
    ) -> ActivityMonitoringRunResult:
        selected_trials = self._selected_trials(sequence)
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "activity-monitoring.started",
                started_at,
                {"sequence_id": sequence.sequence_id},
            )
        )

        presented_trials = []
        for trial_index, trial in enumerate(selected_trials):
            presented_trials.append(self._present_trial(trial, clock, event_sink))
            if trial_index < len(selected_trials) - 1:
                self._present_inter_trial_interval(clock, event_sink)

        ended_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "activity-monitoring.ended",
                ended_at,
                {
                    "sequence_id": sequence.sequence_id,
                    "trial_count": len(presented_trials),
                },
            )
        )

        return ActivityMonitoringRunResult(
            sequence_id=sequence.sequence_id,
            presented_trials=tuple(presented_trials),
            started_at=started_at,
            ended_at=ended_at,
        )

    def _present_trial(
        self,
        trial: ActivityMonitoringTrial,
        clock: Clock,
        event_sink: EventSink,
    ) -> PresentedActivityMonitoringTrial:
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "activity-monitoring.trial.started",
                started_at,
                {
                    "trial_id": trial.trial_id,
                    "media_type": trial.media_type,
                    "gaze_condition": trial.gaze_condition,
                    "media": trial.stimulus.media.name,
                },
            )
        )

        self._wait()(trial.fixation_seconds)
        if trial.media_type == "static-image":
            self._present_image_trial(trial)
        else:
            self._present_movie_trial(trial)
        self._wait()(trial.post_blank_seconds)

        ended_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "activity-monitoring.trial.ended",
                ended_at,
                {"trial_id": trial.trial_id},
            )
        )

        return PresentedActivityMonitoringTrial(
            trial_id=trial.trial_id,
            media_type=trial.media_type,
            gaze_condition=trial.gaze_condition,
            started_at=started_at,
            ended_at=ended_at,
        )

    def _present_image_trial(self, trial: ActivityMonitoringTrial) -> None:
        self._play_soundtrack(trial)
        self._render_status(f"Image trial: {trial.trial_id} {trial.stimulus.media.name}")
        with as_file(trial.stimulus.media) as media_path:
            image = self._image_factory()(self.window, str(media_path))
            try:
                self._draw_for_duration(image, trial.presentation_seconds)
            finally:
                self._stop_active_sounds()

    def _present_movie_trial(self, trial: ActivityMonitoringTrial) -> None:
        self._render_status(f"Movie trial: {trial.trial_id} {trial.stimulus.media.name}")
        with as_file(trial.stimulus.media) as media_path:
            movie = self._movie_factory()(self.window, str(media_path))
            movie.play()
            try:
                self._draw_for_duration(movie, trial.presentation_seconds)
            finally:
                movie.stop()

    def _draw_for_duration(self, drawable: DrawableLike, duration_seconds: float) -> None:
        remaining_seconds = duration_seconds
        while remaining_seconds > 0:
            frame_seconds = min(self.frame_duration_seconds, remaining_seconds)
            drawable.draw()
            self.window.flip()
            self._wait()(frame_seconds)
            remaining_seconds -= frame_seconds

    def _play_soundtrack(self, trial: ActivityMonitoringTrial) -> None:
        if not self.play_sound or trial.stimulus.soundtrack is None:
            return

        with as_file(trial.stimulus.soundtrack) as soundtrack_path:
            sound_object = self._sound_factory()(str(soundtrack_path))
            sound_object.play()
            self._active_sounds.append(sound_object)

    def _present_inter_trial_interval(
        self,
        clock: Clock,
        event_sink: EventSink,
    ) -> None:
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "activity-monitoring.inter-trial-interval.started",
                started_at,
                {"duration_seconds": self.inter_trial_interval_seconds},
            )
        )
        self.window.color = "black"
        self.window.flip()
        self._wait()(self.inter_trial_interval_seconds)
        event_sink.emit(
            RuntimeEvent(
                "activity-monitoring.inter-trial-interval.ended",
                clock.now(),
                {"duration_seconds": self.inter_trial_interval_seconds},
            )
        )

    def _stop_active_sounds(self) -> None:
        for sound_object in self._active_sounds:
            sound_object.stop()
        self._active_sounds.clear()

    def _selected_trials(
        self,
        sequence: ActivityMonitoringSequence,
    ) -> tuple[ActivityMonitoringTrial, ...]:
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

    def _movie_factory(self) -> MovieFactory:
        if self.movie_factory is not None:
            return self.movie_factory

        from psychopy import visual

        return lambda window, movie: visual.MovieStim(
            window,
            filename=movie,
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
        if event.name == "activity-monitoring.started":
            self.status(f"Activity Monitoring started: {event.payload['sequence_id']}")
        elif event.name == "activity-monitoring.trial.started":
            self.status(
                "AM trial started: "
                f"{event.payload['trial_id']} "
                f"{event.payload['media_type']} "
                f"{event.payload['gaze_condition']} "
                f"{event.payload['media']}"
            )
        elif event.name == "activity-monitoring.trial.ended":
            self.status(f"AM trial ended: {event.payload['trial_id']}")
        elif event.name == "activity-monitoring.ended":
            self.status(
                "Activity Monitoring ended after "
                f"{event.payload['trial_count']} completed trial(s)."
            )


def run_activity_monitoring_demo(
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
        status("Running Activity Monitoring demo.")
        presenter = PsychoPyActivityMonitoringPresenter(
            window=window,
            play_sound=play_sound,
            trial_limit=trial_limit,
            render_status=status if debug_render else None,
        )
        presenter.present(
            build_activity_monitoring_sequence(),
            PsychoPyClock(core.Clock()),
            StatusLoggingEventSink(RecordingEventSink(), status),
        )
        status("Activity Monitoring demo finished.")
    finally:
        status("Closing PsychoPy window...")
        window.close()

    return 0


def run_activity_monitoring_session(
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
            status("Running Activity Monitoring session.")
            presenter = PsychoPyActivityMonitoringPresenter(
                window=window,
                play_sound=play_sound,
                trial_limit=trial_limit,
                render_status=status if debug_render else None,
            )
            presenter.present(
                build_activity_monitoring_sequence(),
                PsychoPyClock(core.Clock()),
                StatusLoggingEventSink(event_sink, status),
            )
            status("Activity Monitoring session finished.")
        finally:
            status("Closing PsychoPy window...")
            window.close()

    return run_recording_session(
        task_id="activity-monitoring",
        tracker=tracker,
        tracker_address=tracker_address,
        output_dir=output_dir,
        present=present,
    )
