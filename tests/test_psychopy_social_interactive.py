import sys
from dataclasses import dataclass, field

from aria_et.psychopy.social_interactive import (
    PsychoPySocialInteractivePresenter,
    run_social_interactive_session,
)
from aria_et.runtime import ManualClock, RecordingEventSink
from aria_et.social_interactive import build_social_interactive_sequence


@dataclass
class FakeWindow:
    size: tuple[float, float] = (1000, 800)
    flips: int = 0

    def flip(self):
        self.flips += 1


@dataclass
class FakeMovie:
    path: str
    play_sound: bool
    draws: list[str]
    plays: list[tuple[str, bool]]
    stops: list[str]

    def play(self):
        self.plays.append((self.path, self.play_sound))

    def draw(self):
        self.draws.append(self.path)

    def stop(self):
        self.stops.append(self.path)


@dataclass
class FakeFactories:
    movie_draws: list[str] = field(default_factory=list)
    movie_plays: list[tuple[str, bool]] = field(default_factory=list)
    movie_stops: list[str] = field(default_factory=list)
    waits: list[float] = field(default_factory=list)

    def make_movie(self, window, movie, play_sound):
        return FakeMovie(
            movie,
            play_sound,
            self.movie_draws,
            self.movie_plays,
            self.movie_stops,
        )

    def wait(self, seconds):
        self.waits.append(seconds)


def make_presenter(window, factories, **overrides):
    defaults = {"frame_duration_seconds": 20}
    defaults.update(overrides)
    return PsychoPySocialInteractivePresenter(
        window=window,
        movie_factory=factories.make_movie,
        wait=factories.wait,
        **defaults,
    )


def test_social_interactive_presenter_presents_trials_in_sequence_order():
    sequence = build_social_interactive_sequence()
    window = FakeWindow()
    factories = FakeFactories()
    event_sink = RecordingEventSink()

    result = make_presenter(window, factories).present(
        sequence,
        ManualClock(timestamp=1),
        event_sink,
    )

    assert result.sequence_id == "social-interactive"
    assert [trial.trial_id for trial in result.presented_trials] == [
        f"si-{index:02d}" for index in range(1, 23)
    ]
    assert [event.name for event in event_sink.events][0] == "social-interactive.started"
    assert [event.name for event in event_sink.events][-1] == "social-interactive.ended"


def test_social_interactive_presenter_uses_movie_factory_with_play_condition_metadata():
    sequence = build_social_interactive_sequence()
    window = FakeWindow()
    factories = FakeFactories()
    event_sink = RecordingEventSink()

    result = make_presenter(window, factories, trial_limit=2).present(
        sequence,
        ManualClock(),
        event_sink,
    )

    assert [trial.play_condition for trial in result.presented_trials] == [
        "parallel-play",
        "parallel-play",
    ]
    assert len(factories.movie_plays) == 2
    assert factories.movie_plays[0][0].endswith("sibs1_non_15s.mp4")
    assert factories.movie_plays[0][1] is True
    assert factories.movie_plays[1][0].endswith("sibs5_non_15s.mp4")
    assert event_sink.events[1].payload["block_id"] == "SI-B1"
    assert event_sink.events[1].payload["play_condition"] == "parallel-play"


def test_social_interactive_presenter_honors_trial_timing():
    sequence = build_social_interactive_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories, trial_limit=2).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert factories.waits[:3] == [1, 15, 0.25]
    assert factories.waits[3:6] == [1, 15, 0.25]


def test_social_interactive_presenter_draws_movie_frames_through_duration():
    sequence = build_social_interactive_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories, trial_limit=1, frame_duration_seconds=5).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert len(factories.movie_draws) == 3
    assert factories.waits == [1, 5, 5, 5, 0.25]
    assert len(factories.movie_stops) == 1


def test_social_interactive_presenter_can_disable_movie_audio():
    sequence = build_social_interactive_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories, trial_limit=1, play_sound=False).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert factories.movie_plays[0][1] is False


def test_social_interactive_presenter_can_limit_trials_for_demos():
    sequence = build_social_interactive_sequence()
    window = FakeWindow()
    factories = FakeFactories()
    event_sink = RecordingEventSink()

    result = make_presenter(window, factories, trial_limit=2).present(
        sequence,
        ManualClock(),
        event_sink,
    )

    assert [trial.trial_id for trial in result.presented_trials] == ["si-01", "si-02"]
    assert event_sink.events[-1].payload["trial_count"] == 2


def test_run_social_interactive_session_uses_recording_session(monkeypatch):
    calls = []

    def fake_run_recording_session(**kwargs):
        calls.append(kwargs)
        return 0

    monkeypatch.setattr(
        "aria_et.session.run_recording_session",
        fake_run_recording_session,
    )

    exit_code = run_social_interactive_session(
        tracker="none",
        tracker_address="tobii-prp://169.254.10.180",
        output_dir="runs/test-si",
        subject="01",
        session="baseline",
        run="02",
        fullscreen=True,
        screen=2,
        window_size=(1024, 768),
        screen_distance_meters=0.6,
        screen_resolution_pixels=(1280, 720),
        screen_size_meters=(0.4, 0.2),
        monitor_name="EIZO_EV2480",
        audio_speaker="EV2480",
    )

    assert exit_code == 0
    assert calls[0]["task_id"] == "social-interactive"
    assert calls[0]["tracker"] == "none"
    assert calls[0]["tracker_address"] == "tobii-prp://169.254.10.180"
    assert calls[0]["output_dir"] == "runs/test-si"
    assert calls[0]["bids"].subject == "01"
    assert calls[0]["bids"].session == "baseline"
    assert calls[0]["bids"].run == "02"
    assert calls[0]["stimulus_display"].psychopy_screen == 2
    assert calls[0]["stimulus_display"].fullscreen is True
    assert calls[0]["stimulus_display"].window_size_pixels == (1280, 720)
    assert callable(calls[0]["present"])


def test_importing_social_interactive_presenter_does_not_import_psychopy():
    assert "psychopy" not in sys.modules
