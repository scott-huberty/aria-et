import sys
from dataclasses import dataclass, field

from aria_et.psychopy.pupillary_light_reflex import (
    PsychoPyPupillaryLightReflexPresenter,
)
from aria_et.pupillary_light_reflex import build_pupillary_light_reflex_sequence
from aria_et.runtime import ManualClock, RecordingEventSink


@dataclass
class FakeWindow:
    size: tuple[float, float] = (1000, 800)
    flips: int = 0

    def flip(self):
        self.flips += 1


@dataclass
class FakeImage:
    path: str
    draws: list[str]

    def draw(self):
        self.draws.append(self.path)


@dataclass
class FakeSound:
    path: str
    played: list[str]

    def play(self):
        self.played.append(self.path)


@dataclass
class FakeFactories:
    images: list[FakeImage] = field(default_factory=list)
    image_draws: list[str] = field(default_factory=list)
    sounds: list[FakeSound] = field(default_factory=list)
    sound_plays: list[str] = field(default_factory=list)
    waits: list[float] = field(default_factory=list)

    def make_image(self, window, image):
        fake_image = FakeImage(image, self.image_draws)
        self.images.append(fake_image)
        return fake_image

    def make_sound(self, path):
        fake_sound = FakeSound(path, self.sound_plays)
        self.sounds.append(fake_sound)
        return fake_sound

    def wait(self, seconds):
        self.waits.append(seconds)


def make_presenter(window, factories, **overrides):
    defaults = {"frame_duration_seconds": 10, "inter_trial_attention_seconds": 0}
    defaults.update(overrides)
    return PsychoPyPupillaryLightReflexPresenter(
        window=window,
        image_factory=factories.make_image,
        sound_factory=factories.make_sound,
        wait=factories.wait,
        **defaults,
    )


def test_pupillary_light_reflex_presenter_presents_trials_in_sequence_order():
    sequence = build_pupillary_light_reflex_sequence()
    window = FakeWindow()
    factories = FakeFactories()
    event_sink = RecordingEventSink()

    result = make_presenter(window, factories).present(
        sequence,
        ManualClock(timestamp=1),
        event_sink,
    )

    assert result.sequence_id == "pupillary-light-reflex"
    assert [trial.trial_id for trial in result.presented_trials] == [
        f"plr-{index:02d}" for index in range(1, 19)
    ]
    assert event_sink.events[0].name == "pupillary-light-reflex.started"
    assert event_sink.events[-1].name == "pupillary-light-reflex.ended"


def test_pupillary_light_reflex_presenter_uses_frame_and_sound_factories_with_plr_metadata():
    sequence = build_pupillary_light_reflex_sequence()
    window = FakeWindow()
    factories = FakeFactories()
    event_sink = RecordingEventSink()

    result = make_presenter(window, factories, trial_limit=2).present(
        sequence,
        ManualClock(),
        event_sink,
    )

    assert [(trial.block_id, trial.stimulus_id) for trial in result.presented_trials] == [
        ("PLR-B01-O1", "plr78"),
        ("PLR-B02-O1", "plr65"),
    ]
    assert len(factories.images) == 374
    assert factories.images[0].path.endswith("plr78/frame_001.png")
    assert factories.images[187].path.endswith("plr65/frame_001.png")
    assert factories.sound_plays[0].endswith("plr78.wav")
    assert factories.sound_plays[1].endswith("plr65.wav")
    assert event_sink.events[1].payload["frame_count"] == 187
    assert event_sink.events[1].payload["flash_frame_start"] == 80
    assert event_sink.events[1].payload["flash_frame_count"] == 4


def test_pupillary_light_reflex_presenter_reuses_preloaded_stimulus_images():
    sequence = build_pupillary_light_reflex_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories, trial_limit=5).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert len(factories.images) == 187 * 3
    assert len(factories.image_draws) == 187 * 5
    assert sum("plr78/frame_001.png" in path for path in factories.image_draws) == 2
    assert sum("plr65/frame_001.png" in path for path in factories.image_draws) == 2
    assert sum("plr71/frame_001.png" in path for path in factories.image_draws) == 1


def test_pupillary_light_reflex_presenter_shows_attention_cue_between_trials():
    sequence = build_pupillary_light_reflex_sequence()
    window = FakeWindow()
    factories = FakeFactories()
    event_sink = RecordingEventSink()

    make_presenter(
        window,
        factories,
        trial_limit=2,
        frame_duration_seconds=0.5,
        inter_trial_attention_seconds=1.0,
    ).present(
        sequence,
        ManualClock(),
        event_sink,
    )

    assert len(factories.image_draws) == (187 * 2) + 2
    assert len(factories.waits) == (187 * 2) + 2
    assert len(factories.sound_plays) == 3

    event_names = [event.name for event in event_sink.events]
    first_trial_end = event_names.index("pupillary-light-reflex.trial.ended")
    cue_start = event_names.index("pupillary-light-reflex.attention-cue.started")
    cue_end = event_names.index("pupillary-light-reflex.attention-cue.ended")
    second_trial_start = event_names.index(
        "pupillary-light-reflex.trial.started",
        first_trial_end + 1,
    )
    assert first_trial_end < cue_start < cue_end < second_trial_start


def test_pupillary_light_reflex_presenter_honors_trial_timing():
    sequence = build_pupillary_light_reflex_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories, trial_limit=2).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert len(factories.waits) == 374
    assert all(wait == 10 for wait in factories.waits)


def test_pupillary_light_reflex_presenter_draws_frames_and_emits_flash_frame_events():
    sequence = build_pupillary_light_reflex_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    event_sink = RecordingEventSink()
    make_presenter(window, factories, trial_limit=1, frame_duration_seconds=2).present(
        sequence,
        ManualClock(),
        event_sink,
    )

    assert len(factories.image_draws) == 187
    assert factories.waits == [2] * 187
    assert window.flips == 187
    flash_events = [
        event
        for event in event_sink.events
        if event.name == "pupillary-light-reflex.flash-frame.presented"
    ]
    assert [event.payload["frame_index"] for event in flash_events] == [80, 81, 82, 83]
    assert [event.payload["flash_frame_index"] for event in flash_events] == [1, 2, 3, 4]


def test_pupillary_light_reflex_presenter_can_disable_audio():
    sequence = build_pupillary_light_reflex_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories, trial_limit=1, play_sound=False).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert factories.sounds == []
    assert factories.sound_plays == []


def test_pupillary_light_reflex_presenter_can_limit_trials_for_demos():
    sequence = build_pupillary_light_reflex_sequence()
    window = FakeWindow()
    factories = FakeFactories()
    event_sink = RecordingEventSink()

    result = make_presenter(window, factories, trial_limit=2).present(
        sequence,
        ManualClock(),
        event_sink,
    )

    assert [trial.trial_id for trial in result.presented_trials] == [
        "plr-01",
        "plr-02",
    ]
    assert event_sink.events[-1].payload["trial_count"] == 2


def test_importing_pupillary_light_reflex_presenter_does_not_import_psychopy():
    assert "psychopy" not in sys.modules
