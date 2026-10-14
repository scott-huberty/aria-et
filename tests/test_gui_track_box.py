import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from aria_et.config import AriaEtConfig, set_config
from aria_et.gui.main_window import MainWindow
from aria_et.gui.widgets.track_box import CONNECTING_TEXT, TrackBoxPanel
from aria_et.position_monitor import STATUS_TEXT, PositionSample

pytestmark = pytest.mark.qt_gui


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeMonitor:
    def __init__(self, status="running", sample=None, now=10.0):
        self.status = status
        self.sample = sample
        self._now = now
        self.calls = []

    def latest(self):
        return self.sample

    def now(self):
        return self._now

    def start(self, **kwargs):
        self.calls.append(("start", kwargs))
        self.status = "running"

    def stop(self):
        self.calls.append(("stop",))
        self.status = "stopped"


GOOD = PositionSample((0.45, 0.5, 0.5), (0.55, 0.5, 0.5), received_at=10.0)
TOO_CLOSE = PositionSample((0.45, 0.5, 0.1), (0.55, 0.5, 0.1), received_at=10.0)
NO_EYES = PositionSample(None, None, received_at=10.0)


@pytest.mark.parametrize(
    ("monitor", "expected"),
    [
        (None, STATUS_TEXT["no_tracker"]),
        (FakeMonitor(status="unavailable"), STATUS_TEXT["no_tracker"]),
        (FakeMonitor(status="connecting"), CONNECTING_TEXT),
        (FakeMonitor(sample=GOOD), STATUS_TEXT["good"]),
        (FakeMonitor(sample=TOO_CLOSE), STATUS_TEXT["too_close"]),
        (FakeMonitor(sample=NO_EYES), STATUS_TEXT["no_eyes"]),
        (FakeMonitor(sample=GOOD, now=99.0), STATUS_TEXT["stale"]),
    ],
)
def test_panel_status_and_painting(qapp, monitor, expected):
    panel = TrackBoxPanel(monitor)
    panel.resize(190, 170)

    assert panel.status_text() == expected
    assert not panel.grab().isNull()  # paints without errors in every state


def test_panel_refreshes_only_while_visible(qapp):
    panel = TrackBoxPanel(FakeMonitor(sample=GOOD))

    assert not panel.is_refreshing()
    panel.show()
    assert panel.is_refreshing()
    panel.hide()
    assert not panel.is_refreshing()


@pytest.fixture
def config(tmp_path):
    return AriaEtConfig(data_root=tmp_path / "aria-data")


def test_window_places_the_panel_under_the_nav(qapp, config):
    window = MainWindow(config, position_monitor=FakeMonitor(status="stopped"))

    assert window._track_box.parent() is window._nav.parent()
    assert window._track_box.status_text() == STATUS_TEXT["no_tracker"]


def test_monitor_follows_the_hardware_check_and_stops_on_close(qapp, config):
    set_config("tobii.address", "tobii-prp://169.254.10.180")
    set_config("tobii.serial_number", "TPSP1-010214213025")
    monitor = FakeMonitor(status="stopped")
    window = MainWindow(config, position_monitor=monitor)

    # Nothing starts before the Hardware check finds the tracker.
    assert monitor.calls == []

    window._hardware_page._connected = True
    window._sync_position_monitor()
    assert monitor.calls[-1] == (
        "start",
        {
            "address": "tobii-prp://169.254.10.180",
            "serial_number": "TPSP1-010214213025",
        },
    )

    window._hardware_page._connected = False
    window._sync_position_monitor()
    assert monitor.calls[-1] == ("stop",)

    window.close()
    assert monitor.calls[-1] == ("stop",)
