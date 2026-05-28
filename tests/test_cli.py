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
            "window_size": (800, 600),
            "play_sound": False,
            "point_duration_seconds": 0.25,
            "advance_on_space": False,
            "debug_render": False,
        }
    ]


def test_demo_calibration_defaults_to_windowed_runner_options():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return 0

    exit_code = main(["demo-calibration"], demo_calibration_runner=runner)

    assert exit_code == 0
    assert calls == [
        {
            "fullscreen": False,
            "window_size": (1024, 768),
            "play_sound": True,
            "point_duration_seconds": 1.0,
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
            "window_size": (800, 600),
            "play_sound": False,
            "trial_limit": 2,
            "debug_render": True,
        }
    ]


def test_parse_window_size():
    assert parse_window_size("1920x1080") == (1920, 1080)


def test_parse_window_size_rejects_invalid_format():
    with pytest.raises(Exception, match="Expected size"):
        parse_window_size("nope")
