from aria_et.tasks import BATTERY_ORDER, STANDALONE_TASKS, task_ids


def test_battery_order_matches_first_scope():
    assert task_ids(BATTERY_ORDER) == (
        "calibration",
        "activity-monitoring",
        "social-interactive",
        "static-social-scenes",
        "pupillary-light-reflex",
    )


def test_each_paradigm_can_be_targeted_standalone():
    assert task_ids(STANDALONE_TASKS) == (
        "activity-monitoring",
        "social-interactive",
        "static-social-scenes",
        "pupillary-light-reflex",
    )
