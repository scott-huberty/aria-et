import subprocess
import sys

import pytest


pytestmark = pytest.mark.psychopy_smoke


def test_real_image_texture_cleanup_survives_worker_thread_collection():
    # Use an AM image already fetched by the smoke CI job. Run in a child so
    # an unraisable destructor exception is captured without affecting pytest.
    script = """
import gc
import sys
import threading
import weakref
from importlib.resources import as_file
from psychopy import visual
from pyglet import gl
from aria_et.assets import activity_monitoring_assets
from aria_et.psychopy.textures import clear_image_textures

errors = []
sys.unraisablehook = lambda error: errors.append(str(error.exc_value))
window = visual.Window(size=(400, 300), screen=0, fullscr=False,
                       units='pix', checkTiming=False, autoLog=False)
live = None
try:
    with as_file(activity_monitoring_assets().image('ams_a0_s3_b3_gm_d1_f1.jpg')) as path:
        image = visual.ImageStim(window, image=str(path), autoLog=False)
        image.draw()
        window.flip()
        clear_image_textures(image)
        assert not any(hasattr(image, name) for name in ('_texID', '_maskID', '_pixBuffID'))
        image.cycle = image
        reference = weakref.ref(image)
        # A live image may reuse the freed GL names. Later destruction of the
        # old image must neither call GL on a worker nor delete the live image.
        live = visual.ImageStim(window, image=str(path), autoLog=False)
        live.draw()
        window.flip()
        was_enabled = gc.isenabled()
        gc.disable()
        try:
            del image
            worker = threading.Thread(target=gc.collect)
            worker.start()
            worker.join(timeout=10)
            assert not worker.is_alive()
            assert reference() is None
        finally:
            if was_enabled:
                gc.enable()
        assert gl.glIsTexture(live._texID.value)
        assert gl.glIsTexture(live._maskID.value)
finally:
    if live is not None:
        clear_image_textures(live)
    window.close()
assert not errors, errors
print('ImageStim worker-thread cleanup passed')
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=60
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "ImageStim worker-thread cleanup passed" in output
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
        "--no-sound",
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
