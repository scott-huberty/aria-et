import sys
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from aria_et.activity_monitoring import build_activity_monitoring_sequence
from aria_et.psychopy.activity_monitoring import (
    PsychoPyActivityMonitoringPresenter,
    video_duration_seconds,
)
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

    def unload(self):
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
    elapsed: float = 0.0

    def make_image(self, window, image):
        return FakeImage(image, self.image_draws)

    def make_movie(self, window, movie):
        return FakeMovie(movie, self.movie_draws, self.movie_plays)

    def make_sound(self, path):
        return FakeSound(path, self.sound_plays, self.sound_stops)

    def wait(self, seconds):
        self.waits.append(seconds)
        self.elapsed += seconds


def make_presenter(window, factories, **overrides):
    defaults = {
        "frame_duration_seconds": 20,
        "movie_duration_reader": lambda path: 20.0,
    }
    defaults.update(overrides)
    return PsychoPyActivityMonitoringPresenter(
        window=window,
        image_factory=factories.make_image,
        movie_factory=factories.make_movie,
        sound_factory=factories.make_sound,
        wait=factories.wait,
        monotonic=lambda: factories.elapsed,
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
    assert [event.name for event in event_sink.events][
        0
    ] == "activity-monitoring.started"
    assert [event.name for event in event_sink.events][
        -1
    ] == "activity-monitoring.ended"


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
    assert factories.movie_plays[0].endswith("am_a3_s5_b3_gm_d1_f0.mp4")
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


@pytest.mark.parametrize(
    "draw_seconds, flip_seconds, expected_frames, expected_waits",
    [
        (0.125, 0.125, 4, [0.25] * 4),
        (0.75, 0.25, 2, []),
    ],
)
def test_activity_monitoring_duration_includes_drawing_and_flip_time(
    draw_seconds, flip_seconds, expected_frames, expected_waits
):
    factories = FakeFactories()
    draws = []

    def draw():
        draws.append(factories.elapsed)
        factories.elapsed += draw_seconds

    def flip():
        factories.elapsed += flip_seconds

    presenter = make_presenter(
        SimpleNamespace(flip=flip), factories, frame_duration_seconds=0.5
    )
    presenter._draw_for_duration(SimpleNamespace(draw=draw), 2.0)

    assert factories.elapsed == 2.0
    assert len(draws) == expected_frames
    assert factories.waits == expected_waits


def test_activity_monitoring_does_not_draw_again_after_a_decoder_stall():
    factories = FakeFactories()
    draws = []

    def draw():
        draws.append(factories.elapsed)
        factories.elapsed += 3.0

    presenter = make_presenter(FakeWindow(), factories, frame_duration_seconds=0.5)
    presenter._draw_for_duration(SimpleNamespace(draw=draw), 2.0)

    assert draws == [0.0]
    assert factories.waits == []


@pytest.mark.parametrize("failure_stage", [None, "play", "draw"])
def test_activity_monitoring_unloads_movie_even_when_playback_fails(failure_stage):
    factories = FakeFactories()
    unloaded = []

    def play():
        if failure_stage == "play":
            raise RuntimeError("playback failed")

    def draw():
        if failure_stage == "draw":
            raise RuntimeError("playback failed")

    movie = SimpleNamespace(play=play, draw=draw, unload=lambda: unloaded.append(True))
    presenter = PsychoPyActivityMonitoringPresenter(
        window=FakeWindow(),
        movie_factory=lambda window, path: movie,
        wait=factories.wait,
        monotonic=lambda: factories.elapsed,
        frame_duration_seconds=20,
        movie_duration_reader=lambda path: 20.0,
    )
    trial = build_activity_monitoring_sequence().trials[0]

    if failure_stage:
        with pytest.raises(RuntimeError, match="playback failed"):
            presenter._present_movie_trial(trial)
    else:
        presenter._present_movie_trial(trial)

    assert unloaded == [True]


@pytest.mark.parametrize(
    "video_duration, expected_seconds", [(12.5, 12.5), (25.0, 25.0)]
)
def test_activity_monitoring_movie_plays_to_video_endpoint(
    video_duration, expected_seconds
):
    window = FakeWindow()
    factories = FakeFactories()
    presenter = make_presenter(
        window,
        factories,
        frame_duration_seconds=2.5,
        movie_duration_reader=lambda path: video_duration,
    )

    presenter._present_movie_trial(build_activity_monitoring_sequence().trials[0])

    assert factories.elapsed == expected_seconds
    assert len(factories.movie_plays) == 1
    assert len(factories.movie_draws) == expected_seconds / 2.5
    # Clear the last movie frame immediately, before the post-trial wait.
    assert window.flips == len(factories.movie_draws) + 1
    assert window.colors[-1] == "black"


def test_activity_monitoring_movie_deadline_includes_play_startup_time():
    factories = FakeFactories()
    draws = []
    unloaded = []
    movie = SimpleNamespace(
        play=lambda: setattr(factories, "elapsed", factories.elapsed + 0.5),
        draw=lambda: draws.append(factories.elapsed),
        unload=lambda: unloaded.append(True),
    )
    presenter = PsychoPyActivityMonitoringPresenter(
        window=FakeWindow(),
        movie_factory=lambda window, path: movie,
        movie_duration_reader=lambda path: 1.0,
        frame_duration_seconds=0.25,
        wait=factories.wait,
        monotonic=lambda: factories.elapsed,
    )

    presenter._present_movie_trial(build_activity_monitoring_sequence().trials[0])

    assert draws == [0.5, 0.75]
    assert factories.elapsed == 1.0
    assert unloaded == [True]


@pytest.mark.parametrize(
    "opened, frame_count, frame_rate, expected",
    [
        (True, 546, 30000 / 1001, 18.2182),
        (False, 546, 30, None),
        (True, 0, 30, None),
        (True, 546, 0, None),
        (True, float("nan"), 30, None),
        (True, 546, float("inf"), None),
    ],
)
def test_video_duration_metadata_is_validated_and_capture_released(
    monkeypatch, opened, frame_count, frame_rate, expected
):
    released = []
    capture = SimpleNamespace(
        isOpened=lambda: opened,
        get=lambda prop: {1: frame_count, 2: frame_rate}[prop],
        release=lambda: released.append(True),
    )
    monkeypatch.setitem(
        sys.modules,
        "cv2",
        SimpleNamespace(
            VideoCapture=lambda path: capture,
            CAP_PROP_FRAME_COUNT=1,
            CAP_PROP_FPS=2,
        ),
    )

    if expected is None:
        with pytest.raises(ValueError, match="video"):
            video_duration_seconds("clip.mp4")
    else:
        assert video_duration_seconds("clip.mp4") == pytest.approx(expected)

    assert released == [True]


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


def test_activity_monitoring_default_movie_factory_uses_configured_speaker(monkeypatch):
    calls = []

    class FakeVisual:
        @staticmethod
        def MovieStim(*args, **kwargs):
            calls.append((args, kwargs))
            return "movie"

    monkeypatch.setitem(sys.modules, "psychopy", SimpleNamespace(visual=FakeVisual))

    presenter = PsychoPyActivityMonitoringPresenter(
        window=FakeWindow(),
        audio_speaker="EV2480",
    )

    movie = presenter._movie_factory()(FakeWindow(), "movie.mp4")

    assert movie == "movie"
    assert calls[0][1]["filename"] == "movie.mp4"
    assert calls[0][1]["audioDevice"] == "EV2480"
    assert calls[0][1]["noAudio"] is False


def test_activity_monitoring_default_sound_factory_uses_configured_speaker(monkeypatch):
    calls = []

    class FakeSoundModule:
        @staticmethod
        def Sound(*args, **kwargs):
            calls.append((args, kwargs))
            return "sound"

    monkeypatch.setitem(sys.modules, "psychopy", SimpleNamespace(sound=FakeSoundModule))

    presenter = PsychoPyActivityMonitoringPresenter(
        window=FakeWindow(),
        audio_speaker="EV2480",
    )

    sound = presenter._sound_factory()("satie.wav")

    assert sound == "sound"
    assert calls[0][0] == ("satie.wav",)
    assert calls[0][1]["speaker"] == "EV2480"


def test_importing_activity_monitoring_presenter_does_not_import_psychopy():
    assert "psychopy" not in sys.modules
