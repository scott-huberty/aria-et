"""PsychoPy adapter for Activity Monitoring presentation."""

from __future__ import annotations

import math
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.resources import as_file
from pathlib import Path
from typing import TYPE_CHECKING

from aria_et.activity_monitoring import (
    ActivityMonitoringSequence,
    ActivityMonitoringTrial,
    build_activity_monitoring_sequence,
)
from aria_et.protocols import (
    DrawableLike,
    MovieLike,
    SoundLike,
    StatusSink,
    Wait,
    WindowLike,
)
from aria_et.psychopy.environment import (
    PsychoPyClock,
    bids_session_metadata,
    stimulus_display_metadata,
)
from aria_et.runtime import Clock, EventSink, RuntimeEvent

if TYPE_CHECKING:
    from aria_et.session import TrackerName


__all__ = [
    "ActivityMonitoringRunResult",
    "ImageFactory",
    "MovieFactory",
    "PresentedActivityMonitoringTrial",
    "PsychoPyActivityMonitoringPresenter",
    "SoundFactory",
    "StatusLoggingEventSink",
    "run_activity_monitoring_demo",
    "run_activity_monitoring_session",
    "video_duration_seconds",
]


ImageFactory = Callable[[WindowLike, str], DrawableLike]
MovieFactory = Callable[[WindowLike, str], MovieLike]
SoundFactory = Callable[[str], SoundLike]


def video_duration_seconds(path: str) -> float:
    """Read the video endpoint for the bundled constant-frame-rate AM assets.

    MovieStim reports container duration, which can include an audio tail after
    the last video frame. Do not ask the movie decoder for frames in that tail.

    Parameters
    ----------
    path : str
        The video file.

    Returns
    -------
    float
        The duration of the video stream in seconds.

    Raises
    ------
    ValueError
        If the file cannot be read or has no frame count or rate.
    """
    import cv2

    capture = cv2.VideoCapture(path)
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not read video metadata: {path}")
        frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        frame_rate = capture.get(cv2.CAP_PROP_FPS)
        if not all(
            math.isfinite(value) and value > 0 for value in (frame_count, frame_rate)
        ):
            raise ValueError(f"Invalid video frame count or frame rate: {path}")
        duration = frame_count / frame_rate
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError(f"Invalid video duration: {path}")
        return duration
    finally:
        capture.release()


@dataclass(frozen=True)
class PresentedActivityMonitoringTrial:
    """One Activity Monitoring trial that was shown.

    Attributes
    ----------
    trial_id : str
        The trial id.
    media_type : str
        ``"dynamic-video"`` or ``"static-image"``.
    gaze_condition : str
        ``"activity-gaze"`` or ``"mutual-gaze"``.
    started_at : float
        The start time, from the clock of the task.
    ended_at : float
        The end time, from the clock of the task.
    """

    trial_id: str
    media_type: str
    gaze_condition: str
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class ActivityMonitoringRunResult:
    """The result of one Activity Monitoring presentation.

    Attributes
    ----------
    sequence_id : str
        The sequence id.
    presented_trials : tuple[PresentedActivityMonitoringTrial, ...]
        The trials that were shown, in presentation order.
    started_at : float
        The start time, from the clock of the task.
    ended_at : float
        The end time, from the clock of the task.
    """

    sequence_id: str
    presented_trials: tuple[PresentedActivityMonitoringTrial, ...]
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class PsychoPyActivityMonitoringPresenter:
    """Shows the Activity Monitoring sequence in a PsychoPy window.

    Each trial shows a fixation blank, then a video or an image with its
    soundtrack, then a blank. A blank inter-trial interval follows each
    trial except the last.

    Attributes
    ----------
    window : WindowLike
        The PsychoPy window.
    image_factory : ImageFactory or None
        Makes an image stimulus. None uses ``psychopy.visual.ImageStim``.
    movie_factory : MovieFactory or None
        Makes a movie stimulus. None uses ``psychopy.visual.MovieStim``.
    sound_factory : SoundFactory or None
        Makes a sound. None uses ``psychopy.sound.Sound``.
    wait : Wait or None
        Waits a number of seconds. None uses ``psychopy.core.wait``.
    play_sound : bool
        False plays no stimulus audio.
    audio_speaker : str or None
        The name, or part of the name, of the speaker for stimulus audio.
        None uses the default speaker.
    continue_without_sound_on_error : bool
        True continues without sound if a sound cannot play.
    sound_error_sink : StatusSink or None
        Receives a warning when a sound cannot play.
    trial_limit : int or None
        The maximum number of trials to show. None shows all trials.
    frame_duration_seconds : float
        The duration of one frame of the draw loop.
    inter_trial_interval_seconds : float
        The blank interval between trials.
    render_status : StatusSink or None
        Receives a status line for each stimulus that is drawn. None writes
        nothing.
    monotonic : Callable[[], float]
        Gives the time in seconds for the draw loop. For tests.
    movie_duration_reader : Callable[[str], float]
        Reads the video duration of a movie file. For tests.
    """

    window: WindowLike
    image_factory: ImageFactory | None = None
    movie_factory: MovieFactory | None = None
    sound_factory: SoundFactory | None = None
    wait: Wait | None = None
    play_sound: bool = True
    audio_speaker: str | None = None
    continue_without_sound_on_error: bool = False
    sound_error_sink: StatusSink | None = None
    trial_limit: int | None = None
    frame_duration_seconds: float = 1 / 30
    inter_trial_interval_seconds: float = 1.0
    render_status: StatusSink | None = None
    monotonic: Callable[[], float] = time.perf_counter
    movie_duration_reader: Callable[[str], float] = video_duration_seconds
    _active_sounds: list[SoundLike] = field(
        default_factory=list, init=False, repr=False
    )

    def present(
        self,
        sequence: ActivityMonitoringSequence,
        clock: Clock,
        event_sink: EventSink,
    ) -> ActivityMonitoringRunResult:
        """Show the trials and emit their events.

        Parameters
        ----------
        sequence : ActivityMonitoringSequence
            The trial sequence to show.
        clock : Clock
            Gives the event times.
        event_sink : EventSink
            Receives the events of the task.

        Returns
        -------
        ActivityMonitoringRunResult
            The trials that were shown, with their times.
        """
        selected_trials = self._selected_trials(sequence)
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "activity-monitoring.started",
                started_at,
                {
                    "sequence_id": sequence.sequence_id,
                    "planned_trial_count": len(selected_trials),
                },
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
        if trial.presentation_seconds is None:
            raise ValueError("Static-image trials require a presentation duration.")
        self._play_soundtrack(trial)
        self._render_status(
            f"Image trial: {trial.trial_id} {trial.stimulus.media.name}"
        )
        with as_file(trial.stimulus.media) as media_path:
            image = self._image_factory()(self.window, str(media_path))
            try:
                self._draw_for_duration(image, trial.presentation_seconds)
            finally:
                self._stop_active_sounds()

    def _present_movie_trial(self, trial: ActivityMonitoringTrial) -> None:
        self._render_status(
            f"Movie trial: {trial.trial_id} {trial.stimulus.media.name}"
        )
        with as_file(trial.stimulus.media) as media_path:
            duration = self.movie_duration_reader(str(media_path))
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError(f"Invalid video duration: {media_path}")
            movie = self._movie_factory()(self.window, str(media_path))
            try:
                started_at = self.monotonic()
                movie.play()
                self._draw_for_duration(movie, duration, started_at=started_at)
            finally:
                # MovieStim.stop() reloads the file for replay. Each trial owns
                # a disposable movie, so release its decoder and texture instead.
                movie.unload()
            self.window.color = "black"
            self.window.flip()

    def _draw_for_duration(
        self,
        drawable: DrawableLike,
        duration_seconds: float,
        *,
        started_at: float | None = None,
    ) -> None:
        deadline = (
            self.monotonic() if started_at is None else started_at
        ) + duration_seconds
        while (frame_started := self.monotonic()) < deadline:
            drawable.draw()
            self.window.flip()
            # Drawing, decoding, and waiting for the screen refresh all consume
            # trial time. Waiting a full frame after them extends the stimulus
            # and can drive a movie reader past its last available video frame.
            frame_deadline = min(frame_started + self.frame_duration_seconds, deadline)
            remaining_seconds = frame_deadline - self.monotonic()
            if remaining_seconds > 0:
                self._wait()(remaining_seconds)

    def _play_soundtrack(self, trial: ActivityMonitoringTrial) -> None:
        if not self.play_sound or trial.stimulus.soundtrack is None:
            return

        with as_file(trial.stimulus.soundtrack) as soundtrack_path:
            try:
                sound_object = self._sound_factory()(str(soundtrack_path))
                sound_object.play()
            except BaseException as error:
                from aria_et.psychopy.environment import should_reraise_sound_error

                if (
                    not self.continue_without_sound_on_error
                    or should_reraise_sound_error(error)
                ):
                    raise
                self._warn_sound_unavailable(error)
                return
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
            noAudio=not self.play_sound,
            audioDevice=self.audio_speaker if self.play_sound else None,
        )

    def _sound_factory(self) -> SoundFactory:
        if self.sound_factory is not None:
            return self.sound_factory

        from psychopy import sound

        return lambda path: sound.Sound(path, speaker=self.audio_speaker)

    def _wait(self) -> Wait:
        if self.wait is not None:
            return self.wait

        from psychopy import core

        return core.wait

    def _render_status(self, message: str) -> None:
        if self.render_status is not None:
            self.render_status(message)

    def _warn_sound_unavailable(self, error: BaseException) -> None:
        if self.sound_error_sink is None:
            return
        from aria_et.psychopy.environment import warn_demo_sound_unavailable

        warn_demo_sound_unavailable(sink=self.sound_error_sink, error=error)


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
    """Show the Activity Monitoring task without recording. For previews.

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

    from aria_et.psychopy.environment import (
        demo_movie_factory,
        effective_window_size,
        open_window,
        resolve_audio_speaker,
    )
    from aria_et.runtime import RecordingEventSink

    audio_speaker = resolve_audio_speaker(audio_speaker)

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
        status("Running Activity Monitoring demo.")
        presenter = PsychoPyActivityMonitoringPresenter(
            window=window,
            movie_factory=demo_movie_factory(
                visual_module=visual,
                prefs_module=prefs,
                status_sink=status,
                play_sound=play_sound,
                audio_speaker=audio_speaker,
            ),
            play_sound=play_sound,
            audio_speaker=audio_speaker,
            continue_without_sound_on_error=True,
            sound_error_sink=status,
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
    tracker: TrackerName,
    tracker_address: str | None = None,
    tracker_serial_number: str | None = None,
    output_dir: str | Path,
    subject: str,
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
    """Record one Activity Monitoring run.

    The run writes its files to
    ``<output_dir>/sub-<subject>/ses-<session>/task-<task>_run-<run>``. See
    ``run_recording_session``.

    Parameters
    ----------
    tracker : TrackerName
        ``"tobii"`` records gaze. ``"none"`` is a dry run without gaze.
    tracker_address : str or None
        The tracker address. None uses the saved tracker, then discovery.
    tracker_serial_number : str or None
        The serial number of the tracker.
    output_dir : str or Path
        The ``sourcedata`` folder.
    subject : str
        The subject label, with or without ``"sub-"``.
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

        from aria_et.psychopy.environment import (
            effective_window_size,
            open_window,
            resolve_audio_speaker,
        )

        speaker = resolve_audio_speaker(audio_speaker)

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
            audio_speaker=speaker,
        )
        try:
            status("Running Activity Monitoring session.")
            presenter = PsychoPyActivityMonitoringPresenter(
                window=window,
                play_sound=play_sound,
                audio_speaker=speaker,
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
