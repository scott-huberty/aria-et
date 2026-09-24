import subprocess
import sys

import pytest


pytestmark = pytest.mark.psychopy_smoke


def test_demo_calibration_gui_smoke():
    command = [
        sys.executable,
        "-m",
        "aria_et.cli",
        "demo-calibration",
        "--screen",
        "0",
        "--windowed",
        "--size",
        "800x600",
        "--point-duration",
        "0.1",
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Running Gap-Overlap reward calibration" in output
    assert "Calibration demo finished." in output
    assert "Traceback" not in output


@pytest.mark.parametrize("trial_limit, timeout", [(1, 60), (16, 420)])
def test_demo_activity_monitoring_gui_smoke(trial_limit, timeout):
    command = [
        sys.executable,
        "-m",
        "aria_et.cli",
        "demo-am",
        "--screen",
        "0",
        "--windowed",
        "--size",
        "800x600",
        "--trial-limit",
        str(trial_limit),
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Running Activity Monitoring demo." in output
    assert "Activity Monitoring demo finished." in output
    assert (
        f"Activity Monitoring ended after {trial_limit} completed trial(s)." in output
    )
    assert "Traceback" not in output
