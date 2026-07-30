"""Shared PsychoPy environment setup."""

from __future__ import annotations

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


def configure_audio(
    *,
    prefs_module: Any,
    audio_speaker: str | None,
) -> None:
    if audio_speaker:
        prefs_module.hardware["audioDevice"] = [audio_speaker]


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
) -> object:
    configure_audio(prefs_module=prefs_module, audio_speaker=audio_speaker)
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
