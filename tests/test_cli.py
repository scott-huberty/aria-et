import pytest

from aria_et.cli import main, parse_window_size


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
            "fullscreen": True,
            "screen": 1,
            "window_size": (800, 600),
            "play_sound": False,
            "trial_limit": 2,
            "debug_render": True,
        }
    ]


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
        ],
        run_static_social_scenes_runner=runner,
    )

    assert exit_code == 0
    assert calls == [
        {
            "tracker": "none",
            "tracker_address": None,
            "output_dir": "runs/test-ss",
            "fullscreen": True,
            "screen": 1,
            "window_size": (1024, 768),
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
            "--attention-cue-seconds",
            "0.25",
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
            "play_sound": False,
            "trial_limit": 2,
            "inter_trial_attention_seconds": 0.25,
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
            "--screen",
            "2",
            "--attention-cue-seconds",
            "0",
        ],
        run_pupillary_light_reflex_runner=runner,
    )

    assert exit_code == 0
    assert calls == [
        {
            "tracker": "none",
            "tracker_address": None,
            "output_dir": "runs/test-plr",
            "fullscreen": True,
            "screen": 2,
            "window_size": (1024, 768),
            "play_sound": True,
            "trial_limit": None,
            "inter_trial_attention_seconds": 0,
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
        ],
        run_pupillary_light_reflex_runner=runner,
    )

    assert exit_code == 0
    assert calls[0]["tracker"] == "tobii"
    assert calls[0]["tracker_address"] == "tobii-prp://169.254.10.180"


def test_demo_pupillary_light_reflex_can_disable_attention_cue():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(
        ["demo-plr", "--attention-cue-seconds", "0"],
        demo_pupillary_light_reflex_runner=runner,
    )

    assert exit_code == 0
    assert calls[0]["inter_trial_attention_seconds"] == 0


def test_parse_window_size():
    assert parse_window_size("1920x1080") == (1920, 1080)


def test_parse_window_size_rejects_invalid_format():
    with pytest.raises(Exception, match="Expected size"):
        parse_window_size("nope")
