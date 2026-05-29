import sys
from dataclasses import dataclass, field

import pytest

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
    defaults = {"frame_duration_seconds": 10}
    defaults.update(overrides)
    return PsychoPyPupillaryLightReflexPresenter(
        window=window,
        movie_factory=factories.make_movie,
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


def test_pupillary_light_reflex_presenter_uses_movie_factory_with_plr_metadata():
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
    assert len(factories.movie_plays) == 2
    assert factories.movie_plays[0][0].endswith("plr78.avi")
    assert factories.movie_plays[0][1] is True
    assert factories.movie_plays[1][0].endswith("plr65.avi")
    assert event_sink.events[1].payload["frame_count"] == 186
    assert event_sink.events[1].payload["flash_frame_count"] == 4


def test_pupillary_light_reflex_presenter_honors_trial_timing():
    sequence = build_pupillary_light_reflex_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories, trial_limit=2).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert factories.waits == [6.2, 6.2]


def test_pupillary_light_reflex_presenter_draws_movie_frames_through_duration():
    sequence = build_pupillary_light_reflex_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories, trial_limit=1, frame_duration_seconds=2).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert len(factories.movie_draws) == 4
    assert factories.waits == pytest.approx([2, 2, 2, 0.2])
    assert len(factories.movie_stops) == 1


def test_pupillary_light_reflex_presenter_can_disable_movie_audio():
    sequence = build_pupillary_light_reflex_sequence()
    window = FakeWindow()
    factories = FakeFactories()

    make_presenter(window, factories, trial_limit=1, play_sound=False).present(
        sequence,
        ManualClock(),
        RecordingEventSink(),
    )

    assert factories.movie_plays[0][1] is False


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
