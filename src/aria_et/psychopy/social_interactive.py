"""PsychoPy adapter for Social Interactive presentation."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib.resources import as_file
from pathlib import Path
from typing import TYPE_CHECKING

from aria_et.protocols import MovieLike, StatusSink, Wait, WindowLike
from aria_et.psychopy.environment import (
    PsychoPyClock,
    bids_session_metadata,
    stimulus_display_metadata,
)
from aria_et.runtime import Clock, EventSink, RuntimeEvent
from aria_et.social_interactive import (
    SocialInteractiveSequence,
    SocialInteractiveTrial,
    build_social_interactive_sequence,
)

if TYPE_CHECKING:
    from aria_et.session import TrackerName


__all__ = [
    "MovieFactory",
    "PresentedSocialInteractiveTrial",
    "PsychoPySocialInteractivePresenter",
    "SocialInteractiveRunResult",
    "StatusLoggingEventSink",
    "run_social_interactive_demo",
    "run_social_interactive_session",
]


MovieFactory = Callable[[WindowLike, str, bool], MovieLike]


@dataclass(frozen=True)
class PresentedSocialInteractiveTrial:
    """One Social Interactive trial that was shown.

    Attributes
    ----------
    trial_id : str
        The trial id.
    block_id : str
        The block id.
    play_condition : str
        ``"parallel-play"`` or ``"cooperative-play"``.
    started_at : float
        The start time, from the clock of the task.
    ended_at : float
        The end time, from the clock of the task.
    """

    trial_id: str
    block_id: str
    play_condition: str
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class SocialInteractiveRunResult:
    """The result of one Social Interactive presentation.

    Attributes
    ----------
    sequence_id : str
        The sequence id.
    presented_trials : tuple[PresentedSocialInteractiveTrial, ...]
        The trials that were shown, in presentation order.
    started_at : float
        The start time, from the clock of the task.
    ended_at : float
        The end time, from the clock of the task.
    """

    sequence_id: str
    presented_trials: tuple[PresentedSocialInteractiveTrial, ...]
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class PsychoPySocialInteractivePresenter:
    """Shows the Social Interactive sequence in a PsychoPy window.

    Each trial shows a fixation blank, then a video with its audio, then a
    blank.

    Attributes
    ----------
    window : WindowLike
        The PsychoPy window.
    movie_factory : MovieFactory or None
        Makes a movie stimulus. None uses ``psychopy.visual.MovieStim``.
    wait : Wait or None
        Waits a number of seconds. None uses ``psychopy.core.wait``.
    play_sound : bool
        False plays no stimulus audio.
    trial_limit : int or None
        The maximum number of trials to show. None shows all trials.
    frame_duration_seconds : float
        The duration of one frame of the draw loop.
    render_status : StatusSink or None
        Receives a status line for each stimulus that is drawn. None writes
        nothing.
    monotonic : Callable[[], float]
        Gives the time in seconds for the draw loop. For tests.
    """

    window: WindowLike
    movie_factory: MovieFactory | None = None
    wait: Wait | None = None
    play_sound: bool = True
    trial_limit: int | None = None
    frame_duration_seconds: float = 1 / 30
    render_status: StatusSink | None = None
    monotonic: Callable[[], float] = time.perf_counter

    def present(
        self,
        sequence: SocialInteractiveSequence,
        clock: Clock,
        event_sink: EventSink,
    ) -> SocialInteractiveRunResult:
        """Show the trials and emit their events.

        Parameters
        ----------
        sequence : SocialInteractiveSequence
            The trial sequence to show.
        clock : Clock
            Gives the event times.
        event_sink : EventSink
            Receives the events of the task.

        Returns
        -------
        SocialInteractiveRunResult
            The trials that were shown, with their times.
        """
        selected = tuple(self._selected_trials(sequence))
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "social-interactive.started",
                started_at,
                {
                    "sequence_id": sequence.sequence_id,
                    "planned_trial_count": len(selected),
                },
            )
        )

        presented_trials = tuple(
            self._present_trial(trial, clock, event_sink) for trial in selected
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
            try:
                started_at = self.monotonic()
                movie.play()
                self._draw_for_duration(
                    movie, trial.presentation_seconds, started_at=started_at
                )
            finally:
                # MovieStim.stop() reloads the file for replay, which costs a
                # full movie load. Each trial owns a disposable movie, so
                # release its decoder and texture instead.
                movie.unload()
            # Clear the last movie frame so the post-trial blank and the next
            # trial's fixation are black, not a frozen frame of footage.
            self.window.color = "black"
            self.window.flip()
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

    def _draw_for_duration(
        self, movie: MovieLike, duration_seconds: float, *, started_at: float
    ) -> None:
        deadline = started_at + duration_seconds
        while (frame_started := self.monotonic()) < deadline:
            movie.draw()
            self.window.flip()
            # Drawing, decoding, and waiting for the screen refresh all consume
            # trial time. Waiting a full frame after them stretches a 15 s
            # trial to ~22 s and freezes the last movie frame on screen.
            frame_deadline = min(frame_started + self.frame_duration_seconds, deadline)
            remaining_seconds = frame_deadline - self.monotonic()
            if remaining_seconds > 0:
                self._wait()(remaining_seconds)

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
class StatusLoggingEventSink:
    """An ``EventSink`` that also writes a status line for the main events.

    Attributes
    ----------
    delegate : EventSink
        The event sink that records the events.
    status : StatusSink
        Receives the status lines.
    """

    delegate: EventSink
    status: StatusSink

    def emit(self, event: RuntimeEvent) -> None:
        """Record one event, and write a status line for a start or end event.

        Parameters
        ----------
        event : RuntimeEvent
            The event.
        """
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
    screen_distance_meters: float = 0.65,
    screen_resolution_pixels: tuple[int, int] = (1920, 1080),
    screen_size_meters: tuple[float, float] = (0.527, 0.296),
    monitor_name: str = "EIZO_EV2480",
    audio_speaker: str | None = None,
    play_sound: bool = True,
    trial_limit: int | None = None,
    debug_render: bool = False,
    status_sink: StatusSink | None = None,
) -> int:
    """Show the Social Interactive task without recording. For previews.

    The demo writes no files. If the configured speaker fails, it continues
    with the default speaker, then without sound.

    Parameters
    ----------
    fullscreen : bool
        True fills the screen. False opens a window of ``window_size``.
    screen : int
        The PsychoPy screen number of the stimulus display.
    window_size : tuple[int, int]
        The window width and height in pixels, when not fullscreen.
    screen_distance_meters : float
        The distance from the eyes of the participant to the screen.
    screen_resolution_pixels : tuple[int, int]
        The screen width and height in pixels.
    screen_size_meters : tuple[float, float]
        The screen width and height in meters.
    monitor_name : str
        The name of the PsychoPy monitor profile.
    audio_speaker : str or None
        The name, or part of the name, of the speaker for stimulus audio.
        None uses the default speaker.
    play_sound : bool
        False plays no stimulus audio.
    trial_limit : int or None
        The maximum number of trials to show. None shows all trials.
    debug_render : bool
        True writes a status line for each stimulus that is drawn.
    status_sink : StatusSink or None
        Receives status messages. None prints them to standard error.

    Returns
    -------
    int
        The exit code: 0 when the demo ends.
    """
    status = status_sink or (
        lambda message: print(message, file=sys.stderr, flush=True)
    )

    status("Importing PsychoPy...")
    from psychopy import core, monitors, prefs, visual

    from aria_et.psychopy.environment import effective_window_size, open_window
    from aria_et.runtime import RecordingEventSink

    effective_size = effective_window_size(
        fullscreen=fullscreen,
        window_size=window_size,
        screen_resolution_pixels=screen_resolution_pixels,
    )
    status(
        "Opening PsychoPy window "
        f"({effective_size[0]}x{effective_size[1]}, fullscreen={fullscreen}, screen={screen})..."
    )
    window = open_window(
        visual_module=visual,
        monitors_module=monitors,
        prefs_module=prefs,
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


def run_social_interactive_session(
    *,
    tracker: TrackerName,
    output_dir: str | Path,
    subject: str,
    tracker_address: str | None = None,
    tracker_serial_number: str | None = None,
    session: str | None = None,
    run: str | None = None,
    fullscreen: bool = False,
    screen: int = 1,
    window_size: tuple[int, int] = (1024, 768),
    screen_distance_meters: float = 0.65,
    screen_resolution_pixels: tuple[int, int] = (1920, 1080),
    screen_size_meters: tuple[float, float] = (0.527, 0.296),
    monitor_name: str = "EIZO_EV2480",
    audio_speaker: str | None = None,
    play_sound: bool = True,
    trial_limit: int | None = None,
    debug_render: bool = False,
    status_sink: StatusSink | None = None,
) -> int:
    """Record one Social Interactive run.

    The run writes its files to
    ``<output_dir>/sub-<subject>/ses-<session>/task-<task>_run-<run>``. See
    ``run_recording_session``.

    Parameters
    ----------
    tracker : TrackerName
        ``"tobii"`` records gaze. ``"none"`` is a dry run without gaze.
    output_dir : str or Path
        The ``sourcedata`` folder.
    subject : str
        The subject label, with or without ``"sub-"``.
    tracker_address : str or None
        The tracker address. None uses the saved tracker, then discovery.
    tracker_serial_number : str or None
        The serial number of the tracker.
    session : str or None
        The session label, with or without ``"ses-"``. None for no session.
    run : str or None
        The run label, with or without ``"run-"``. None gives the next free
        run number.
    fullscreen : bool
        True fills the screen. False opens a window of ``window_size``.
    screen : int
        The PsychoPy screen number of the stimulus display.
    window_size : tuple[int, int]
        The window width and height in pixels, when not fullscreen.
    screen_distance_meters : float
        The distance from the eyes of the participant to the screen.
    screen_resolution_pixels : tuple[int, int]
        The screen width and height in pixels.
    screen_size_meters : tuple[float, float]
        The screen width and height in meters.
    monitor_name : str
        The name of the PsychoPy monitor profile.
    audio_speaker : str or None
        The name, or part of the name, of the speaker for stimulus audio.
        None uses the default speaker.
    play_sound : bool
        False plays no stimulus audio.
    trial_limit : int or None
        The maximum number of trials to show. None shows all trials.
    debug_render : bool
        True writes a status line for each stimulus that is drawn.
    status_sink : StatusSink or None
        Receives status messages. None prints them to standard error.

    Returns
    -------
    int
        The exit code of ``run_recording_session``.
    """
    from aria_et.session import run_recording_session

    status = status_sink or (
        lambda message: print(message, file=sys.stderr, flush=True)
    )

    def present(event_sink: EventSink) -> None:  # numpydoc ignore=GL08
        status("Importing PsychoPy...")
        from psychopy import core, monitors, prefs, visual

        from aria_et.psychopy.environment import effective_window_size, open_window

        effective_size = effective_window_size(
            fullscreen=fullscreen,
            window_size=window_size,
            screen_resolution_pixels=screen_resolution_pixels,
        )
        status(
            "Opening PsychoPy window "
            f"({effective_size[0]}x{effective_size[1]}, fullscreen={fullscreen}, screen={screen})..."
        )
        window = open_window(
            visual_module=visual,
            monitors_module=monitors,
            prefs_module=prefs,
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
            status("Running Social Interactive session.")
            presenter = PsychoPySocialInteractivePresenter(
                window=window,
                play_sound=play_sound,
                trial_limit=trial_limit,
                render_status=status if debug_render else None,
            )
            presenter.present(
                build_social_interactive_sequence(),
                PsychoPyClock(core.Clock()),
                StatusLoggingEventSink(event_sink, status),
            )
            status("Social Interactive session finished.")
        finally:
            status("Closing PsychoPy window...")
            window.close()

    return run_recording_session(
        task_id="social-interactive",
        tracker=tracker,
        tracker_address=tracker_address,
        tracker_serial_number=tracker_serial_number,
        output_dir=output_dir,
        bids=bids_session_metadata(subject, session, run),
        stimulus_display=stimulus_display_metadata(
            screen=screen,
            fullscreen=fullscreen,
            window_size=window_size,
            screen_distance_meters=screen_distance_meters,
            screen_resolution_pixels=screen_resolution_pixels,
            screen_size_meters=screen_size_meters,
        ),
        present=present,
    )
