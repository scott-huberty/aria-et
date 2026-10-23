"""PsychoPy adapter for Pupillary Light Reflex presentation."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from importlib.abc import Traversable
from importlib.resources import as_file
from pathlib import Path
from typing import TYPE_CHECKING

from aria_et.protocols import DrawableLike, SoundLike, StatusSink, Wait, WindowLike
from aria_et.psychopy.environment import (
    PsychoPyClock,
    bids_session_metadata,
    stimulus_display_metadata,
)
from aria_et.pupillary_light_reflex import (
    PupillaryLightReflexBlock,
    PupillaryLightReflexSequence,
    PupillaryLightReflexTrial,
    build_pupillary_light_reflex_sequence,
)
from aria_et.runtime import Clock, EventSink, RuntimeEvent

if TYPE_CHECKING:
    from aria_et.session import TrackerName


__all__ = [
    "ImageFactory",
    "PresentedPupillaryLightReflexTrial",
    "PsychoPyPupillaryLightReflexPresenter",
    "PupillaryLightReflexRunResult",
    "SoundFactory",
    "StatusLoggingEventSink",
    "run_pupillary_light_reflex_demo",
    "run_pupillary_light_reflex_session",
]


ImageFactory = Callable[[WindowLike, str], DrawableLike]
SoundFactory = Callable[[str], SoundLike]


@dataclass(frozen=True)
class PresentedPupillaryLightReflexTrial:
    """One Pupillary Light Reflex trial that was shown.

    Attributes
    ----------
    trial_id : str
        The trial id.
    block_id : str
        The block id.
    stimulus_id : str
        The stimulus id.
    started_at : float
        The start time, from the clock of the task.
    ended_at : float
        The end time, from the clock of the task.
    """

    trial_id: str
    block_id: str
    stimulus_id: str
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class PupillaryLightReflexRunResult:
    """The result of one Pupillary Light Reflex presentation.

    Attributes
    ----------
    sequence_id : str
        The sequence id.
    presented_trials : tuple[PresentedPupillaryLightReflexTrial, ...]
        The trials that were shown, in presentation order.
    started_at : float
        The start time, from the clock of the task.
    ended_at : float
        The end time, from the clock of the task.
    """

    sequence_id: str
    presented_trials: tuple[PresentedPupillaryLightReflexTrial, ...]
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class PsychoPyPupillaryLightReflexPresenter:
    """Shows the Pupillary Light Reflex sequence in a PsychoPy window.

    Each trial plays a frame animation with one flash, and its sound. The
    trial limit counts blocks; each block has one trial.

    Attributes
    ----------
    window : WindowLike
        The PsychoPy window.
    image_factory : ImageFactory or None
        Makes an image stimulus. None uses ``psychopy.visual.ImageStim``.
    sound_factory : SoundFactory or None
        Makes a sound. None uses ``psychopy.sound.Sound``.
    wait : Wait or None
        Waits a number of seconds. None uses ``psychopy.core.wait``.
    play_sound : bool
        False plays no stimulus audio.
    continue_without_sound_on_error : bool
        True continues without sound if a sound cannot play.
    sound_error_sink : StatusSink or None
        Receives a warning when a sound cannot play.
    trial_limit : int or None
        The maximum number of trials to show. None shows all trials.
    frame_duration_seconds : float
        The duration of one frame of the draw loop.
    render_status : StatusSink or None
        Receives a status line for each stimulus that is drawn. None writes
        nothing.
    """

    window: WindowLike
    image_factory: ImageFactory | None = None
    sound_factory: SoundFactory | None = None
    wait: Wait | None = None
    play_sound: bool = True
    continue_without_sound_on_error: bool = False
    sound_error_sink: StatusSink | None = None
    trial_limit: int | None = None
    frame_duration_seconds: float = 1 / 30
    render_status: StatusSink | None = None
    _active_sounds: list[SoundLike] = field(
        default_factory=list, init=False, repr=False
    )

    def present(
        self,
        sequence: PupillaryLightReflexSequence,
        clock: Clock,
        event_sink: EventSink,
    ) -> PupillaryLightReflexRunResult:
        """Show the trials and emit their events.

        Parameters
        ----------
        sequence : PupillaryLightReflexSequence
            The trial sequence to show.
        clock : Clock
            Gives the event times.
        event_sink : EventSink
            Receives the events of the task.

        Returns
        -------
        PupillaryLightReflexRunResult
            The trials that were shown, with their times.
        """
        selected_blocks = self._selected_blocks(sequence)
        image_cache = self._prepare_image_cache(selected_blocks)
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "pupillary-light-reflex.started",
                started_at,
                {
                    "sequence_id": sequence.sequence_id,
                    "planned_trial_count": sum(
                        len(block.trials) for block in selected_blocks
                    ),
                },
            )
        )

        presented_trials = []
        for block in selected_blocks:
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
        blocks: Sequence[PupillaryLightReflexBlock],
    ) -> dict[str, tuple[DrawableLike, ...]]:
        cache = {}
        for block in blocks:
            for trial in block.trials:
                if trial.stimulus_id in cache:
                    continue
                self._render_status(f"PLR preload: {trial.stimulus_id}")
                cache[trial.stimulus_id] = self._prepare_images(trial.stimulus.frames)
        return cache

    def _prepare_images(
        self, frames: tuple[Traversable, ...]
    ) -> tuple[DrawableLike, ...]:
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
            try:
                sound_object = self._sound_factory()(str(sound_path))
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

    def _selected_blocks(
        self,
        sequence: PupillaryLightReflexSequence,
    ) -> tuple[PupillaryLightReflexBlock, ...]:
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
    """Show the Pupillary Light Reflex task without recording. For previews.

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
        status("Running Pupillary Light Reflex demo.")
        presenter = PsychoPyPupillaryLightReflexPresenter(
            window=window,
            play_sound=play_sound,
            continue_without_sound_on_error=True,
            sound_error_sink=status,
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


def run_pupillary_light_reflex_session(
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
    """Record one Pupillary Light Reflex run.

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
            status("Running Pupillary Light Reflex session.")
            presenter = PsychoPyPupillaryLightReflexPresenter(
                window=window,
                play_sound=play_sound,
                trial_limit=trial_limit,
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
