import sys
from dataclasses import dataclass, field

from aria_et.activity_monitoring import build_activity_monitoring_sequence
from aria_et.psychopy.activity_monitoring import PsychoPyActivityMonitoringPresenter
from aria_et.runtime import ManualClock, RecordingEventSink


@dataclass
class FakeWindow:
    size: tuple[float, float] = (1000, 800)
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
class FakeMovie:
    path: str
    draws: list[str]
    plays: list[str]

    def play(self):
        self.plays.append(self.path)

    def draw(self):
        self.draws.append(self.path)

    def stop(self):
        pass


@dataclass
class FakeSound:
    path: str
    plays: list[str]
    stops: list[str]

    def play(self):
        self.plays.append(self.path)

    def stop(self):
        self.stops.append(self.path)


@dataclass
class FakeFactories:
    image_draws: list[str] = field(default_factory=list)
    movie_draws: list[str] = field(default_factory=list)
    movie_plays: list[str] = field(default_factory=list)
    sound_plays: list[str] = field(default_factory=list)
    sound_stops: list[str] = field(default_factory=list)
    waits: list[float] = field(default_factory=list)

    def make_image(self, window, image):
        return FakeImage(image, self.image_draws)

    def make_movie(self, window, movie):
        return FakeMovie(movie, self.movie_draws, self.movie_plays)

    def make_sound(self, path):
        return FakeSound(path, self.sound_plays, self.sound_stops)

    def wait(self, seconds):
        self.waits.append(seconds)


def make_presenter(window, factories, **overrides):
    defaults = {"frame_duration_seconds": 20}
    defaults.update(overrides)
    return PsychoPyActivityMonitoringPresenter(
        window=window,
        image_factory=factories.make_image,
        movie_factory=factories.make_movie,
        sound_factory=factories.make_sound,
        wait=factories.wait,
        **defaults,
    )


def test_activity_monitoring_presenter_presents_trials_in_sequence_order():
    sequence = build_activity_monitoring_sequence()
    window = FakeWindow()
    factories = FakeFactories()
    event_sink = RecordingEventSink()

    result = make_presenter(window, factories).present(
        sequence,
        ManualClock(timestamp=1),
        event_sink,
    )

    assert result.sequence_id == "activity-monitoring"
    assert [trial.trial_id for trial in result.presented_trials] == [
        f"am-{index:02d}" for index in range(1, 17)
    ]
    assert [event.name for event in event_sink.events][0] == "activity-monitoring.started"
    assert [event.name for event in event_sink.events][-1] == "activity-monitoring.ended"


def test_activity_monitoring_presenter_uses_image_and_movie_factories():
    sequence = build_activity_monitoring_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert len(factories.movie_plays) == 8
    assert len(factories.movie_draws) == 8
    assert len(factories.image_draws) == 8
    assert factories.movie_plays[0].endswith("am_a3_s5_b3_gm_d1_f0.avi")
    assert factories.image_draws[0].endswith("ams_a4_s6_b4_ga_d1_f1.jpg")


def test_activity_monitoring_presenter_honors_trial_timing():
    sequence = build_activity_monitoring_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert factories.waits[:4] == [1, 20, 0.25, 1.0]
    assert factories.waits[4:8] == [1, 10, 0.5, 1.0]


def test_activity_monitoring_presenter_draws_movie_frames_through_duration():
    sequence = build_activity_monitoring_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories, trial_limit=1, frame_duration_seconds=5).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert len(factories.movie_draws) == 4
    assert factories.waits == [1, 5, 5, 5, 5, 0.25]


def test_activity_monitoring_presenter_shows_blank_inter_trial_interval_between_trials():
    sequence = build_activity_monitoring_sequence()
    window = FakeWindow()
    factories = FakeFactories()
    event_sink = RecordingEventSink()

    make_presenter(
        window,
        factories,
        trial_limit=2,
        frame_duration_seconds=0.5,
    ).present(
        sequence,
        ManualClock(),
        event_sink,
    )

    assert len(factories.movie_draws) == 40
    assert len(factories.image_draws) == 20
    assert len(factories.sound_plays) == 1
    assert factories.waits[42] == 1.0
    assert window.colors[40] == "black"

    event_names = [event.name for event in event_sink.events]
    first_trial_end = event_names.index("activity-monitoring.trial.ended")
    iti_start = event_names.index("activity-monitoring.inter-trial-interval.started")
    iti_end = event_names.index("activity-monitoring.inter-trial-interval.ended")
    second_trial_start = event_names.index(
        "activity-monitoring.trial.started",
        first_trial_end + 1,
    )
    assert first_trial_end < iti_start < iti_end < second_trial_start


def test_activity_monitoring_presenter_plays_static_soundtrack_only_when_enabled():
    sequence = build_activity_monitoring_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert len(factories.sound_plays) == 8
    assert all(path.endswith("satie.wav") for path in factories.sound_plays)
    assert factories.sound_stops == factories.sound_plays

    muted_factories = FakeFactories()
    make_presenter(window, muted_factories, play_sound=False).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert muted_factories.sound_plays == []
    assert muted_factories.sound_stops == []


def test_activity_monitoring_presenter_can_limit_trials_for_demos():
    sequence = build_activity_monitoring_sequence()
    window = FakeWindow()
    factories = FakeFactories()
    event_sink = RecordingEventSink()

    result = make_presenter(window, factories, trial_limit=2).present(
        sequence,
        ManualClock(),
        event_sink,
    )

    assert [trial.trial_id for trial in result.presented_trials] == ["am-01", "am-02"]
    assert event_sink.events[-1].payload["trial_count"] == 2


def test_importing_activity_monitoring_presenter_does_not_import_psychopy():
    assert "psychopy" not in sys.modules
