import json

from aria_et.eyetracker import TobiiGazeRecorder, check_eyetracker


class FakeTobiiResearch:
    __version__ = "2.1.0"

    def __init__(self, eyetrackers):
        self._eyetrackers = eyetrackers
        self.opened_addresses = []

    def find_all_eyetrackers(self):
        return self._eyetrackers

    def EyeTracker(self, address):
        self.opened_addresses.append(address)
        if address == "tobii-prp://missing":
            raise RuntimeError("connection failed")
        tracker = FakeEyeTracker()
        tracker.address = address
        return tracker


class FakeEyeTracker:
    device_name = "Tobii Pro Spectrum"
    model = "Spectrum"
    serial_number = "TPS-123"
    address = "tet-tcp://169.254.0.1"
    firmware_version = "2.6.2"

    def __init__(self):
        self.subscriptions = []
        self.unsubscriptions = []

    def subscribe_to(self, subscription_type, callback, as_dictionary=False):
        self.subscriptions.append(
            {
                "subscription_type": subscription_type,
                "callback": callback,
                "as_dictionary": as_dictionary,
            }
        )

    def unsubscribe_from(self, subscription_type, callback=None):
        self.unsubscriptions.append(
            {
                "subscription_type": subscription_type,
                "callback": callback,
            }
        )


class FakeTobiiModule:
    EYETRACKER_GAZE_DATA = "eyetracker_gaze_data"


def test_check_eyetracker_reports_missing_tobii_sdk(capsys):
    def missing_sdk(name):
        raise ImportError(f"No module named {name}")

    exit_code = check_eyetracker(import_module=missing_sdk)

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "Tobii Pro SDK is not available" in captured.err
    assert "pip install tobii-research" in captured.err


def test_check_eyetracker_reports_no_connected_tobii_tracker(capsys):
    def installed_sdk(name):
        return FakeTobiiResearch(())

    exit_code = check_eyetracker(import_module=installed_sdk)

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "Tobii Pro SDK 2.1.0 is available" in captured.out
    assert "No Tobii eye tracker was found" in captured.err


def test_check_eyetracker_reports_connected_tobii_tracker(capsys):
    def installed_sdk(name):
        return FakeTobiiResearch((FakeEyeTracker(),))

    exit_code = check_eyetracker(import_module=installed_sdk)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Tobii Pro SDK 2.1.0 is available" in captured.out
    assert "Found 1 Tobii eye tracker" in captured.out
    assert "Tobii Pro Spectrum" in captured.out
    assert "TPS-123" in captured.out


def test_check_eyetracker_can_connect_to_explicit_address(capsys):
    sdk = FakeTobiiResearch(())

    def installed_sdk(name):
        return sdk

    exit_code = check_eyetracker(
        address="tobii-prp://169.254.10.180",
        import_module=installed_sdk,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert sdk.opened_addresses == ["tobii-prp://169.254.10.180"]
    assert "Connected to Tobii eye tracker at tobii-prp://169.254.10.180" in captured.out
    assert "Found 1 Tobii eye tracker" in captured.out


def test_check_eyetracker_reports_explicit_address_connection_failure(capsys):
    def installed_sdk(name):
        return FakeTobiiResearch(())

    exit_code = check_eyetracker(
        address="tobii-prp://missing",
        import_module=installed_sdk,
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "No Tobii eye tracker could be opened at tobii-prp://missing" in captured.err


def test_tobii_gaze_recorder_writes_tracker_metadata_and_gaze_samples(tmp_path):
    tracker = FakeEyeTracker()
    recorder = TobiiGazeRecorder(
        eyetracker=tracker,
        tobii_research=FakeTobiiModule,
        gaze_path=tmp_path / "gaze.jsonl",
        tracker_metadata_path=tmp_path / "tracker.json",
        clock=lambda: 12.5,
    )

    with recorder:
        callback = tracker.subscriptions[0]["callback"]
        callback(
            {
                "system_time_stamp": 123,
                "left_gaze_point_on_display_area": (0.25, 0.75),
            }
        )

    metadata = json.loads((tmp_path / "tracker.json").read_text())
    assert metadata == {
        "address": "tet-tcp://169.254.0.1",
        "firmware_version": "2.6.2",
        "model": "Spectrum",
        "serial_number": "TPS-123",
    }
    assert tracker.subscriptions == [
        {
            "subscription_type": "eyetracker_gaze_data",
            "callback": callback,
            "as_dictionary": True,
        }
    ]
    assert tracker.unsubscriptions == [
        {
            "subscription_type": "eyetracker_gaze_data",
            "callback": callback,
        }
    ]
    gaze_record = json.loads((tmp_path / "gaze.jsonl").read_text())
    assert gaze_record == {
        "received_at": 12.5,
        "sample": {
            "left_gaze_point_on_display_area": [0.25, 0.75],
            "system_time_stamp": 123,
        },
    }
