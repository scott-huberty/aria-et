import pytest

import aria_et
from aria_et.config import (
    default_config_path,
    get_config_value,
    load_config,
    set_config,
    unset_config,
)


def test_set_config_creates_missing_file_with_defaults(tmp_path):
    config = aria_et.set_config("tobii.address", "tobii-prp://169.254.10.180")

    assert default_config_path().exists()
    assert config.tracker_address == "tobii-prp://169.254.10.180"
    assert config.tracker_serial_number is None
    assert config.monitor_name == "EIZO_EV2480"
    assert load_config().tracker_address == "tobii-prp://169.254.10.180"


def test_set_config_round_trips_and_keeps_other_values(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[display]\npsychopy_screen = 3\n\n[tobii]\neye_tracker_manager = 'C:\\ETM\\etm.exe'\n",
        encoding="utf-8",
    )

    set_config("tobii.serial_number", "TPSP1-010214213025", config_path)
    config = set_config("display.screen_distance_meters", "0.7", config_path)

    assert config.psychopy_screen == 3
    assert config.eye_tracker_manager == "C:\\ETM\\etm.exe"
    assert config.tracker_serial_number == "TPSP1-010214213025"
    assert config.screen_distance_meters == 0.7
    assert get_config_value("tobii.serial_number", config_path) == "TPSP1-010214213025"


def test_set_config_coerces_and_validates_types(tmp_path):
    config_path = tmp_path / "config.toml"

    assert set_config("display.etm_screen", "4", config_path).etm_screen == 4
    with pytest.raises(TypeError, match="display.etm_screen"):
        set_config("display.etm_screen", "two", config_path)


def test_set_config_rejects_unknown_keys(tmp_path):
    with pytest.raises(KeyError, match="tobii.adress"):
        set_config("tobii.adress", "x", tmp_path / "config.toml")


def test_unset_config_removes_value(tmp_path):
    config_path = tmp_path / "config.toml"
    set_config("tobii.address", "tobii-prp://169.254.10.180", config_path)

    config = unset_config("tobii.address", config_path)

    assert config.tracker_address is None
    assert get_config_value("tobii.address", config_path) is None


def test_load_config_uses_defaults_when_file_is_missing(tmp_path):
    config = load_config()

    assert config.data_root == tmp_path / "aria-et-data"
    assert config.etm_screen == 2
    assert config.psychopy_screen == 1
    assert config.screen_distance_meters == 0.65
    assert config.screen_resolution == "1920x1080"
    assert config.screen_size_meters == "0.527x0.296"
    assert config.monitor_name == "EIZO_EV2480"
    assert config.audio_speaker == "EV2480"
    assert config.eye_tracker_manager is None


def test_load_config_reads_user_toml(tmp_path):
    config_path = tmp_path / ".aria-et" / "config.toml"
    config_path.parent.mkdir()
    config_path.write_text(
        """
[data]
root = "~/lab-data"

[display]
etm_screen = 3
psychopy_screen = 2
screen_distance_meters = 0.72
screen_resolution = "2560x1440"
screen_size_meters = "0.6x0.34"
monitor_name = "ConfiguredMonitor"

[audio]
speaker = "EV2480"

[tobii]
eye_tracker_manager = "/Applications/Tobii"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_config()

    assert config.data_root == tmp_path / "lab-data"
    assert config.etm_screen == 3
    assert config.psychopy_screen == 2
    assert config.screen_distance_meters == 0.72
    assert config.screen_resolution == "2560x1440"
    assert config.screen_size_meters == "0.6x0.34"
    assert config.monitor_name == "ConfiguredMonitor"
    assert config.audio_speaker == "EV2480"
    assert config.eye_tracker_manager == "/Applications/Tobii"


def test_load_config_rejects_invalid_section_type(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("display = 'screen 2'\n", encoding="utf-8")

    with pytest.raises(TypeError, match=r"\[display\]"):
        load_config(config_path)


def test_load_config_rejects_invalid_value_type(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('[display]\npsychopy_screen = "2"\n', encoding="utf-8")

    with pytest.raises(TypeError, match="psychopy_screen"):
        load_config(config_path)
