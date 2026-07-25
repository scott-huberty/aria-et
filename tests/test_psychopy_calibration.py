import sys
from dataclasses import dataclass, field
from random import Random

from aria_et.calibration import build_gap_overlap_reward_calibration_sequence
from aria_et.psychopy.calibration import PsychoPyCalibrationPresenter, StatusLoggingEventSink
from aria_et.runtime import ManualClock, RecordingEventSink


@dataclass
class FakeWindow:
    size: tuple[float, float] = (1000, 800)
    clientSize: tuple[float, float] | None = None
    flips: int = 0

    def __post_init__(self):
        if self.clientSize is None:
            self.clientSize = self.size

    def flip(self) -> None:
        self.flips += 1


@dataclass
class FakeImage:
    path: str
    pos: tuple[float, float]
    size: tuple[float, float]
    draws: list[str]

    def draw(self) -> None:
        self.draws.append(self.path)


@dataclass
class FakeSound:
    path: str
    played: list[str]

    def play(self) -> None:
        self.played.append(self.path)


@dataclass
class FakePsychoPyFactories:
    images: list[FakeImage] = field(default_factory=list)
    sounds: list[FakeSound] = field(default_factory=list)
    draws: list[str] = field(default_factory=list)
    played: list[str] = field(default_factory=list)
    waits: list[float] = field(default_factory=list)

    def make_image(self, window, image, pos, size):
        fake_image = FakeImage(image, pos, size, self.draws)
        self.images.append(fake_image)
        return fake_image

    def make_sound(self, path):
        fake_sound = FakeSound(path, self.played)
        self.sounds.append(fake_sound)
        return fake_sound

    def wait(self, seconds):
        self.waits.append(seconds)


def make_presenter(window, factories, **overrides):
    return PsychoPyCalibrationPresenter(
        window=window,
        image_factory=factories.make_image,
        sound_factory=factories.make_sound,
        wait=factories.wait,
        **overrides,
    )


def test_psychopy_presenter_presents_calibration_points_in_order():
    sequence = build_gap_overlap_reward_calibration_sequence()
    window = FakeWindow()
    factories = FakePsychoPyFactories()
    event_sink = RecordingEventSink()

    result = make_presenter(
        window,
        factories,
        point_duration_seconds=0.2,
        frame_duration_seconds=0.1,
    ).present(sequence, ManualClock(timestamp=1), event_sink)

    assert [point.label for point in result.presented_points] == [
        "center",
        "top-left",
        "top-right",
        "bottom-right",
        "bottom-left",
    ]
    assert [event.name for event in event_sink.events][0] == "calibration.started"
    assert [event.name for event in event_sink.events][-1] == "calibration.ended"


def test_psychopy_presenter_maps_normalized_positions_to_pixel_positions():
    sequence = build_gap_overlap_reward_calibration_sequence()
    window = FakeWindow(size=(1000, 800))
    factories = FakePsychoPyFactories()

    make_presenter(
        window,
        factories,
        point_duration_seconds=0.1,
        frame_duration_seconds=0.1,
    ).present(sequence, ManualClock(), RecordingEventSink())

    assert [image.pos for image in factories.images] == [
        (0.0, 0.0),
        (-400.0, 320.0),
        (400.0, 320.0),
        (400.0, -320.0),
        (-400.0, -320.0),
    ]


def test_psychopy_presenter_uses_client_size_for_retina_window_positions():
    sequence = build_gap_overlap_reward_calibration_sequence()
    window = FakeWindow(size=(2000, 1600), clientSize=(1000, 800))
    factories = FakePsychoPyFactories()

    make_presenter(
        window,
        factories,
        point_duration_seconds=0.1,
        frame_duration_seconds=0.1,
    ).present(sequence, ManualClock(), RecordingEventSink())

    assert [image.pos for image in factories.images] == [
        (0.0, 0.0),
        (-400.0, 320.0),
        (400.0, 320.0),
        (400.0, -320.0),
        (-400.0, -320.0),
    ]


def test_psychopy_presenter_emits_window_positions_with_point_start_events():
    sequence = build_gap_overlap_reward_calibration_sequence()
    window = FakeWindow(size=(1000, 800))
    factories = FakePsychoPyFactories()
    event_sink = RecordingEventSink()

    make_presenter(
        window,
        factories,
        point_duration_seconds=0.1,
        frame_duration_seconds=0.1,
    ).present(sequence, ManualClock(), event_sink)

    point_starts = [
        event for event in event_sink.events if event.name == "calibration.point.started"
    ]
    assert [
        (event.payload["label"], event.payload["window_x"], event.payload["window_y"])
        for event in point_starts
    ] == [
        ("center", 0.0, 0.0),
        ("top-left", -400.0, 320.0),
        ("top-right", 400.0, 320.0),
        ("bottom-right", 400.0, -320.0),
        ("bottom-left", -400.0, -320.0),
    ]


def test_psychopy_presenter_draws_reward_animation_frames_and_flips_window():
    sequence = build_gap_overlap_reward_calibration_sequence(rng=Random(1))
    window = FakeWindow()
    factories = FakePsychoPyFactories()

    make_presenter(
        window,
        factories,
        point_duration_seconds=0.3,
        frame_duration_seconds=0.1,
    ).present(sequence, ManualClock(), RecordingEventSink())

    assert len(factories.images) == 15
    assert len(factories.draws) == 15
    assert window.flips == 15
    assert factories.waits == [0.1] * 15
    assert factories.images[0].path.endswith("frame_001.png")
    assert factories.images[1].path.endswith("frame_002.png")
    assert factories.images[2].path.endswith("frame_003.png")
    assert factories.images[0].pos == (0.0, 0.0)
    assert factories.images[0].size == (120, 120)


def test_psychopy_presenter_can_log_frame_level_render_progress():
    sequence = build_gap_overlap_reward_calibration_sequence(rng=Random(0))
    window = FakeWindow()
    factories = FakePsychoPyFactories()
    statuses = []

    make_presenter(
        window,
        factories,
        point_duration_seconds=0.1,
        frame_duration_seconds=0.1,
        render_status=statuses.append,
    ).present(sequence, ManualClock(), RecordingEventSink())

    assert statuses[:6] == [
        "Animation started: center frame_count=1 frame_duration=0.1",
        "Frame image create: center frame=1/1",
        "Frame draw: center frame=1/1",
        "Frame flip: center frame=1/1",
        "Frame wait: center frame=1/1",
        "Frame done: center frame=1/1",
    ]
    assert "Animation ended: center" in statuses
    assert "Waiting for advance" not in statuses


def test_psychopy_presenter_plays_reward_sound_for_each_point():
    sequence = build_gap_overlap_reward_calibration_sequence()
    window = FakeWindow()
    factories = FakePsychoPyFactories()
    presenter = make_presenter(window, factories)

    presenter.present(sequence, ManualClock(), RecordingEventSink())

    assert len(factories.sounds) == 5
    assert all(path.endswith(".wav") for path in factories.played)
    assert all("snd_gap_rew" in path for path in factories.played)
    assert presenter._active_sounds == factories.sounds


def test_psychopy_presenter_can_disable_sound():
    sequence = build_gap_overlap_reward_calibration_sequence()
    window = FakeWindow()
    factories = FakePsychoPyFactories()

    make_presenter(window, factories, play_sound=False).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert factories.sounds == []
    assert factories.played == []


def test_psychopy_presenter_can_abort_between_animation_frames():
    sequence = build_gap_overlap_reward_calibration_sequence()
    window = FakeWindow()
    factories = FakePsychoPyFactories()
    event_sink = RecordingEventSink()
    checks = 0

    def abort_after_first_frame():
        nonlocal checks
        checks += 1
        return checks > 2

    result = make_presenter(
        window,
        factories,
        point_duration_seconds=0.3,
        frame_duration_seconds=0.1,
        abort_requested=abort_after_first_frame,
    ).present(sequence, ManualClock(), event_sink)

    assert result.presented_points == ()
    assert window.flips == 1
    assert [event.name for event in event_sink.events][-2:] == [
        "calibration.aborted",
        "calibration.ended",
    ]


def test_psychopy_presenter_can_wait_for_advance_between_points():
    sequence = build_gap_overlap_reward_calibration_sequence()
    window = FakeWindow()
    factories = FakePsychoPyFactories()
    checks = 0

    def advance_after_one_wait():
        nonlocal checks
        checks += 1
        return checks % 2 == 0

    result = make_presenter(
        window,
        factories,
        point_duration_seconds=0.1,
        frame_duration_seconds=0.1,
        advance_requested=advance_after_one_wait,
    ).present(sequence, ManualClock(), RecordingEventSink())

    assert [point.label for point in result.presented_points] == [
        "center",
        "top-left",
        "top-right",
        "bottom-right",
        "bottom-left",
    ]
    assert len(factories.waits) == 10


def test_psychopy_presenter_can_abort_while_waiting_for_advance():
    sequence = build_gap_overlap_reward_calibration_sequence()
    window = FakeWindow()
    factories = FakePsychoPyFactories()
    event_sink = RecordingEventSink()
    abort_checks = 0

    def never_advance():
        return False

    def abort_after_one_wait():
        nonlocal abort_checks
        abort_checks += 1
        return abort_checks > 1

    result = make_presenter(
        window,
        factories,
        point_duration_seconds=0.1,
        frame_duration_seconds=0.1,
        advance_requested=never_advance,
        abort_requested=abort_after_one_wait,
    ).present(sequence, ManualClock(), event_sink)

    assert result.presented_points == ()
    assert [event.name for event in event_sink.events][-2:] == [
        "calibration.aborted",
        "calibration.ended",
    ]


def test_status_logging_event_sink_logs_point_progression():
    delegate = RecordingEventSink()
    statuses = []
    sink = StatusLoggingEventSink(delegate, statuses.append)

    sink.emit(
        delegate_event(
            "calibration.point.started",
            {
                "label": "top-left",
                "x": 0.1,
                "y": 0.1,
                "window_x": -400.0,
                "window_y": 320.0,
            },
        )
    )
    sink.emit(delegate_event("calibration.point.ended", {"label": "top-left"}))

    assert [event.name for event in delegate.events] == [
        "calibration.point.started",
        "calibration.point.ended",
    ]
    assert statuses == [
        "Point started: top-left normalized=(0.1, 0.1) window=(-400.0, 320.0)",
        "Point ended: top-left",
    ]


def delegate_event(name, payload):
    from aria_et.runtime import RuntimeEvent

    return RuntimeEvent(name, 0.0, payload)


def test_importing_psychopy_presenter_does_not_import_psychopy():
    assert "psychopy" not in sys.modules
