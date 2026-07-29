"""User configuration for ARIA eye-tracking commands."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10.
    import tomli as tomllib


DEFAULT_DATA_DIR_NAME = "aria-et-data"
DEFAULT_ETM_SCREEN = 2
DEFAULT_PSYCHOPY_SCREEN = 1
DEFAULT_EIZO_SCREEN_DISTANCE_METERS = 0.65
DEFAULT_EIZO_SCREEN_RESOLUTION = "1920x1080"
DEFAULT_EIZO_SCREEN_SIZE_METERS = "0.527x0.296"


@dataclass(frozen=True)
class AriaEtConfig:
    data_root: Path = Path.home() / DEFAULT_DATA_DIR_NAME
    etm_screen: int = DEFAULT_ETM_SCREEN
    psychopy_screen: int = DEFAULT_PSYCHOPY_SCREEN
    screen_distance_meters: float = DEFAULT_EIZO_SCREEN_DISTANCE_METERS
    screen_resolution: str = DEFAULT_EIZO_SCREEN_RESOLUTION
    screen_size_meters: str = DEFAULT_EIZO_SCREEN_SIZE_METERS
    eye_tracker_manager: str | None = None


def default_config_path() -> Path:
    return Path.home() / ".aria-et" / "config.toml"


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
        eye_tracker_manager=_optional_str_value(
            _section(raw_config, "tobii"),
            "eye_tracker_manager",
        ),
    )


def _section(config: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    section = config.get(name, {})
    if not isinstance(section, Mapping):
        raise ValueError(f"Configuration section [{name}] must be a table.")
    return section


def _path_value(section: Mapping[str, Any], key: str, default: Path) -> Path:
    value = section.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"Configuration value {key} must be a string path.")
    return Path(value).expanduser()


def _str_value(section: Mapping[str, Any], key: str, default: str) -> str:
    value = section.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"Configuration value {key} must be a string.")
    return value


def _optional_str_value(section: Mapping[str, Any], key: str) -> str | None:
    value = section.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Configuration value {key} must be a string.")
    return value


def _int_value(section: Mapping[str, Any], key: str, default: int) -> int:
    value = section.get(key, default)
    if not isinstance(value, int):
        raise ValueError(f"Configuration value {key} must be an integer.")
    return value


def _float_value(section: Mapping[str, Any], key: str, default: float) -> float:
    value = section.get(key, default)
    if not isinstance(value, (int, float)):
        raise ValueError(f"Configuration value {key} must be a number.")
    return float(value)
