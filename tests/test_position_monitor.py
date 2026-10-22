import math
from types import SimpleNamespace

import pytest

from aria_et.position_monitor import (
    PositionMonitor,
    PositionSample,
    classify,
    mean_distance,
    panel_position,
    sample_from_guide,
)

STREAM = "user_position_guide"
NAN3 = (math.nan, math.nan, math.nan)


def _guide(left=None, right=None):
    return {
        "left_user_position": left or NAN3,
        "left_user_position_validity": int(left is not None),
        "right_user_position": right or NAN3,
        "right_user_position_validity": int(right is not None),
    }


def test_sample_from_guide_keeps_only_valid_eyes():
    sample = sample_from_guide(_guide(left=(0.4, 0.5, 0.5)), received_at=1.0)

    assert sample.left == (0.4, 0.5, 0.5)
    assert sample.right is None
    assert sample.eyes() == {"left": (0.4, 0.5, 0.5)}


def test_sample_from_guide_rejects_nan_even_if_marked_valid():
    data = _guide(left=(0.4, 0.5, 0.5))
    data["left_user_position"] = (0.4, math.nan, 0.5)

    assert sample_from_guide(data, 1.0).left is None


def test_panel_position_mirrors_x_like_detox():
    assert panel_position(0.2, 0.3) == (0.8, 0.3)


def test_mean_distance_averages_valid_eyes():
    both = PositionSample((0.4, 0.5, 0.4), (0.6, 0.5, 0.6), 0.0)
    one = PositionSample(None, (0.6, 0.5, 0.7), 0.0)

    assert mean_distance(both) == pytest.approx(0.5)
    assert mean_distance(one) == pytest.approx(0.7)
    assert mean_distance(PositionSample(None, None, 0.0)) is None
    assert mean_distance(None) is None


@pytest.mark.parametrize(
    ("left", "right", "age", "expected"),
    [
        ((0.45, 0.5, 0.5), (0.55, 0.5, 0.5), 0.0, "good"),
        ((0.45, 0.5, 0.2), (0.55, 0.5, 0.2), 0.0, "too_close"),
        ((0.45, 0.5, 0.8), (0.55, 0.5, 0.8), 0.0, "too_far"),
        ((0.05, 0.5, 0.5), (0.15, 0.5, 0.5), 0.0, "off_centre"),
        ((0.45, 0.95, 0.5), None, 0.0, "off_centre"),
        (None, None, 0.0, "no_eyes"),
        ((0.45, 0.5, 0.5), (0.55, 0.5, 0.5), 2.0, "stale"),
    ],
)
def test_classify(left, right, age, expected):
    sample = PositionSample(left, right, received_at=10.0)

    assert classify(sample, now=10.0 + age) == expected


def test_classify_without_any_sample_is_stale():
    assert classify(None, now=0.0) == "stale"


class FakeTracker:
    def __init__(self):
        self.callback = None
        self.unsubscribed = 0

    def subscribe_to(self, stream, callback, as_dictionary=False):
        assert stream == STREAM and as_dictionary
        self.callback = callback

    def send(self, data):
        assert self.callback is not None
        self.callback(data)

    def unsubscribe_from(self, stream, callback=None):
        assert stream == STREAM
        self.unsubscribed += 1
        self.callback = None


def _import_module(tracker):
    tobii = SimpleNamespace(
        EYETRACKER_USER_POSITION_GUIDE=STREAM,
        find_all_eyetrackers=lambda: (tracker,),
        EyeTracker=lambda address: tracker,
    )

    def import_module(name):
        if name == "tobii_research":
            return tobii
        raise ImportError(name)

    return import_module


def test_monitor_subscribes_and_keeps_the_latest_sample():
    tracker = FakeTracker()
    times = iter([1.0, 2.0])
    monitor = PositionMonitor(import_module=_import_module(tracker), clock=lambda: next(times))

    monitor.start(address="tobii-prp://169.254.10.180", background=False)
    tracker.send(_guide(left=(0.4, 0.5, 0.5)))
    tracker.send(_guide(right=(0.6, 0.5, 0.6)))

    assert monitor.status == "running"
    latest = monitor.latest()
    assert latest is not None
    assert latest.right == (0.6, 0.5, 0.6)
    assert latest.left is None
    assert latest.received_at == 2.0


def test_monitor_stop_unsubscribes_and_is_safe_twice():
    tracker = FakeTracker()
    monitor = PositionMonitor(import_module=_import_module(tracker))
    monitor.start(background=False)

    monitor.stop()
    monitor.stop()

    assert tracker.unsubscribed == 1
    assert monitor.status == "stopped"
    assert monitor.latest() is None


def test_monitor_restart_replaces_the_subscription():
    tracker = FakeTracker()
    monitor = PositionMonitor(import_module=_import_module(tracker))
    monitor.start(background=False)

    monitor.start(background=False)

    assert tracker.unsubscribed == 1
    assert monitor.status == "running"


def test_monitor_failure_is_reported_not_raised():
    def missing_sdk(name):
        raise ImportError(name)

    monitor = PositionMonitor(import_module=missing_sdk)

    monitor.start(background=False)

    assert monitor.status == "unavailable"
    assert "Tobii Pro SDK" in monitor.message
    monitor.stop()  # still safe
