from aria_et.cli import main


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
