import pytest
from pathlib import Path
from types import SimpleNamespace

from aria_et.cli import main, parse_float_pair, parse_window_size


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))


def test_list_tasks_prints_battery_order(capsys):
    exit_code = main(["list-tasks"])

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        "calibration",
        "activity-monitoring",
        "social-interactive",
        "static-social-scenes",
        "pupillary-light-reflex",
    ]


def test_init_config_writes_lab_defaults(tmp_path, capsys):
    config_path = tmp_path / "config.toml"

    exit_code = main(["init-config", "--path", str(config_path)])

    assert exit_code == 0
    assert "Wrote ARIA-ET config" in capsys.readouterr().out
    config_text = config_path.read_text(encoding="utf-8")
    assert '[display]' in config_text
    assert 'monitor_name = "EIZO_EV2480"' in config_text
    assert '[audio]' in config_text
    assert 'speaker = "EV2480"' in config_text


def test_init_config_refuses_to_overwrite_existing_file(tmp_path, capsys):
    config_path = tmp_path / "config.toml"
    config_path.write_text("custom = true\n", encoding="utf-8")

    exit_code = main(["init-config", "--path", str(config_path)])

    assert exit_code == 1
    assert "already exists" in capsys.readouterr().err
    assert config_path.read_text(encoding="utf-8") == "custom = true\n"


def test_init_config_can_force_overwrite_existing_file(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("custom = true\n", encoding="utf-8")

    exit_code = main(["init-config", "--path", str(config_path), "--force"])

    assert exit_code == 0
    assert 'monitor_name = "EIZO_EV2480"' in config_path.read_text(encoding="utf-8")


def test_psychopy_task_warns_when_config_is_missing_without_creating_it(tmp_path, capsys):
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        ["run-plr", "--tracker", "none", "--subject", "01"],
        run_pupillary_light_reflex_runner=runner,
    )

    assert exit_code == 0
    assert "No ARIA-ET config found" in capsys.readouterr().err
    assert not (tmp_path / ".aria-et" / "config.toml").exists()
    assert calls[0]["monitor_name"] == "EIZO_EV2480"


def test_check_eyetracker_invokes_injected_runner():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 3

    exit_code = main(["check-eyetracker"], check_eyetracker_runner=runner)

    assert exit_code == 3
    assert calls == [{"address": None}]


def test_check_eyetracker_passes_explicit_address_to_injected_runner():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        ["check-eyetracker", "--address", "tobii-prp://169.254.10.180"],
        check_eyetracker_runner=runner,
    )

    assert exit_code == 0
    assert calls == [{"address": "tobii-prp://169.254.10.180"}]


def test_export_bids_invokes_injected_runner(capsys):
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            bids_root=Path("bids-out"),
            written_files=(Path("bids-out/dataset_description.json"),),
        )

    exit_code = main(
        [
            "export-bids",
            "--input",
            "runs/plr-smoke",
            "--output",
            "bids-out",
        ],
        export_bids_runner=runner,
    )

    assert exit_code == 0
    assert calls == [{"run_dir": "runs/plr-smoke", "bids_root": "bids-out"}]
    assert "Exported BIDS eyetracking files to bids-out" in capsys.readouterr().out


def test_export_bids_defaults_to_user_data_bids_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            bids_root=kwargs["bids_root"],
            written_files=(),
        )

    exit_code = main(
        [
            "export-bids",
            "--input",
            "runs/plr-smoke",
        ],
        export_bids_runner=runner,
    )

    assert exit_code == 0
    assert calls == [
        {
            "run_dir": "runs/plr-smoke",
            "bids_root": tmp_path / "aria-et-data" / "bids",
        }
    ]


def test_calibrate_eyetracker_invokes_manager_runner_with_production_defaults():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        ["calibrate-eyetracker"],
        calibrate_eyetracker_runner=runner,
    )

    assert exit_code == 0
    assert calls == [
        {
            "address": None,
            "calibration_output_dir": "calibrations",
            "serial_number": None,
            "screen": 2,
        }
    ]


def test_calibrate_eyetracker_can_target_address_serial_screen_and_manager():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 31

    exit_code = main(
        [
            "calibrate-eyetracker",
            "--address",
            "tobii-prp://169.254.10.180",
            "--screen",
            "2",
            "--manager",
            "/tmp/TobiiProEyeTrackerManager",
        ],
        calibrate_eyetracker_runner=runner,
    )

    assert exit_code == 31
    assert calls == [
        {
            "address": "tobii-prp://169.254.10.180",
            "calibration_output_dir": "calibrations",
            "serial_number": None,
            "screen": 2,
            "executable": "/tmp/TobiiProEyeTrackerManager",
        }
    ]


def test_calibrate_eyetracker_can_set_output_directory():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        [
            "calibrate-eyetracker",
            "--output",
            "runs/calibrations",
        ],
        calibrate_eyetracker_runner=runner,
    )

    assert exit_code == 0
    assert calls == [
        {
            "address": None,
            "calibration_output_dir": "runs/calibrations",
            "serial_number": None,
            "screen": 2,
        }
    ]


def test_cli_uses_user_config_defaults(tmp_path):
    config_path = tmp_path / ".aria-et" / "config.toml"
    config_path.parent.mkdir()
    config_path.write_text(
        """
[data]
root = "~/configured-data"

[display]
etm_screen = 4
psychopy_screen = 3
screen_distance_meters = 0.72
screen_resolution = "2560x1440"
screen_size_meters = "0.6x0.34"
monitor_name = "ConfiguredMonitor"

[audio]
speaker = "EV2480"

[tobii]
eye_tracker_manager = "/Applications/ConfiguredETM"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    calibration_calls = []
    run_calls = []

    def calibration_runner(**kwargs):
        calibration_calls.append(kwargs)
        return 0

    def run_runner(**kwargs):
        run_calls.append(kwargs)
        return 0

    assert (
        main(
            ["calibrate-eyetracker"],
            calibrate_eyetracker_runner=calibration_runner,
        )
        == 0
    )
    assert (
        main(
            ["run-am", "--tracker", "none", "--subject", "1"],
            run_activity_monitoring_runner=run_runner,
        )
        == 0
    )

    assert calibration_calls[0]["screen"] == 4
    assert calibration_calls[0]["executable"] == "/Applications/ConfiguredETM"
    assert run_calls[0]["output_dir"] == tmp_path / "configured-data" / "sourcedata"
    assert run_calls[0]["screen"] == 3
    assert run_calls[0]["screen_distance_meters"] == 0.72
    assert run_calls[0]["screen_resolution_pixels"] == (2560, 1440)
    assert run_calls[0]["screen_size_meters"] == (0.6, 0.34)
    assert run_calls[0]["monitor_name"] == "ConfiguredMonitor"
    assert run_calls[0]["audio_speaker"] == "EV2480"


def test_demo_calibration_invokes_injected_runner():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        [
            "demo-calibration",
            "--windowed",
            "--size",
            "800x600",
            "--no-sound",
            "--point-duration",
            "0.25",
        ],
        demo_calibration_runner=runner,
    )

    assert exit_code == 0
    assert calls == [
        {
            "fullscreen": False,
            "screen": 1,
            "window_size": (800, 600),
            "screen_distance_meters": 0.65,
            "screen_resolution_pixels": (1920, 1080),
            "screen_size_meters": (0.527, 0.296),
            "monitor_name": "EIZO_EV2480",
            "audio_speaker": None,
            "play_sound": False,
            "point_duration_seconds": 0.25,
            "advance_on_space": False,
            "debug_render": False,
        }
    ]


def test_demo_calibration_defaults_to_eizo_fullscreen_runner_options():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(["demo-calibration"], demo_calibration_runner=runner)

    assert exit_code == 0
    assert calls == [
        {
            "fullscreen": True,
            "screen": 1,
            "window_size": (1024, 768),
            "screen_distance_meters": 0.65,
            "screen_resolution_pixels": (1920, 1080),
            "screen_size_meters": (0.527, 0.296),
            "monitor_name": "EIZO_EV2480",
            "audio_speaker": None,
            "play_sound": True,
            "point_duration_seconds": 3.0,
            "advance_on_space": False,
            "debug_render": False,
        }
    ]


def test_demo_calibration_can_request_fullscreen():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(["demo-calibration", "--fullscreen"], demo_calibration_runner=runner)

    assert exit_code == 0
    assert calls[0]["fullscreen"] is True


def test_demo_calibration_can_wait_for_space_between_points():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        ["demo-calibration", "--advance-on-space"],
        demo_calibration_runner=runner,
    )

    assert exit_code == 0
    assert calls[0]["advance_on_space"] is True


def test_demo_calibration_can_enable_render_debug_logging():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        ["demo-calibration", "--debug-render"],
        demo_calibration_runner=runner,
    )

    assert exit_code == 0
    assert calls[0]["debug_render"] is True


def test_demo_activity_monitoring_invokes_injected_runner():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        [
            "demo-am",
            "--fullscreen",
            "--size",
            "800x600",
            "--no-sound",
            "--trial-limit",
            "2",
            "--debug-render",
        ],
        demo_activity_monitoring_runner=runner,
    )

    assert exit_code == 0
    assert calls == [
        {
            "fullscreen": True,
            "screen": 1,
            "window_size": (800, 600),
            "screen_distance_meters": 0.65,
            "screen_resolution_pixels": (1920, 1080),
            "screen_size_meters": (0.527, 0.296),
            "monitor_name": "EIZO_EV2480",
            "audio_speaker": None,
            "play_sound": False,
            "trial_limit": 2,
            "debug_render": True,
        }
    ]


def test_run_activity_monitoring_invokes_injected_runner():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        [
            "run-am",
            "--tracker",
            "none",
            "--output",
            "runs/test-am",
            "--subject",
            "01",
            "--fullscreen",
            "--size",
            "800x600",
            "--no-sound",
            "--trial-limit",
            "2",
            "--debug-render",
        ],
        run_activity_monitoring_runner=runner,
    )

    assert exit_code == 0
    assert calls == [
        {
            "tracker": "none",
            "tracker_address": None,
            "output_dir": "runs/test-am",
            "subject": "01",
            "session": None,
            "run": None,
            "fullscreen": True,
            "screen": 1,
            "window_size": (800, 600),
            "screen_distance_meters": 0.65,
            "screen_resolution_pixels": (1920, 1080),
            "screen_size_meters": (0.527, 0.296),
            "monitor_name": "EIZO_EV2480",
            "audio_speaker": None,
            "play_sound": False,
            "trial_limit": 2,
            "debug_render": True,
        }
    ]


def test_run_activity_monitoring_defaults_to_user_data_sourcedata_root(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path))
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        [
            "run-am",
            "--tracker",
            "none",
            "--subject",
            "1",
        ],
        run_activity_monitoring_runner=runner,
    )

    assert exit_code == 0
    assert calls[0]["output_dir"] == tmp_path / "aria-et-data" / "sourcedata"
    assert calls[0]["subject"] == "1"
    assert calls[0]["run"] is None


def test_demo_social_interactive_invokes_injected_runner():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        [
            "demo-si",
            "--fullscreen",
            "--size",
            "800x600",
            "--no-sound",
            "--trial-limit",
            "2",
            "--debug-render",
        ],
        demo_social_interactive_runner=runner,
    )

    assert exit_code == 0
    assert calls == [
        {
            "fullscreen": True,
            "screen": 1,
            "window_size": (800, 600),
            "screen_distance_meters": 0.65,
            "screen_resolution_pixels": (1920, 1080),
            "screen_size_meters": (0.527, 0.296),
            "monitor_name": "EIZO_EV2480",
            "audio_speaker": None,
            "play_sound": False,
            "trial_limit": 2,
            "debug_render": True,
        }
    ]


def test_demo_static_social_scenes_invokes_injected_runner():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        [
            "demo-ss",
            "--fullscreen",
            "--size",
            "800x600",
            "--no-sound",
            "--trial-limit",
            "2",
            "--debug-render",
        ],
        demo_static_social_scenes_runner=runner,
    )

    assert exit_code == 0
    assert calls == [
        {
            "fullscreen": True,
            "screen": 1,
            "window_size": (800, 600),
            "screen_distance_meters": 0.65,
            "screen_resolution_pixels": (1920, 1080),
            "screen_size_meters": (0.527, 0.296),
            "monitor_name": "EIZO_EV2480",
            "audio_speaker": None,
            "play_sound": False,
            "trial_limit": 2,
            "debug_render": True,
        }
    ]


def test_run_static_social_scenes_invokes_injected_runner():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        [
            "run-ss",
            "--tracker",
            "none",
            "--output",
            "runs/test-ss",
            "--subject",
            "01",
        ],
        run_static_social_scenes_runner=runner,
    )

    assert exit_code == 0
    assert calls == [
        {
            "tracker": "none",
            "tracker_address": None,
            "output_dir": "runs/test-ss",
            "subject": "01",
            "session": None,
            "run": None,
            "fullscreen": True,
            "screen": 1,
            "window_size": (1024, 768),
            "screen_distance_meters": 0.65,
            "screen_resolution_pixels": (1920, 1080),
            "screen_size_meters": (0.527, 0.296),
            "monitor_name": "EIZO_EV2480",
            "audio_speaker": None,
            "play_sound": True,
            "trial_limit": None,
            "debug_render": False,
        }
    ]


def test_demo_pupillary_light_reflex_invokes_injected_runner():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        [
            "demo-plr",
            "--fullscreen",
            "--size",
            "800x600",
            "--no-sound",
            "--trial-limit",
            "2",
            "--debug-render",
        ],
        demo_pupillary_light_reflex_runner=runner,
    )

    assert exit_code == 0
    assert calls == [
        {
            "fullscreen": True,
            "screen": 1,
            "window_size": (800, 600),
            "screen_distance_meters": 0.65,
            "screen_resolution_pixels": (1920, 1080),
            "screen_size_meters": (0.527, 0.296),
            "monitor_name": "EIZO_EV2480",
            "audio_speaker": None,
            "play_sound": False,
            "trial_limit": 2,
            "debug_render": True,
        }
    ]


def test_run_pupillary_light_reflex_invokes_injected_runner():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        [
            "run-plr",
            "--tracker",
            "none",
            "--output",
            "runs/test-plr",
            "--subject",
            "01",
            "--session",
            "baseline",
            "--run",
            "02",
            "--screen",
            "2",
            "--screen-distance-meters",
            "0.6",
            "--screen-resolution",
            "1280x720",
            "--screen-size-meters",
            "0.4x0.2",
        ],
        run_pupillary_light_reflex_runner=runner,
    )

    assert exit_code == 0
    assert calls == [
        {
            "tracker": "none",
            "tracker_address": None,
            "output_dir": "runs/test-plr",
            "subject": "01",
            "session": "baseline",
            "run": "02",
            "fullscreen": True,
            "screen": 2,
            "window_size": (1024, 768),
            "screen_distance_meters": 0.6,
            "screen_resolution_pixels": (1280, 720),
            "screen_size_meters": (0.4, 0.2),
            "monitor_name": "EIZO_EV2480",
            "audio_speaker": None,
            "play_sound": True,
            "trial_limit": None,
            "debug_render": False,
        }
    ]


def test_run_pupillary_light_reflex_passes_explicit_tracker_address():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        [
            "run-plr",
            "--tracker",
            "tobii",
            "--address",
            "tobii-prp://169.254.10.180",
            "--output",
            "runs/test-plr",
            "--subject",
            "01",
        ],
        run_pupillary_light_reflex_runner=runner,
    )

    assert exit_code == 0
    assert calls[0]["tracker"] == "tobii"
    assert calls[0]["tracker_address"] == "tobii-prp://169.254.10.180"


def test_parse_window_size():
    assert parse_window_size("1920x1080") == (1920, 1080)


def test_parse_window_size_rejects_invalid_format():
    with pytest.raises(Exception, match="Expected size"):
        parse_window_size("nope")


def test_parse_float_pair():
    assert parse_float_pair("0.527x0.296") == (0.527, 0.296)
