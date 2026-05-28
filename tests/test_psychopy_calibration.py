import sys
from dataclasses import dataclass, field

from aria_et.calibration import build_pikachu_calibration_sequence
from aria_et.psychopy.calibration import PsychoPyCalibrationPresenter
from aria_et.runtime import ManualClock, RecordingEventSink


@dataclass
class FakeWindow:
    size: tuple[float, float] = (1000, 800)
    flips: int = 0

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
    sequence = build_pikachu_calibration_sequence()
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
    sequence = build_pikachu_calibration_sequence()
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


def test_psychopy_presenter_draws_animation_frames_and_flips_window():
    sequence = build_pikachu_calibration_sequence()
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
    assert factories.images[0].path.endswith("imrewspn_001.bmp")
    assert factories.images[1].path.endswith("imrewspn_002.bmp")
    assert factories.images[2].path.endswith("imrewspn_003.bmp")


def test_psychopy_presenter_plays_sound_for_each_point():
    sequence = build_pikachu_calibration_sequence()
    window = FakeWindow()
    factories = FakePsychoPyFactories()

    make_presenter(window, factories).present(sequence, ManualClock(), RecordingEventSink())

    assert len(factories.sounds) == 5
    assert all(path.endswith("pikachu.wav") for path in factories.played)


def test_psychopy_presenter_can_disable_sound():
    sequence = build_pikachu_calibration_sequence()
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
    sequence = build_pikachu_calibration_sequence()
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


def test_importing_psychopy_presenter_does_not_import_psychopy():
    assert "psychopy" not in sys.modules
