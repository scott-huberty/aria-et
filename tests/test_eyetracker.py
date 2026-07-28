from aria_et.eyetracker import check_eyetracker


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
