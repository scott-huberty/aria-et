import gc
import threading
from importlib import metadata
from types import SimpleNamespace

import pytest

from aria_et.activity_monitoring import build_activity_monitoring_sequence
from aria_et.psychopy.activity_monitoring import PsychoPyActivityMonitoringPresenter
from aria_et.psychopy.static_social_scenes import PsychoPyStaticSocialScenesPresenter
from aria_et.psychopy.textures import clear_image_textures
from aria_et.runtime import ManualClock, RecordingEventSink
from aria_et.static_social_scenes import build_static_social_scenes_sequence


def test_imagestim_workaround_still_needed():
    # psychopy#7844 is expected in 2027.1.0; verify its inclusion, then remove
    # the workaround and this test. No new dependency needed to compare versions.
    version = metadata.version("psychopy")
    release = tuple(int(part) for part in version.split(".")[:2])
    assert release < (2027, 1), (
        "PsychoPy may now include #7844: remove the ImageStim texture-cleanup "
        "workaround and this test after verifying the upstream fix."
    )


@pytest.mark.parametrize("ids", [(), ("_texID",), ("_texID", "_maskID", "_pixBuffID")])
def test_cleanup_clears_before_removing_ids_and_is_safe_to_repeat(ids):
    calls = []
    image = SimpleNamespace(**{name: object() for name in ids})
    image.clearTextures = lambda: calls.append(
        {name: getattr(image, name) for name in ids if hasattr(image, name)}
    )
    clear_image_textures(image)
    assert set(calls[0]) == set(ids)
    assert all(not hasattr(image, name) for name in ids)
    clear_image_textures(image)
    assert calls[1] == {}


def test_draw_only_stimulus_needs_no_cleanup():
    clear_image_textures(SimpleNamespace(draw=lambda: None))


def test_failed_native_cleanup_retires_ids_and_reports_error():
    def fail():
        raise OSError("native cleanup failed")

    image = SimpleNamespace(clearTextures=fail, _texID=1, _maskID=2, _pixBuffID=3)
    with pytest.raises(OSError, match="native cleanup failed"):
        clear_image_textures(image)
    assert all(not hasattr(image, name) for name in ("_texID", "_maskID", "_pixBuffID"))


@pytest.mark.parametrize("task", ["am", "ss"])
@pytest.mark.parametrize("failure", [None, "draw", "flip", "cleanup", "sound-stop"])
def test_presenters_release_textures_and_sound_on_presentation_thread(task, failure):
    calls = []
    presentation_thread = threading.get_ident()
    elapsed = [0.0]

    def wait(seconds):
        elapsed[0] += seconds

    class Image:
        def __init__(self):
            self._texID, self._maskID, self._pixBuffID = 1, 2, 3

        def draw(self):
            calls.append("draw")
            if failure == "draw":
                raise RuntimeError("draw failed")

        def clearTextures(self):
            calls.append("clear")
            assert threading.get_ident() == presentation_thread
            assert all(
                hasattr(self, name) for name in ("_texID", "_maskID", "_pixBuffID")
            )
            if failure == "cleanup":
                raise RuntimeError("cleanup failed")

    image = Image()

    def flip():
        calls.append("flip")
        # SS has a preblank flip before drawing starts.
        if failure == "flip" and "draw" in calls:
            raise RuntimeError("flip failed")

    def stop():
        calls.append("stop")
        if failure == "sound-stop":
            raise RuntimeError("sound-stop failed")

    options = dict(
        window=SimpleNamespace(color="black", flip=flip),
        image_factory=lambda *args: image,
        sound_factory=lambda *args: SimpleNamespace(
            play=lambda: calls.append("play"), stop=stop
        ),
        wait=wait,
        frame_duration_seconds=30,
    )
    if task == "am":
        presenter = PsychoPyActivityMonitoringPresenter(
            **options, monotonic=lambda: elapsed[0]
        )
        present = lambda: presenter._present_image_trial(
            build_activity_monitoring_sequence().trials[1]
        )
    else:
        presenter = PsychoPyStaticSocialScenesPresenter(**options)
        present = lambda: presenter._present_trial(
            build_static_social_scenes_sequence().trials[0],
            ManualClock(),
            RecordingEventSink(),
        )
    if failure:
        with pytest.raises(RuntimeError, match=f"{failure} failed"):
            present()
    else:
        present()
    assert calls.count("clear") == 1
    assert calls.count("stop") == 1
    assert all(not hasattr(image, name) for name in ("_texID", "_maskID", "_pixBuffID"))


def test_later_worker_thread_collection_cannot_delete_texture_names_again():
    deletes = []
    finalized = threading.Event()

    class Image:
        def __init__(self):
            self._texID = 42
            self.cycle = self  # Defer finalization to cyclic GC, as in PsychoPy.

        def clearTextures(self):
            if hasattr(self, "_texID"):
                deletes.append((self._texID, threading.get_ident()))

        def __del__(self):
            self.clearTextures()
            finalized.set()

    was_enabled = gc.isenabled()
    gc.disable()
    try:
        image = Image()
        clear_image_textures(image)
        del image
        worker = threading.Thread(target=gc.collect)
        worker.start()
        worker.join(timeout=5)
        assert finalized.is_set()
        assert deletes == [(42, threading.get_ident())]
    finally:
        if was_enabled:
            gc.enable()
