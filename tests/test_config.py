import pytest

from aria_et.config import load_config


def test_load_config_uses_defaults_when_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    config = load_config()

    assert config.data_root == tmp_path / "aria-et-data"
    assert config.etm_screen == 2
    assert config.psychopy_screen == 1
    assert config.screen_distance_meters == 0.65
    assert config.screen_resolution == "1920x1080"
    assert config.screen_size_meters == "0.527x0.296"
    assert config.eye_tracker_manager is None


def test_load_config_reads_user_toml(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
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
    assert config.eye_tracker_manager == "/Applications/Tobii"


def test_load_config_rejects_invalid_section_type(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('display = "screen 2"\n', encoding="utf-8")

    with pytest.raises(ValueError, match=r"\[display\]"):
        load_config(config_path)


def test_load_config_rejects_invalid_value_type(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[display]\npsychopy_screen = \"2\"\n", encoding="utf-8")

    with pytest.raises(ValueError, match="psychopy_screen"):
        load_config(config_path)
