import json
import math
import subprocess
from datetime import datetime, timezone

from aria_et.eyetracker import (
    TobiiGazeRecorder,
    check_eyetracker,
    run_eyetracker_manager_calibration,
    save_current_calibration,
)


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
        self.calibration_data = b"fake-calibration-data"

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

    def retrieve_calibration_data(self):
        return self.calibration_data


class FakeTobiiModule:
    EYETRACKER_GAZE_DATA = "eyetracker_gaze_data"


class ManualClock:
    def __init__(self, timestamp=0.0):
        self.timestamp = timestamp

    def __call__(self):
        return self.timestamp


class CountingFlushTobiiGazeRecorder(TobiiGazeRecorder):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.flush_count = 0

    def _flush_gaze_file(self):
        self.flush_count += 1
        super()._flush_gaze_file()


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
                "left_pupil_diameter": math.nan,
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
            "left_pupil_diameter": None,
            "system_time_stamp": 123,
        },
    }


def test_tobii_gaze_recorder_flushes_after_configured_sample_count(tmp_path):
    tracker = FakeEyeTracker()
    clock = ManualClock()
    recorder = CountingFlushTobiiGazeRecorder(
        eyetracker=tracker,
        tobii_research=FakeTobiiModule,
        gaze_path=tmp_path / "gaze.jsonl",
        tracker_metadata_path=tmp_path / "tracker.json",
        clock=clock,
        flush_every_samples=2,
        flush_every_seconds=60.0,
    )

    recorder.start()
    try:
        callback = tracker.subscriptions[0]["callback"]
        callback({"system_time_stamp": 1})
        recorder._queue.join()
        assert recorder.flush_count == 0

        callback({"system_time_stamp": 2})
        recorder._queue.join()
        assert recorder.flush_count == 1
    finally:
        recorder.stop()
    assert recorder.flush_count == 2
    assert len((tmp_path / "gaze.jsonl").read_text().splitlines()) == 2


def test_tobii_gaze_recorder_flushes_after_configured_elapsed_time(tmp_path):
    tracker = FakeEyeTracker()
    clock = ManualClock()
    recorder = CountingFlushTobiiGazeRecorder(
        eyetracker=tracker,
        tobii_research=FakeTobiiModule,
        gaze_path=tmp_path / "gaze.jsonl",
        tracker_metadata_path=tmp_path / "tracker.json",
        clock=clock,
        flush_every_samples=100,
        flush_every_seconds=0.5,
    )

    recorder.start()
    try:
        callback = tracker.subscriptions[0]["callback"]
        clock.timestamp = 0.25
        callback({"system_time_stamp": 1})
        recorder._queue.join()
        assert recorder.flush_count == 0

        clock.timestamp = 0.5
        callback({"system_time_stamp": 2})
        recorder._queue.join()
        assert recorder.flush_count == 1
    finally:
        recorder.stop()
    assert recorder.flush_count == 2
    assert len((tmp_path / "gaze.jsonl").read_text().splitlines()) == 2


def test_tobii_gaze_recorder_drains_queue_on_stop(tmp_path):
    tracker = FakeEyeTracker()
    recorder = TobiiGazeRecorder(
        eyetracker=tracker,
        tobii_research=FakeTobiiModule,
        gaze_path=tmp_path / "gaze.jsonl",
        tracker_metadata_path=tmp_path / "tracker.json",
        clock=lambda: 12.5,
        flush_every_samples=100,
        flush_every_seconds=60.0,
    )

    recorder.start()
    callback = tracker.subscriptions[0]["callback"]
    for index in range(10):
        callback({"system_time_stamp": index})

    recorder.stop()

    assert len((tmp_path / "gaze.jsonl").read_text().splitlines()) == 10


def test_tobii_gaze_recorder_writes_writer_health_snapshots(tmp_path):
    tracker = FakeEyeTracker()
    clock = ManualClock()
    recorder = TobiiGazeRecorder(
        eyetracker=tracker,
        tobii_research=FakeTobiiModule,
        gaze_path=tmp_path / "gaze.jsonl",
        tracker_metadata_path=tmp_path / "tracker.json",
        writer_health_path=tmp_path / "gaze_writer.json",
        clock=clock,
        flush_every_samples=2,
        flush_every_seconds=60.0,
    )

    recorder.start()
    try:
        callback = tracker.subscriptions[0]["callback"]
        callback({"system_time_stamp": 1})
        callback({"system_time_stamp": 2})
        recorder._queue.join()
        health = json.loads((tmp_path / "gaze_writer.json").read_text())
        assert health["received_queue_samples"] == 2
        assert health["written_queue_samples"] == 2
        assert health["dropped_queue_samples"] == 0
        assert health["flush_count"] == 1
        assert health["max_queue_samples"] == 6000
        assert health["writer_error"] is None
    finally:
        recorder.stop()

    final_health = json.loads((tmp_path / "gaze_writer.json").read_text())
    assert final_health["written_queue_samples"] == 2
    assert final_health["flush_count"] == 2
    assert final_health["writer_thread_alive"] is False


def test_tobii_gaze_recorder_counts_queue_drops(tmp_path):
    tracker = FakeEyeTracker()
    recorder = TobiiGazeRecorder(
        eyetracker=tracker,
        tobii_research=FakeTobiiModule,
        gaze_path=tmp_path / "gaze.jsonl",
        tracker_metadata_path=tmp_path / "tracker.json",
        writer_health_path=tmp_path / "gaze_writer.json",
        clock=lambda: 12.5,
        max_queue_samples=1,
    )
    recorder._started = True
    recorder._queue.put_nowait((12.5, {"system_time_stamp": 1}))

    recorder._record_gaze_sample({"system_time_stamp": 2})

    assert recorder.writer_health()["received_queue_samples"] == 1
    assert recorder.writer_health()["dropped_queue_samples"] == 1


def test_save_current_calibration_writes_metadata_and_sdk_payload(tmp_path):
    tracker = FakeEyeTracker()
    artifact_dir = save_current_calibration(
        eyetracker=tracker,
        output_dir=tmp_path / "calibrations",
        method="tobii-pro-eye-tracker-manager",
        screen=1,
        manager_executable="/Applications/Tobii",
        manager_return_code=0,
        now=datetime(2026, 7, 28, 16, 30, 5, tzinfo=timezone.utc),
    )

    assert artifact_dir == tmp_path / "calibrations" / "calibration-20260728T163005Z"
    assert (artifact_dir / "calibration.bin").read_bytes() == b"fake-calibration-data"
    metadata = json.loads((artifact_dir / "calibration.json").read_text())
    assert metadata == {
        "schema_version": 1,
        "calibration_id": "calibration-20260728T163005Z",
        "created_at": "2026-07-28T16:30:05Z",
        "method": "tobii-pro-eye-tracker-manager",
        "screen": 1,
        "tracker": {
            "address": "tet-tcp://169.254.0.1",
            "firmware_version": "2.6.2",
            "model": "Spectrum",
            "serial_number": "TPS-123",
        },
        "calibration_data_file": "calibration.bin",
        "manager_executable": "/Applications/Tobii",
        "manager_return_code": 0,
    }


def test_save_current_calibration_avoids_overwriting_same_second_artifact(tmp_path):
    timestamp = datetime(2026, 7, 28, 16, 30, 5, tzinfo=timezone.utc)
    first = save_current_calibration(
        eyetracker=FakeEyeTracker(),
        output_dir=tmp_path / "calibrations",
        method="tobii-pro-eye-tracker-manager",
        screen=1,
        manager_executable="/Applications/Tobii",
        manager_return_code=0,
        now=timestamp,
    )
    second = save_current_calibration(
        eyetracker=FakeEyeTracker(),
        output_dir=tmp_path / "calibrations",
        method="tobii-pro-eye-tracker-manager",
        screen=1,
        manager_executable="/Applications/Tobii",
        manager_return_code=0,
        now=timestamp,
    )

    assert first.name == "calibration-20260728T163005Z"
    assert second.name == "calibration-20260728T163005Z-2"


def test_run_eyetracker_manager_calibration_discovers_tracker_and_launches_manager(capsys):
    commands = []

    def installed_sdk(name):
        return FakeTobiiResearch((FakeEyeTracker(),))

    def run_command(command, check):
        commands.append({"command": command, "check": check})
        return subprocess.CompletedProcess(command, 0)

    exit_code = run_eyetracker_manager_calibration(
        screen=1,
        executable="/Applications/Tobii",
        calibration_output_dir=None,
        import_module=installed_sdk,
        run_command=run_command,
    )

    assert exit_code == 0
    assert commands == [
        {
            "command": [
                "/Applications/Tobii",
                "--mode=usercalibration",
                "--screen=1",
                "--device-address=tet-tcp://169.254.0.1",
            ],
            "check": False,
        }
    ]
    assert "calibration completed" in capsys.readouterr().out


def test_run_eyetracker_manager_calibration_saves_successful_calibration(tmp_path, capsys):
    def installed_sdk(name):
        return FakeTobiiResearch((FakeEyeTracker(),))

    def run_command(command, check):
        return subprocess.CompletedProcess(command, 0)

    exit_code = run_eyetracker_manager_calibration(
        screen=1,
        executable="/Applications/Tobii",
        calibration_output_dir=tmp_path / "calibrations",
        import_module=installed_sdk,
        run_command=run_command,
        now=lambda: datetime(2026, 7, 28, 16, 30, 5, tzinfo=timezone.utc),
    )

    assert exit_code == 0
    artifact_dir = tmp_path / "calibrations" / "calibration-20260728T163005Z"
    assert (artifact_dir / "calibration.bin").read_bytes() == b"fake-calibration-data"
    assert "Saved calibration data to" in capsys.readouterr().out


def test_run_eyetracker_manager_calibration_captures_manager_output(tmp_path, capsys):
    def installed_sdk(name):
        return FakeTobiiResearch((FakeEyeTracker(),))

    manager = tmp_path / "fake-etm"
    manager.write_text(
        "#!/bin/sh\n"
        "echo 'etm stdout line'\n"
        "echo 'etm stderr line' >&2\n"
        "exit 0\n",
        encoding="utf-8",
    )
    manager.chmod(0o755)

    exit_code = run_eyetracker_manager_calibration(
        address="tobii-prp://169.254.10.180",
        screen=1,
        executable=str(manager),
        calibration_output_dir=tmp_path / "calibrations",
        import_module=installed_sdk,
        now=lambda: datetime(2026, 7, 28, 16, 30, 5, tzinfo=timezone.utc),
    )

    assert exit_code == 0
    artifact_dir = tmp_path / "calibrations" / "calibration-20260728T163005Z"
    log_path = artifact_dir / "etm.log"
    assert log_path.read_text(encoding="utf-8") == (
        "etm stdout line\netm stderr line\n"
    )
    metadata = json.loads((artifact_dir / "calibration.json").read_text())
    assert metadata["etm_log_file"] == "etm.log"
    captured = capsys.readouterr()
    assert "etm stdout line" in captured.out
    assert "etm stderr line" in captured.out


def test_run_eyetracker_manager_calibration_can_target_serial_number():
    commands = []

    def run_command(command, check):
        commands.append(command)
        return subprocess.CompletedProcess(command, 31)

    exit_code = run_eyetracker_manager_calibration(
        serial_number="TPSP1-010214213025",
        screen=2,
        executable="/Applications/Tobii",
        calibration_output_dir=None,
        run_command=run_command,
    )

    assert exit_code == 31
    assert commands == [
        [
            "/Applications/Tobii",
            "--mode=usercalibration",
            "--screen=2",
            "--device-sn=TPSP1-010214213025",
        ]
    ]


def test_run_eyetracker_manager_calibration_rejects_address_and_serial(capsys):
    exit_code = run_eyetracker_manager_calibration(
        address="tobii-prp://169.254.10.180",
        serial_number="TPSP1-010214213025",
    )

    assert exit_code == 51
    assert "either --address or --serial-number" in capsys.readouterr().err
