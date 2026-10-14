import json
import math
import random
import sys
from types import SimpleNamespace

import pytest

from aria_et.psychopy.calibration import (
    CALIBRATION_METHOD,
    RESULTS_KEYS_HINT,
    describe_validation,
    run_child_friendly_calibration_demo,
    run_child_friendly_eyetracker_calibration,
    run_validation,
)

# A 527 x 296 mm screen; the eye sits 650 mm in front of its centre.
DISPLAY_AREA = SimpleNamespace(
    top_left=(-263.5, 148.0, 0.0),
    top_right=(263.5, 148.0, 0.0),
    bottom_left=(-263.5, -148.0, 0.0),
)
EYE_ORIGIN = (0.0, 0.0, 650.0)
SCREEN_CENTRE = (0.0, 0.0, 0.0)
GAZE_STREAM = "gaze_data"


class FakeTracker:
    """A tracker whose gaze stream always looks at the screen centre."""

    address = "tobii-prp://169.254.10.180"
    model = "Tobii Pro Spectrum"
    firmware_version = "2.6.2"

    def __init__(self, serial_number="TPS-123"):
        self.serial_number = serial_number
        self.subscribers = []
        self.unsubscribed = []

    def retrieve_calibration_data(self):
        return b"detox-calibration"

    def get_display_area(self):
        return DISPLAY_AREA

    def subscribe_to(self, stream, callback, as_dictionary=False):
        assert stream == GAZE_STREAM and as_dictionary
        self.subscribers.append(callback)

    def unsubscribe_from(self, stream, callback=None):
        self.unsubscribed.append(stream)
        self.subscribers.remove(callback)

    def emit_gaze(self):
        sample = {}
        for eye in ("left", "right"):
            sample[f"{eye}_gaze_origin_in_user_coordinate_system"] = EYE_ORIGIN
            sample[f"{eye}_gaze_point_in_user_coordinate_system"] = SCREEN_CENTRE
            sample[f"{eye}_gaze_point_on_display_area"] = (0.5, 0.5)
            sample[f"{eye}_gaze_origin_validity"] = 1
            sample[f"{eye}_gaze_point_validity"] = 1
        for callback in list(self.subscribers):
            callback(sample)


class FakeWindow:
    size = (1920, 1080)
    clientSize = (1920, 1080)

    def __init__(self):
        self.closed = False
        self.tracker = None  # set by tests: each flip delivers one gaze sample

    def flip(self):
        if self.tracker is not None:
            self.tracker.emit_gaze()

    def close(self):
        self.closed = True


class FakeStim:
    created = []  # every stimulus built, so tests can inspect the results screen

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.size = kwargs.get("size")
        FakeStim.created.append(self)

    def draw(self):
        pass


class FakeElementArray(FakeStim):
    pass


class FakeSound:
    instances = []

    def __init__(self, path, loops=0):
        self.path = path
        self.plays = 0
        FakeSound.instances.append(self)

    def play(self):
        self.plays += 1

    def stop(self):
        pass

    def setVolume(self, volume):
        self.volumes = getattr(self, "volumes", []) + [volume]


class FakeKeys:
    """Scripted keypresses: each getKeys call pops the next batch, then Space."""

    def __init__(self, script=()):
        self.script = list(script)

    def getKeys(self, keyList=None):
        return self.script.pop(0) if self.script else ["space"]

    def clearEvents(self):
        pass


class FakeClock:
    def __init__(self):
        self.time = 0.0

    def getTime(self):
        self.time += 0.1
        return self.time


@pytest.fixture
def keys():
    return FakeKeys()


@pytest.fixture
def window(monkeypatch, keys):
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
        visual=SimpleNamespace(
            Window=lambda **kwargs: window,
            TextStim=FakeStim,
            ImageStim=FakeStim,
            Circle=FakeStim,
            ElementArrayStim=FakeElementArray,
        ),
        core=SimpleNamespace(Clock=FakeClock),
        event=keys,
        sound=SimpleNamespace(Sound=FakeSound),
    )
    monkeypatch.setitem(sys.modules, "psychopy", fake_psychopy)
    return window


# Where a real DeToX 5-point calibration puts its targets, as Tobii reports them.
DETOX_POSITIONS = [[0.9, 0.9], [0.9, 0.1], [0.1, 0.9], [0.1, 0.1], [0.5, 0.5]]


class FakeCalibrationResult:
    status = "success"

    def __init__(self, positions=DETOX_POSITIONS):
        self.calibration_points = [
            SimpleNamespace(position_on_display_area=tuple(position))
            for position in positions
        ]


class FakeDetox:
    """Stands in for the DeToX package; records how ETracker is driven."""

    def __init__(
        self,
        trackers,
        *,
        calibrate_result=True,
        stimulus_dir=None,
        positions=DETOX_POSITIONS,
    ):
        self.trackers = trackers
        # One result per calibrate() call; the last one repeats.
        self.calibrate_results = (
            list(calibrate_result)
            if isinstance(calibrate_result, list)
            else [calibrate_result]
        )
        self.calibrate_calls = 0
        self.controllers = []
        if stimulus_dir is not None:
            self.__file__ = str(stimulus_dir.parent / "__init__.py")
        detox = self

        class ETracker:
            def __init__(self, win, etracker_id=0, simulate=False, verbose=True):
                self.win = win
                self.etracker_id = etracker_id
                self.simulate = simulate
                self.eyetracker = None if simulate else detox.trackers[etracker_id]
                self.calibration = SimpleNamespace(
                    compute_and_apply=lambda: FakeCalibrationResult(positions)
                )
                self.calls = []
                detox.controllers.append(self)

            def show_status(self):
                self.calls.append(("show_status",))

            def calibrate(self, **kwargs):
                self.calls.append(("calibrate", kwargs))
                results = detox.calibrate_results
                succeeded = results[min(detox.calibrate_calls, len(results) - 1)]
                detox.calibrate_calls += 1
                if succeeded and not self.simulate:
                    # DeToX computes through its calibration object, then drops it.
                    self.calibration.compute_and_apply()
                return succeeded

        self.ETracker = ETracker


def _import_module(trackers, detox):
    fake_tobii = SimpleNamespace(
        __version__="2.1.0",
        EYETRACKER_GAZE_DATA=GAZE_STREAM,
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


@pytest.fixture
def stimulus_dir(tmp_path):
    stimuli = tmp_path / "DeToX" / "stimuli"
    stimuli.mkdir(parents=True)
    (stimuli / "cute_cat.png").write_bytes(b"png")
    (stimuli / "CalibrationSound.wav").write_bytes(b"wav")
    return stimuli


def _calibrate(
    tmp_path, window, *, stimulus_dir=None, positions=DETOX_POSITIONS, **kwargs
):
    tracker = FakeTracker()
    window.tracker = tracker
    detox = FakeDetox([tracker], stimulus_dir=stimulus_dir, positions=positions)
    exit_code = run_child_friendly_eyetracker_calibration(
        calibration_output_dir=tmp_path / "calibrations",
        import_module=_import_module([tracker], detox),
        status_sink=lambda message: None,
        **kwargs,
    )
    artifact_dir = next((tmp_path / "calibrations").iterdir())
    metadata = json.loads((artifact_dir / "calibration.json").read_text())
    return exit_code, metadata, tracker


def test_calibration_saves_point_positions_and_validation_quality(
    tmp_path, window, stimulus_dir
):
    FakeSound.instances.clear()

    exit_code, metadata, tracker = _calibrate(
        tmp_path, window, stimulus_dir=stimulus_dir
    )

    assert exit_code == 0
    assert metadata["calibration_points"] == {
        "count": 5,
        "positions_adcs": DETOX_POSITIONS,
    }
    validation = metadata["validation"]
    # Validation targets are the calibration's own positions.
    assert validation["points_adcs"] == DETOX_POSITIONS
    assert sorted(p["target_adcs"] for p in validation["points"]) == sorted(
        DETOX_POSITIONS
    )
    assert validation["status"] == "complete"
    assert len(validation["points"]) == 5
    # The fake gaze always hits the screen centre, so the centre target is exact.
    centre = next(p for p in validation["points"] if p["target_adcs"] == [0.5, 0.5])
    assert centre["left"]["accuracy_deg"] == pytest.approx(0.0, abs=1e-6)
    assert centre["left"]["data_loss"] == 0.0
    assert centre["left"]["n_samples"] > 0
    summary = validation["summary"]
    assert summary["left"]["accuracy_deg"] > 0
    assert summary["right"]["max_accuracy_deg"] >= summary["right"]["accuracy_deg"]
    # Gaze is only subscribed during validation, and the sound plays per target.
    assert tracker.subscribers == []
    assert tracker.unsubscribed == [GAZE_STREAM]
    assert FakeSound.instances[0].plays == 5


def test_escape_at_the_validation_instructions_skips_validation(
    tmp_path, window, keys
):
    keys.script = [["escape"]]

    exit_code, metadata, _ = _calibrate(tmp_path, window)

    assert exit_code == 0  # the calibration is kept
    assert metadata["validation"]["status"] == "skipped"
    assert metadata["validation"]["summary"] is None


def test_escape_during_validation_keeps_the_collected_points(tmp_path, window, keys):
    # Start, collect two targets, then Escape on the third.
    keys.script = [[], ["space"], ["space"], ["space"], ["escape"]]

    _, metadata, tracker = _calibrate(tmp_path, window)

    validation = metadata["validation"]
    assert validation["status"] == "partial"
    assert len(validation["points"]) == 2
    assert validation["summary"]["left"]["data_loss"] == 0.0
    assert tracker.subscribers == []


def test_validation_shuffles_targets_with_the_given_rng(window):
    tracker = FakeTracker()
    window.tracker = tracker

    validation = run_validation(
        window,
        eyetracker=tracker,
        tobii_research=SimpleNamespace(EYETRACKER_GAZE_DATA=GAZE_STREAM),
        stimulus_dir=None,
        play_sound=True,
        status=lambda message: None,
        rng=random.Random(0),
    )

    order = [point["target_adcs"] for point in validation["points"]]
    expected = [list(p) for p in validation["points_adcs"]]
    random.Random(0).shuffle(expected)
    assert order == expected


def test_describe_validation_summarizes_both_eyes():
    validation = {
        "status": "complete",
        "summary": {
            "left": {
                "accuracy_deg": 0.72,
                "precision_rms_deg": 0.07,
                "data_loss": 0.0,
                "max_accuracy_deg": 1.0,
            },
            "right": {
                "accuracy_deg": 0.61,
                "precision_rms_deg": None,
                "data_loss": 0.25,
                "max_accuracy_deg": 0.9,
            },
        },
    }

    assert describe_validation(validation) == (
        "Validation complete: accuracy L 0.72° R 0.61°; "
        "precision L 0.07° R n/a; data loss L 0.00% R 25.00%."
    )
    assert describe_validation({"status": "skipped", "summary": None}) == (
        "Validation skipped."
    )


def test_validation_falls_back_to_the_detox_layout_without_recorded_points(
    tmp_path, window
):
    _, metadata, _ = _calibrate(tmp_path, window, positions=[])

    assert metadata["calibration_points"]["count"] == 0
    assert sorted(metadata["validation"]["points_adcs"]) == sorted(DETOX_POSITIONS)


class SteppedClock:
    """A clock that returns preset times, one per call."""

    def __init__(self, times):
        self.times = list(times)

    def getTime(self):
        return self.times.pop(0)


def test_validation_zoom_matches_detox_calibration_animation():
    from aria_et.psychopy.calibration import DetoxAnimationDefaults, _Target

    settings = DetoxAnimationDefaults()
    period = 2 * math.pi / settings.zoom_speed
    window = FakeWindow()
    target = _Target(
        window,
        SimpleNamespace(ImageStim=FakeStim, Circle=FakeStim),
        SimpleNamespace(Clock=lambda: SteppedClock([0.0, period / 4, period / 2])),
        (0.1, 0.1),
        ["cat.png"],
        0,
        animation="zoom",
        settings=settings,
    )
    height = window.size[1]

    sizes = []
    for _ in range(3):
        target.draw()
        sizes.append(target._stim.size)

    # DeToX: size = min + (cos(t * zoom_speed) + 1) / 2 * (max - min), in screen heights.
    assert sizes[0] == pytest.approx(0.16 * height)  # starts at max
    assert sizes[1] == pytest.approx((0.05 + 0.16) / 2 * height)
    assert sizes[2] == pytest.approx(0.05 * height)  # half a cycle later: min
    assert target._stim.kwargs["pos"] == pytest.approx((-768.0, 432.0))
    assert target._stim.kwargs["interpolate"] is True


def test_validation_trill_rotates_at_a_fixed_size():
    from aria_et.psychopy.calibration import DetoxAnimationDefaults, _Target

    settings = DetoxAnimationDefaults()
    target = _Target(
        FakeWindow(),
        SimpleNamespace(ImageStim=FakeStim, Circle=FakeStim),
        SimpleNamespace(Clock=lambda: SteppedClock([1 / 12, 1.3])),
        (0.5, 0.5),
        [],
        0,
        animation="trill",
        settings=settings,
    )

    target.draw()
    assert target._stim.size == pytest.approx(0.14 * 1080)
    assert target._stim.ori == pytest.approx(settings.trill_rotation_range)
    target.draw()  # 1.3 s is in the pause after the 1.1 s active phase
    assert target._stim.ori == 0


def test_animation_defaults_match_the_installed_detox():
    import importlib.util
    import subprocess

    # find_spec, not importorskip: importing DeToX here would import PsychoPy.
    if importlib.util.find_spec("DeToX") is None:
        pytest.skip("DeToX not installed")

    from aria_et.psychopy.calibration import DetoxAnimationDefaults

    names = [name for name in vars(DetoxAnimationDefaults) if not name.startswith("_")]
    # In a subprocess: importing DeToX imports PsychoPy, which other tests forbid.
    script = (
        "import json; from DeToX import ETSettings as cfg; "
        f"print(json.dumps({{n: getattr(cfg.animation, n) for n in {names!r}}}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    installed = json.loads(result.stdout.strip().splitlines()[-1])

    assert installed == {name: getattr(DetoxAnimationDefaults, name) for name in names}


def _validate(window, **kwargs):
    tracker = FakeTracker()
    window.tracker = tracker
    return run_validation(
        window,
        eyetracker=tracker,
        tobii_research=SimpleNamespace(EYETRACKER_GAZE_DATA=GAZE_STREAM),
        status=lambda message: None,
        points=[(0.5, 0.5)],
        **kwargs,
    )


def test_validation_settle_uses_detox_focus_time(window):
    from aria_et.psychopy.calibration import DetoxAnimationDefaults

    default = _validate(window, stimulus_dir=None, play_sound=False)
    tuned_settings = DetoxAnimationDefaults()
    tuned_settings.focus_time = 1.0
    tuned = _validate(
        window,
        stimulus_dir=None,
        play_sound=False,
        animation_settings=tuned_settings,
    )

    assert default["settle_seconds"] == 0.5  # DeToX's focus_time
    assert tuned["settle_seconds"] == 1.0


def test_validation_fades_the_sound_during_the_settle(window, stimulus_dir):
    FakeSound.instances.clear()

    _validate(window, stimulus_dir=stimulus_dir, play_sound=True)

    volumes = FakeSound.instances[0].volumes
    fade = [volume for volume in volumes if volume < 1.0]
    assert len(fade) >= 3
    assert fade == sorted(fade, reverse=True)  # only ever gets quieter
    assert volumes[-1] == 1.0  # reset, ready for the next target


# Keypress scripts: start the validation, collect the 5 targets, then this key
# on the results screen. Unscripted calls return Space, which accepts.
VALIDATE_THEN = [["space"]] * 6


def test_results_screen_accepts_and_saves_one_attempt(tmp_path, window):
    FakeStim.created.clear()

    exit_code, metadata, _ = _calibrate(tmp_path, window)

    assert exit_code == 0
    assert metadata["calibration_attempts"] == 1
    assert metadata["validation_attempts"] == 1
    assert window.closed
    texts = [stim.kwargs.get("text") for stim in FakeStim.created]
    assert RESULTS_KEYS_HINT in texts
    assert "Accuracy (deg)" in texts


def test_results_screen_can_revalidate(tmp_path, window, keys):
    keys.script = VALIDATE_THEN + [["v"]]

    _, metadata, tracker = _calibrate(tmp_path, window)

    assert metadata["validation_attempts"] == 2
    assert metadata["calibration_attempts"] == 1
    assert metadata["validation"]["status"] == "complete"
    assert tracker.unsubscribed == [GAZE_STREAM, GAZE_STREAM]


def test_results_screen_can_recalibrate(tmp_path, window, keys):
    keys.script = VALIDATE_THEN + [["c"]]
    tracker = FakeTracker()
    window.tracker = tracker
    detox = FakeDetox([tracker])

    run_child_friendly_eyetracker_calibration(
        calibration_output_dir=tmp_path / "calibrations",
        import_module=_import_module([tracker], detox),
        status_sink=lambda message: None,
    )

    metadata = json.loads(
        next((tmp_path / "calibrations").glob("*/calibration.json")).read_text()
    )
    calls = [call[0] for call in detox.controllers[0].calls]
    # Re-calibrating shows the positioning screen again, then DeToX.
    assert calls == ["show_status", "calibrate", "show_status", "calibrate"]
    assert metadata["calibration_attempts"] == 2
    assert metadata["validation_attempts"] == 2


def test_aborted_recalibration_keeps_the_previous_results(tmp_path, window, keys):
    keys.script = VALIDATE_THEN + [["c"]]
    tracker = FakeTracker()
    window.tracker = tracker
    detox = FakeDetox([tracker], calibrate_result=[True, False])
    messages = []

    exit_code = run_child_friendly_eyetracker_calibration(
        calibration_output_dir=tmp_path / "calibrations",
        import_module=_import_module([tracker], detox),
        status_sink=messages.append,
    )

    metadata = json.loads(
        next((tmp_path / "calibrations").glob("*/calibration.json")).read_text()
    )
    assert exit_code == 0
    assert detox.calibrate_calls == 2
    # No new validation: the first calibration (still active) is saved.
    assert metadata["calibration_attempts"] == 1
    assert metadata["validation_attempts"] == 1
    assert any("previous calibration is still active" in m for m in messages)


def test_escape_on_the_results_screen_still_saves(tmp_path, window, keys):
    keys.script = VALIDATE_THEN + [["escape"]]

    exit_code, metadata, _ = _calibrate(tmp_path, window)

    assert exit_code == 0
    assert metadata["validation"]["status"] == "complete"


def test_results_screen_explains_a_skipped_validation(tmp_path, window, keys):
    keys.script = [["escape"]]  # skip validation at its instructions
    FakeStim.created.clear()

    _, metadata, _ = _calibrate(tmp_path, window)

    texts = [stim.kwargs.get("text") for stim in FakeStim.created]
    assert metadata["validation"]["status"] == "skipped"
    assert "Validation skipped: no calibration quality to show." in texts
    assert not [s for s in FakeStim.created if isinstance(s, FakeElementArray)]


def test_results_screen_plots_valid_gaze_per_eye_in_detox_colours():
    from aria_et.psychopy.calibration import DetoxColorDefaults, _results_stimuli

    FakeStim.created.clear()
    validation = {
        "status": "complete",
        "points_adcs": [[0.5, 0.5], [0.1, 0.1]],
        "points": [{}, {}],
        "summary": {
            "left": {"accuracy_deg": 0.761, "precision_rms_deg": 0.07, "data_loss": 0.0},
            "right": {"accuracy_deg": 0.94, "precision_rms_deg": 0.06, "data_loss": 0.0},
        },
    }
    gaze = [
        {"target_adcs": [0.5, 0.5], "left": [(0.5, 0.5), (0.5, 0.5)], "right": [(0.5, 0.5)]},
        {"target_adcs": [0.1, 0.1], "left": [(0.1, 0.1)], "right": []},
    ]
    colors = {
        "left": DetoxColorDefaults.left_eye,
        "right": DetoxColorDefaults.right_eye,
    }

    stimuli = _results_stimuli(
        FakeWindow(),
        SimpleNamespace(
            TextStim=FakeStim, Circle=FakeStim, ElementArrayStim=FakeElementArray
        ),
        validation,
        gaze,
        colors,
    )

    arrays = [s for s in stimuli if isinstance(s, FakeElementArray)]
    assert [a.kwargs["nElements"] for a in arrays] == [3, 1]  # left, right
    assert arrays[0].kwargs["xys"][0] == (0.0, 0.0)  # screen centre in pix
    assert arrays[0].kwargs["colors"] == DetoxColorDefaults.left_eye[:3]
    assert arrays[1].kwargs["colors"] == DetoxColorDefaults.right_eye[:3]
    texts = [s.kwargs.get("text") for s in stimuli]
    # The same formatting as the GUI quality card.
    assert ["0.76", "0.94"] == [t for t in texts if t in ("0.76", "0.94")]
    # Two markers (ring + centre) per target.
    assert sum(1 for s in stimuli if "radius" in s.kwargs) == 4


def test_eye_colour_defaults_match_the_installed_detox():
    import importlib.util
    import subprocess

    from aria_et.psychopy.calibration import DetoxColorDefaults

    # find_spec, not importorskip: importing DeToX here would import PsychoPy.
    if importlib.util.find_spec("DeToX") is None:
        pytest.skip("DeToX not installed")
    script = (
        "import json; from DeToX import ETSettings as cfg; "
        "print(json.dumps([list(cfg.colors.left_eye), list(cfg.colors.right_eye)]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    left, right = json.loads(result.stdout.strip().splitlines()[-1])

    assert tuple(left) == DetoxColorDefaults.left_eye
    assert tuple(right) == DetoxColorDefaults.right_eye
