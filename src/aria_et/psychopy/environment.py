"""Shared PsychoPy environment setup."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from aria_et.protocols import (
    ClockLike,
    ClosableWindow,
    MovieLike,
    PsychoPyModule,
    SoundLike,
    StatusSink,
    WindowLike,
)

if TYPE_CHECKING:
    from aria_et.session import BidsSessionMetadata, StimulusDisplayMetadata


__all__ = [
    "PsychoPyClock",
    "available_speaker_names",
    "bids_session_metadata",
    "configure_audio",
    "configure_monitor",
    "demo_movie_factory",
    "demo_sound_factory",
    "effective_window_size",
    "open_window",
    "resolve_audio_speaker",
    "should_reraise_sound_error",
    "stimulus_display_metadata",
    "warn_demo_sound_unavailable",
]


@dataclass
class PsychoPyClock:
    """The runtime ``Clock``, read from a PsychoPy clock."""

    psychopy_clock: ClockLike

    def now(self) -> float:
        """Return the time of the PsychoPy clock.

        Returns
        -------
        float
            The time in seconds.
        """
        return self.psychopy_clock.getTime()


def warn_demo_sound_unavailable(*, sink: StatusSink, error: BaseException) -> None:
    """Tell the operator that the demo continues without sound.

    Parameters
    ----------
    sink : StatusSink
        Receives the warning.
    error : BaseException
        The error from the sound backend.
    """
    sink(
        "Sound playback is disabled for this demo because PsychoPy could not "
        f"initialize the configured speaker ({error}). Use --no-sound to silence "
        "this warning, or connect/select the configured speaker before running "
        "with sound."
    )


def should_reraise_sound_error(error: BaseException) -> bool:
    """Return True for an error that must stop the program.

    Parameters
    ----------
    error : BaseException
        The error from the sound backend.

    Returns
    -------
    bool
        True for ``KeyboardInterrupt``, ``SystemExit`` and ``GeneratorExit``.
    """
    return isinstance(error, (KeyboardInterrupt, SystemExit, GeneratorExit))


def demo_sound_factory(
    *,
    sound_module: PsychoPyModule,
    prefs_module: PsychoPyModule,
    status_sink: StatusSink,
) -> Callable[[str], SoundLike]:
    """Return a sound factory that falls back to the default speaker.

    Parameters
    ----------
    sound_module : PsychoPyModule
        ``psychopy.sound``.
    prefs_module : PsychoPyModule
        ``psychopy.prefs``.
    status_sink : StatusSink
        Receives a message when the configured speaker fails.

    Returns
    -------
    Callable[[str], SoundLike]
        The factory. It takes the path of a sound file.
    """

    def make_sound(path: str) -> SoundLike:  # numpydoc ignore=GL08
        try:
            return sound_module.Sound(path)
        except BaseException as error:
            if should_reraise_sound_error(error):
                raise
            prefs_module.hardware["audioDevice"] = ["default"]
            status_sink(
                "Configured speaker is unavailable; trying PsychoPy's default "
                f"speaker instead ({error})."
            )
            return sound_module.Sound(path)

    return make_sound


def demo_movie_factory(
    *,
    visual_module: PsychoPyModule,
    prefs_module: PsychoPyModule,
    status_sink: StatusSink,
    play_sound: bool,
    audio_speaker: str | None,
) -> Callable[[WindowLike, str], MovieLike]:
    """Return a movie factory that falls back to the default speaker.

    If the default speaker also fails, the movie plays without audio.

    Parameters
    ----------
    visual_module : PsychoPyModule
        ``psychopy.visual``.
    prefs_module : PsychoPyModule
        ``psychopy.prefs``.
    status_sink : StatusSink
        Receives a message when the configured speaker fails.
    play_sound : bool
        False makes movies without audio.
    audio_speaker : str or None
        The configured speaker.

    Returns
    -------
    Callable[[WindowLike, str], MovieLike]
        The factory. It takes a window and the path of a movie file.
    """

    def make_movie(window: WindowLike, path: str) -> MovieLike:  # numpydoc ignore=GL08
        if not play_sound:
            return visual_module.MovieStim(window, filename=path, noAudio=True)

        try:
            return visual_module.MovieStim(
                window,
                filename=path,
                noAudio=False,
                audioDevice=audio_speaker,
            )
        except BaseException as error:
            if should_reraise_sound_error(error):
                raise
            prefs_module.hardware["audioDevice"] = ["default"]
            status_sink(
                "Configured speaker is unavailable; trying PsychoPy's default "
                f"speaker instead ({error})."
            )

        try:
            return visual_module.MovieStim(
                window,
                filename=path,
                noAudio=False,
                audioDevice=None,
            )
        except BaseException as error:
            if should_reraise_sound_error(error):
                raise
            warn_demo_sound_unavailable(sink=status_sink, error=error)
            return visual_module.MovieStim(window, filename=path, noAudio=True)

    return make_movie


def effective_window_size(
    *,
    fullscreen: bool,
    window_size: tuple[int, int],
    screen_resolution_pixels: tuple[int, int],
) -> tuple[int, int]:
    """Return the size of the PsychoPy window.

    Parameters
    ----------
    fullscreen : bool
        True fills the screen. False opens a window of ``window_size``.
    window_size : tuple[int, int]
        The window width and height in pixels, when not fullscreen.
    screen_resolution_pixels : tuple[int, int]
        The screen width and height in pixels.

    Returns
    -------
    tuple[int, int]
        The screen resolution if fullscreen, else ``window_size``.
    """
    return screen_resolution_pixels if fullscreen else window_size


def configure_monitor(
    *,
    monitors_module: PsychoPyModule,
    monitor_name: str,
    screen_distance_meters: float,
    screen_resolution_pixels: tuple[int, int],
    screen_size_meters: tuple[float, float],
) -> object:
    """Make and save the PsychoPy monitor profile.

    Parameters
    ----------
    monitors_module : PsychoPyModule
        ``psychopy.monitors``.
    monitor_name : str
        The name of the PsychoPy monitor profile.
    screen_distance_meters : float
        The distance from the eyes of the participant to the screen.
    screen_resolution_pixels : tuple[int, int]
        The screen width and height in pixels.
    screen_size_meters : tuple[float, float]
        The screen width and height in meters.

    Returns
    -------
    object
        The PsychoPy monitor.
    """
    monitor = monitors_module.Monitor(
        monitor_name,
        width=screen_size_meters[0] * 100,
        distance=screen_distance_meters * 100,
    )
    monitor.setSizePix(screen_resolution_pixels)
    monitor.saveMon()
    return monitor


def available_speaker_names() -> list[str]:
    """Return the names of the speakers that PsychoPy finds.

    Returns
    -------
    list[str]
        The speaker names.
    """
    from psychopy.hardware.speaker import SpeakerDevice

    return [device["deviceName"] for device in SpeakerDevice.getAvailableDevices()]


def resolve_audio_speaker(
    audio_speaker: str | None,
    *,
    speaker_names: Callable[[], Sequence[str]] = available_speaker_names,
) -> str | None:
    """Expand a configured speaker name to the full name PsychoPy reports.

    PsychoPy matches speaker names exactly, and an unmatched name silently falls
    back to the first speaker found (e.g. "EV2480" vs. "EV2480 (HD Audio Driver
    for Display Audio)"). Accept a unique case-insensitive substring instead.

    Parameters
    ----------
    audio_speaker : str or None
        The configured name, or part of it. None or an empty name is
        returned unchanged.
    speaker_names : Callable[[], Sequence[str]]
        Lists the speaker names that PsychoPy finds. For tests.

    Returns
    -------
    str or None
        The full speaker name if exactly one speaker matches. Otherwise
        ``audio_speaker`` unchanged.
    """
    if not audio_speaker:
        return audio_speaker
    try:
        names = list(speaker_names())
    except Exception:  # noqa: BLE001 - leave unresolved; PsychoPy reports later
        return audio_speaker
    if audio_speaker in names:
        return audio_speaker
    matches = [name for name in names if audio_speaker.casefold() in name.casefold()]
    if len(matches) == 1:
        return matches[0]
    return audio_speaker


def configure_audio(
    *,
    prefs_module: PsychoPyModule,
    audio_speaker: str | None,
    speaker_names: Callable[[], Sequence[str]] = available_speaker_names,
) -> str | None:
    """Set the PsychoPy audio device to the configured speaker.

    Parameters
    ----------
    prefs_module : PsychoPyModule
        ``psychopy.prefs``.
    audio_speaker : str or None
        The name, or part of the name, of the speaker for stimulus audio.
        None uses the default speaker.
    speaker_names : Callable[[], Sequence[str]]
        Lists the speaker names that PsychoPy finds. For tests.

    Returns
    -------
    str or None
        The speaker name after ``resolve_audio_speaker``.
    """
    audio_speaker = resolve_audio_speaker(audio_speaker, speaker_names=speaker_names)
    if audio_speaker:
        prefs_module.hardware["audioDevice"] = [audio_speaker]
    return audio_speaker


def open_window(
    *,
    visual_module: PsychoPyModule,
    monitors_module: PsychoPyModule,
    prefs_module: PsychoPyModule,
    fullscreen: bool,
    screen: int,
    window_size: tuple[int, int],
    screen_distance_meters: float,
    screen_resolution_pixels: tuple[int, int],
    screen_size_meters: tuple[float, float],
    monitor_name: str,
    audio_speaker: str | None,
    speaker_names: Callable[[], Sequence[str]] = available_speaker_names,
) -> ClosableWindow:
    """Set the audio device and the monitor profile, and open the PsychoPy window.

    Parameters
    ----------
    visual_module : PsychoPyModule
        ``psychopy.visual``.
    monitors_module : PsychoPyModule
        ``psychopy.monitors``.
    prefs_module : PsychoPyModule
        ``psychopy.prefs``.
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
    speaker_names : Callable[[], Sequence[str]]
        Lists the speaker names that PsychoPy finds. For tests.

    Returns
    -------
    ClosableWindow
        The open window. The caller must close it.
    """
    configure_audio(
        prefs_module=prefs_module,
        audio_speaker=audio_speaker,
        speaker_names=speaker_names,
    )
    monitor = configure_monitor(
        monitors_module=monitors_module,
        monitor_name=monitor_name,
        screen_distance_meters=screen_distance_meters,
        screen_resolution_pixels=screen_resolution_pixels,
        screen_size_meters=screen_size_meters,
    )
    return visual_module.Window(
        size=effective_window_size(
            fullscreen=fullscreen,
            window_size=window_size,
            screen_resolution_pixels=screen_resolution_pixels,
        ),
        fullscr=fullscreen,
        screen=screen,
        units="pix",
        color="black",
        monitor=monitor,
    )


def bids_session_metadata(
    subject: str, session: str | None, run: str | None
) -> BidsSessionMetadata:
    """Return the BIDS labels of one run.

    Parameters
    ----------
    subject : str
        The subject label, with or without ``"sub-"``.
    session : str or None
        The session label, with or without ``"ses-"``. None for no session.
    run : str or None
        The run label, with or without ``"run-"``. None gives the next free
        run number.

    Returns
    -------
    BidsSessionMetadata
        The labels.
    """
    from aria_et.session import BidsSessionMetadata

    return BidsSessionMetadata(subject=subject, session=session, run=run)


def stimulus_display_metadata(
    *,
    screen: int,
    fullscreen: bool,
    window_size: tuple[int, int],
    screen_distance_meters: float,
    screen_resolution_pixels: tuple[int, int],
    screen_size_meters: tuple[float, float],
) -> StimulusDisplayMetadata:
    """Return the display settings to write to ``session.json``.

    Parameters
    ----------
    screen : int
        The PsychoPy screen number of the stimulus display.
    fullscreen : bool
        True fills the screen. False opens a window of ``window_size``.
    window_size : tuple[int, int]
        The window width and height in pixels, when not fullscreen.
    screen_distance_meters : float
        The distance from the eyes of the participant to the screen.
    screen_resolution_pixels : tuple[int, int]
        The screen width and height in pixels.
    screen_size_meters : tuple[float, float]
        The screen width and height in meters.

    Returns
    -------
    StimulusDisplayMetadata
        The settings. The window size is the screen resolution if
        fullscreen.
    """
    from aria_et.session import StimulusDisplayMetadata

    return StimulusDisplayMetadata(
        screen_distance_meters=screen_distance_meters,
        screen_resolution_pixels=screen_resolution_pixels,
        screen_size_meters=screen_size_meters,
        psychopy_screen=screen,
        fullscreen=fullscreen,
        window_size_pixels=screen_resolution_pixels if fullscreen else window_size,
    )
