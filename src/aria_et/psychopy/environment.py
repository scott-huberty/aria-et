"""Shared PsychoPy environment setup."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


def warn_demo_sound_unavailable(*, sink: Any, error: BaseException) -> None:
    sink(
        "Sound playback is disabled for this demo because PsychoPy could not "
        f"initialize the configured speaker ({error}). Use --no-sound to silence "
        "this warning, or connect/select the configured speaker before running "
        "with sound."
    )


def should_reraise_sound_error(error: BaseException) -> bool:
    return isinstance(error, (KeyboardInterrupt, SystemExit, GeneratorExit))


def demo_sound_factory(
    *,
    sound_module: Any,
    prefs_module: Any,
    status_sink: Any,
) -> Any:
    def make_sound(path: str) -> Any:
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
    visual_module: Any,
    prefs_module: Any,
    status_sink: Any,
    play_sound: bool,
    audio_speaker: str | None,
) -> Any:
    def make_movie(window: Any, path: str) -> Any:
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
    return screen_resolution_pixels if fullscreen else window_size


def configure_monitor(
    *,
    monitors_module: Any,
    monitor_name: str,
    screen_distance_meters: float,
    screen_resolution_pixels: tuple[int, int],
    screen_size_meters: tuple[float, float],
) -> object:
    monitor = monitors_module.Monitor(
        monitor_name,
        width=screen_size_meters[0] * 100,
        distance=screen_distance_meters * 100,
    )
    monitor.setSizePix(screen_resolution_pixels)
    monitor.saveMon()
    return monitor


def available_speaker_names() -> list[str]:
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
    prefs_module: Any,
    audio_speaker: str | None,
    speaker_names: Callable[[], Sequence[str]] = available_speaker_names,
) -> str | None:
    audio_speaker = resolve_audio_speaker(audio_speaker, speaker_names=speaker_names)
    if audio_speaker:
        prefs_module.hardware["audioDevice"] = [audio_speaker]
    return audio_speaker


def open_window(
    *,
    visual_module: Any,
    monitors_module: Any,
    prefs_module: Any,
    fullscreen: bool,
    screen: int,
    window_size: tuple[int, int],
    screen_distance_meters: float,
    screen_resolution_pixels: tuple[int, int],
    screen_size_meters: tuple[float, float],
    monitor_name: str,
    audio_speaker: str | None,
    speaker_names: Callable[[], Sequence[str]] = available_speaker_names,
) -> object:
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
