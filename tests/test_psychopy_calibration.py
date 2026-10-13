import json
import sys
from types import SimpleNamespace

import pytest

from aria_et.psychopy.calibration import (
    CALIBRATION_METHOD,
    run_child_friendly_calibration_demo,
    run_child_friendly_eyetracker_calibration,
)


class FakeTracker:
    address = "tobii-prp://169.254.10.180"
    model = "Tobii Pro Spectrum"
    firmware_version = "2.6.2"

    def __init__(self, serial_number="TPS-123"):
        self.serial_number = serial_number

    def retrieve_calibration_data(self):
        return b"detox-calibration"


class FakeWindow:
    size = (1920, 1080)
    clientSize = (1920, 1080)

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def window(monkeypatch):
    """Fake PsychoPy so the runner can open its window without a display."""
    window = FakeWindow()

    class FakeMonitor:
        def setSizePix(self, size):
            pass

        def saveMon(self):
            pass

    fake_psychopy = SimpleNamespace(
        monitors=SimpleNamespace(Monitor=lambda *args, **kwargs: FakeMonitor()),
        prefs=SimpleNamespace(hardware={}),
        visual=SimpleNamespace(Window=lambda **kwargs: window),
    )
    monkeypatch.setitem(sys.modules, "psychopy", fake_psychopy)
    return window


class FakeDetox:
    """Stands in for the DeToX package; records how ETracker is driven."""

    def __init__(self, trackers, *, calibrate_result=True):
        self.trackers = trackers
        self.calibrate_result = calibrate_result
        self.controllers = []
        detox = self

        class ETracker:
            def __init__(self, win, etracker_id=0, simulate=False, verbose=True):
                self.win = win
                self.etracker_id = etracker_id
                self.simulate = simulate
                self.eyetracker = None if simulate else detox.trackers[etracker_id]
                self.calls = []
                detox.controllers.append(self)

            def show_status(self):
                self.calls.append(("show_status",))

            def calibrate(self, **kwargs):
                self.calls.append(("calibrate", kwargs))
                return detox.calibrate_result

        self.ETracker = ETracker


def _import_module(trackers, detox):
    fake_tobii = SimpleNamespace(
        __version__="2.1.0",
        find_all_eyetrackers=lambda: tuple(trackers),
    )

    def import_module(name):
        if name == "tobii_research":
            return fake_tobii
        if name == "DeToX":
            return detox
        raise ImportError(name)

    return import_module


def test_child_friendly_calibration_runs_detox_and_saves_the_calibration(
    tmp_path, window
):
    # Our tracker is second in discovery, so DeToX must be told its index.
    trackers = [FakeTracker("OTHER"), FakeTracker("TPS-123")]
    detox = FakeDetox(trackers)

    exit_code = run_child_friendly_eyetracker_calibration(
        serial_number="TPS-123",
        calibration_output_dir=tmp_path / "calibrations",
        calibration_points=9,
        shuffle=False,
        animation="trill",
        play_sound=False,
        import_module=_import_module(trackers, detox),
        status_sink=lambda message: None,
    )

    assert exit_code == 0
    controller = detox.controllers[0]
    assert controller.win is window
    assert controller.etracker_id == 1
    assert controller.calls == [
        ("show_status",),
        (
            "calibrate",
            {
                "calibration_points": 9,
                "shuffle": False,
                "audio": False,
                "anim_type": "trill",
                "visualization_style": "circles",
            },
        ),
    ]
    assert window.closed
    artifact_dir = next((tmp_path / "calibrations").iterdir())
    assert (artifact_dir / "calibration.bin").read_bytes() == b"detox-calibration"
    metadata = json.loads((artifact_dir / "calibration.json").read_text())
    assert metadata["method"] == CALIBRATION_METHOD
    assert metadata["tracker"]["serial_number"] == "TPS-123"


def test_child_friendly_calibration_can_skip_positioning(tmp_path, window):
    trackers = [FakeTracker()]
    detox = FakeDetox(trackers)

    run_child_friendly_eyetracker_calibration(
        calibration_output_dir=tmp_path / "calibrations",
        show_positioning=False,
        import_module=_import_module(trackers, detox),
        status_sink=lambda message: None,
    )

    assert [call[0] for call in detox.controllers[0].calls] == ["calibrate"]


def test_aborted_calibration_saves_nothing(tmp_path, window, capsys):
    trackers = [FakeTracker()]
    detox = FakeDetox(trackers, calibrate_result=False)

    exit_code = run_child_friendly_eyetracker_calibration(
        calibration_output_dir=tmp_path / "calibrations",
        import_module=_import_module(trackers, detox),
        status_sink=lambda message: None,
    )

    assert exit_code == 31
    assert not (tmp_path / "calibrations").exists()
    assert "nothing was saved" in capsys.readouterr().err
    assert window.closed


def test_child_friendly_calibration_reports_a_missing_tracker(tmp_path, capsys):
    detox = FakeDetox([])

    exit_code = run_child_friendly_eyetracker_calibration(
        calibration_output_dir=tmp_path / "calibrations",
        import_module=_import_module([], detox),
        status_sink=lambda message: None,
    )

    assert exit_code == 3
    assert detox.controllers == []
    assert "No Tobii eye tracker was found" in capsys.readouterr().err


def test_child_friendly_calibration_rejects_address_and_serial(capsys):
    exit_code = run_child_friendly_eyetracker_calibration(
        address="tobii-prp://169.254.10.180",
        serial_number="TPS-123",
    )

    assert exit_code == 51
    assert "either --address or --serial-number" in capsys.readouterr().err


def test_calibration_demo_uses_detox_mouse_simulation(window):
    detox = FakeDetox([])

    exit_code = run_child_friendly_calibration_demo(
        import_module=_import_module([], detox),
        status_sink=lambda message: None,
    )

    assert exit_code == 0
    controller = detox.controllers[0]
    assert controller.simulate is True
    assert [call[0] for call in controller.calls] == ["show_status", "calibrate"]
    assert window.closed


def test_importing_the_calibration_module_does_not_import_psychopy():
    assert "psychopy" not in sys.modules
    assert "DeToX" not in sys.modules
