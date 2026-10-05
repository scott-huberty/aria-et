"""User configuration for ARIA eye-tracking commands."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli as tomllib  # we pin to py 3.10 until tobii ships new SDK wheels.

DEFAULT_DATA_DIR_NAME = "aria-et-data"
DEFAULT_ETM_SCREEN = 2
DEFAULT_PSYCHOPY_SCREEN = 1
DEFAULT_EIZO_SCREEN_DISTANCE_METERS = 0.65
DEFAULT_EIZO_SCREEN_RESOLUTION = "1920x1080"
DEFAULT_EIZO_SCREEN_SIZE_METERS = "0.527x0.296"
DEFAULT_MONITOR_NAME = "EIZO_EV2480"
DEFAULT_AUDIO_SPEAKER = "EV2480"


@dataclass(frozen=True)
class AriaEtConfig:
    data_root: Path = Path.home() / DEFAULT_DATA_DIR_NAME
    etm_screen: int = DEFAULT_ETM_SCREEN
    psychopy_screen: int = DEFAULT_PSYCHOPY_SCREEN
    screen_distance_meters: float = DEFAULT_EIZO_SCREEN_DISTANCE_METERS
    screen_resolution: str = DEFAULT_EIZO_SCREEN_RESOLUTION
    screen_size_meters: str = DEFAULT_EIZO_SCREEN_SIZE_METERS
    monitor_name: str = DEFAULT_MONITOR_NAME
    audio_speaker: str | None = DEFAULT_AUDIO_SPEAKER
    eye_tracker_manager: str | None = None
    tracker_address: str | None = None
    tracker_serial_number: str | None = None


# Keys accepted by set_config/unset_config, mapped to the type their value is
# coerced to before it is written.
CONFIG_KEYS: dict[str, type] = {
    "data.root": Path,
    "display.psychopy_screen": int,
    "display.etm_screen": int,
    "display.screen_resolution": str,
    "display.screen_size_meters": str,
    "display.screen_distance_meters": float,
    "display.monitor_name": str,
    "audio.speaker": str,
    "tobii.eye_tracker_manager": str,
    "tobii.address": str,
    "tobii.serial_number": str,
}


def default_config_path() -> Path:
    return Path.home() / ".aria-et" / "config.toml"


def default_config_text(config: AriaEtConfig | None = None) -> str:
    config = config or AriaEtConfig(
        data_root=Path.home() / DEFAULT_DATA_DIR_NAME,
        audio_speaker=DEFAULT_AUDIO_SPEAKER,
    )
    audio_speaker = config.audio_speaker or DEFAULT_AUDIO_SPEAKER
    lines = [
        "[data]",
        f"root = '{config.data_root}'",
        "",
        "[display]",
        f"psychopy_screen = {config.psychopy_screen}",
        f"etm_screen = {config.etm_screen}",
        f"screen_resolution = '{config.screen_resolution}'",
        f"screen_size_meters = '{config.screen_size_meters}'",
        f"screen_distance_meters = {config.screen_distance_meters}",
        f"monitor_name = '{config.monitor_name}'",
        "",
        "[audio]",
        f"speaker = '{audio_speaker}'",
        "",
        "[tobii]",
        # TODO: Change this default when we get the Production Windows Laptop.
        "# eye_tracker_manager = '/Applications/TobiiProEyeTrackerManager.app/Contents/MacOS/TobiiProEyeTrackerManager'",
        "# Set per site with `aria-et find-eyetracker --save`.",
        "# address = 'tobii-prp://169.254.x.x'",
        "# serial_number = 'TPSP1-...'",
        "",
    ]
    return "\n".join(lines)


def load_config(path: str | Path | None = None) -> AriaEtConfig:
    config_path = Path(path).expanduser() if path is not None else default_config_path()
    if not config_path.exists():
        return AriaEtConfig(data_root=Path.home() / DEFAULT_DATA_DIR_NAME)

    with config_path.open("rb") as fid:
        raw_config = tomllib.load(fid)

    return AriaEtConfig(
        data_root=_path_value(
            _section(raw_config, "data"),
            "root",
            Path.home() / DEFAULT_DATA_DIR_NAME,
        ),
        etm_screen=_int_value(
            _section(raw_config, "display"),
            "etm_screen",
            DEFAULT_ETM_SCREEN,
        ),
        psychopy_screen=_int_value(
            _section(raw_config, "display"),
            "psychopy_screen",
            DEFAULT_PSYCHOPY_SCREEN,
        ),
        screen_distance_meters=_float_value(
            _section(raw_config, "display"),
            "screen_distance_meters",
            DEFAULT_EIZO_SCREEN_DISTANCE_METERS,
        ),
        screen_resolution=_str_value(
            _section(raw_config, "display"),
            "screen_resolution",
            DEFAULT_EIZO_SCREEN_RESOLUTION,
        ),
        screen_size_meters=_str_value(
            _section(raw_config, "display"),
            "screen_size_meters",
            DEFAULT_EIZO_SCREEN_SIZE_METERS,
        ),
        monitor_name=_str_value(
            _section(raw_config, "display"),
            "monitor_name",
            DEFAULT_MONITOR_NAME,
        ),
        audio_speaker=_optional_str_value(
            _section(raw_config, "audio"),
            "speaker",
        ),
        eye_tracker_manager=_optional_str_value(
            _section(raw_config, "tobii"),
            "eye_tracker_manager",
        ),
        tracker_address=_optional_str_value(
            _section(raw_config, "tobii"),
            "address",
        ),
        tracker_serial_number=_optional_str_value(
            _section(raw_config, "tobii"),
            "serial_number",
        ),
    )


def get_config_value(key: str, path: str | Path | None = None) -> Any:
    """Return the raw value stored under a dotted ``section.key``, or None."""
    section, name = _split_key(key)
    return _read_raw_config(_config_path(path)).get(section, {}).get(name)


def set_config(key: str, value: Any, path: str | Path | None = None) -> AriaEtConfig:
    """Persist ``value`` under a dotted ``section.key`` in the user config.

    Creates the config file from the lab defaults if it does not exist yet.
    Rewriting the file drops any comments it contained.
    """
    section, name = _split_key(key)
    config_path = _config_path(path)
    raw_config = _read_raw_config(config_path, create_defaults=True)
    raw_config.setdefault(section, {})[name] = _coerce_value(key, value)
    _write_raw_config(config_path, raw_config)
    return load_config(config_path)


def unset_config(key: str, path: str | Path | None = None) -> AriaEtConfig:
    """Remove a dotted ``section.key`` from the user config, if present."""
    section, name = _split_key(key)
    config_path = _config_path(path)
    raw_config = _read_raw_config(config_path)
    if name in raw_config.get(section, {}):
        del raw_config[section][name]
        _write_raw_config(config_path, raw_config)
    return load_config(config_path)


def _config_path(path: str | Path | None) -> Path:
    return Path(path).expanduser() if path is not None else default_config_path()


def _split_key(key: str) -> tuple[str, str]:
    if key not in CONFIG_KEYS:
        known = ", ".join(sorted(CONFIG_KEYS))
        raise KeyError(f"Unknown config key {key!r}. Known keys: {known}.")
    section, name = key.split(".", 1)
    return section, name


def _coerce_value(key: str, value: Any) -> str | int | float:
    value_type = CONFIG_KEYS[key]
    try:
        if value_type is Path:
            return str(Path(str(value)).expanduser())
        if value_type is int:
            if isinstance(value, bool):
                raise ValueError
            return int(value)
        if value_type is float:
            return float(value)
    except ValueError as error:
        raise TypeError(
            f"Configuration value {key} must be {value_type.__name__}, got {value!r}."
        ) from error
    return str(value)


def _read_raw_config(
    config_path: Path, *, create_defaults: bool = False
) -> dict[str, dict[str, Any]]:
    if config_path.exists():
        text = config_path.read_text(encoding="utf-8")
    elif create_defaults:
        text = default_config_text()
    else:
        return {}
    raw_config = tomllib.loads(text)
    for name in raw_config:
        _section(raw_config, name)
    return raw_config


def _write_raw_config(
    config_path: Path, raw_config: Mapping[str, Mapping[str, Any]]
) -> None:
    lines = []
    for section, values in raw_config.items():
        if not values:
            continue
        lines.append(f"[{section}]")
        for name, value in values.items():
            lines.append(f"{name} = {_toml_value(value)}")
        lines.append("")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("\n".join(lines), encoding="utf-8")


def _toml_value(value: Any) -> str:
    # The config only holds flat strings and numbers. JSON string escapes are
    # valid TOML basic-string escapes, so json.dumps covers quoting.
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"Unsupported configuration value type: {type(value).__name__}")


def _section(config: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    section = config.get(name, {})
    if not isinstance(section, Mapping):
        raise TypeError(f"Configuration section [{name}] must be a table.")
    return section


def _path_value(section: Mapping[str, Any], key: str, default: Path) -> Path:
    value = section.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise TypeError(f"Configuration value {key} must be a string path.")
    return Path(value).expanduser()


def _str_value(section: Mapping[str, Any], key: str, default: str) -> str:
    value = section.get(key, default)
    if not isinstance(value, str):
        raise TypeError(f"Configuration value {key} must be a string.")
    return value


def _optional_str_value(section: Mapping[str, Any], key: str) -> str | None:
    value = section.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Configuration value {key} must be a string.")
    return value


def _int_value(section: Mapping[str, Any], key: str, default: int) -> int:
    value = section.get(key, default)
    if not isinstance(value, int):
        raise TypeError(f"Configuration value {key} must be an integer.")
    return value


def _float_value(section: Mapping[str, Any], key: str, default: float) -> float:
    value = section.get(key, default)
    if not isinstance(value, (int, float)):
        raise TypeError(f"Configuration value {key} must be a number.")
    return float(value)
