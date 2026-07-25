import sys
from dataclasses import dataclass, field

from aria_et.psychopy.static_social_scenes import PsychoPyStaticSocialScenesPresenter
from aria_et.runtime import ManualClock, RecordingEventSink
from aria_et.static_social_scenes import build_static_social_scenes_sequence


@dataclass
class FakeWindow:
    color: str | tuple[float, float, float] = "black"
    flips: int = 0
    colors: list[str | tuple[float, float, float]] = field(default_factory=list)

    def flip(self):
        self.flips += 1
        self.colors.append(self.color)


@dataclass
class FakeImage:
    path: str
    draws: list[str]

    def draw(self):
        self.draws.append(self.path)


@dataclass
class FakeSound:
    path: str
    plays: list[str]

    def play(self):
        self.plays.append(self.path)


@dataclass
class FakeFactories:
    image_draws: list[str] = field(default_factory=list)
    sound_plays: list[str] = field(default_factory=list)
    waits: list[float] = field(default_factory=list)

    def make_image(self, window, image):
        return FakeImage(image, self.image_draws)

    def make_sound(self, path):
        return FakeSound(path, self.sound_plays)

    def wait(self, seconds):
        self.waits.append(seconds)


def make_presenter(window, factories, **overrides):
    defaults = {"frame_duration_seconds": 20}
    defaults.update(overrides)
    return PsychoPyStaticSocialScenesPresenter(
        window=window,
        image_factory=factories.make_image,
        sound_factory=factories.make_sound,
        wait=factories.wait,
        **defaults,
    )


def test_static_social_scenes_presenter_presents_trials_in_sequence_order():
    sequence = build_static_social_scenes_sequence()
    window = FakeWindow()
    factories = FakeFactories()
    event_sink = RecordingEventSink()

    result = make_presenter(window, factories).present(
        sequence,
        ManualClock(timestamp=1),
        event_sink,
    )

    assert result.sequence_id == "static-social-scenes"
    assert [trial.trial_id for trial in result.presented_trials] == [
        f"ss-{index:02d}" for index in range(1, 13)
    ]
    assert [event.name for event in event_sink.events][0] == "static-social-scenes.started"
    assert [event.name for event in event_sink.events][-1] == "static-social-scenes.ended"


def test_static_social_scenes_presenter_uses_image_factory_and_background_colors():
    sequence = build_static_social_scenes_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories, trial_limit=2).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert len(factories.image_draws) == 2
    assert factories.image_draws[0].endswith("static1_f0.jpg")
    assert factories.image_draws[1].endswith("popout1_f0.jpg")
    assert window.colors == [
        (-1.0, -1.0, -1.0),
        (-1.0, -1.0, -1.0),
        (1.0, 1.0, 1.0),
        (1.0, 1.0, 1.0),
    ]


def test_static_social_scenes_presenter_honors_trial_timing():
    sequence = build_static_social_scenes_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories, trial_limit=2).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert factories.waits[:4] == [0.1, 1.5, 20, 0]
    assert factories.waits[4:8] == [0.1, 1.5, 12, 0]


def test_static_social_scenes_presenter_draws_image_frames_through_duration():
    sequence = build_static_social_scenes_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories, trial_limit=1, frame_duration_seconds=5).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert len(factories.image_draws) == 4
    assert factories.waits == [0.1, 1.5, 5, 5, 5, 5, 0]


def test_static_social_scenes_presenter_plays_soundtracks_only_when_enabled():
    sequence = build_static_social_scenes_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    presenter = make_presenter(window, factories, trial_limit=2)
    presenter.present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert len(factories.sound_plays) == 2
    assert factories.sound_plays[0].endswith("si_song2_vp080.wav")
    assert factories.sound_plays[1].endswith("si_song3_vp080.wav")
    assert [sound.path for sound in presenter._active_sounds] == factories.sound_plays

    muted_factories = FakeFactories()
    muted_presenter = make_presenter(
        window,
        muted_factories,
        trial_limit=2,
        play_sound=False,
    )
    muted_presenter.present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert muted_factories.sound_plays == []
    assert muted_presenter._active_sounds == []


def test_static_social_scenes_presenter_can_limit_trials_for_demos():
    sequence = build_static_social_scenes_sequence()
    window = FakeWindow()
    factories = FakeFactories()
    event_sink = RecordingEventSink()

    result = make_presenter(window, factories, trial_limit=2).present(
        sequence,
        ManualClock(),
        event_sink,
    )

    assert [trial.trial_id for trial in result.presented_trials] == ["ss-01", "ss-02"]
    assert event_sink.events[-1].payload["trial_count"] == 2


def test_importing_static_social_scenes_presenter_does_not_import_psychopy():
    assert "psychopy" not in sys.modules
