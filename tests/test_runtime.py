import sys

import pytest

from aria_et.calibration import build_pikachu_calibration_sequence
from aria_et.runtime import (
    FakeCalibrationPresenter,
    ManualClock,
    RecordingEventSink,
)


def test_fake_calibration_presenter_presents_all_points_in_order():
    sequence = build_pikachu_calibration_sequence()
    clock = ManualClock()
    event_sink = RecordingEventSink()

    result = FakeCalibrationPresenter(point_duration_seconds=0.25).present(
        sequence,
        clock,
        event_sink,
    )

    assert result.sequence_id == "gap-overlap-reward-5-point"
    assert [point.label for point in result.presented_points] == [
        "center",
        "top-left",
        "top-right",
        "bottom-right",
        "bottom-left",
    ]


def test_fake_calibration_presenter_preserves_target_positions():
    sequence = build_pikachu_calibration_sequence()
    clock = ManualClock()
    event_sink = RecordingEventSink()

    result = FakeCalibrationPresenter().present(sequence, clock, event_sink)

    assert [(point.position.x, point.position.y) for point in result.presented_points] == [
        (0.5, 0.5),
        (0.1, 0.1),
        (0.9, 0.1),
        (0.9, 0.9),
        (0.1, 0.9),
    ]


def test_fake_calibration_presenter_emits_lifecycle_events():
    sequence = build_pikachu_calibration_sequence()
    clock = ManualClock(timestamp=10)
    event_sink = RecordingEventSink()

    result = FakeCalibrationPresenter(point_duration_seconds=0.5).present(
        sequence,
        clock,
        event_sink,
    )

    assert [event.name for event in event_sink.events] == [
        "calibration.started",
        "calibration.point.started",
        "calibration.point.ended",
        "calibration.point.started",
        "calibration.point.ended",
        "calibration.point.started",
        "calibration.point.ended",
        "calibration.point.started",
        "calibration.point.ended",
        "calibration.point.started",
        "calibration.point.ended",
        "calibration.ended",
    ]
    assert result.started_at == 10
    assert result.ended_at == 12.5
    assert event_sink.events[0].payload == {"sequence_id": "gap-overlap-reward-5-point"}
    assert event_sink.events[-1].payload == {
        "sequence_id": "gap-overlap-reward-5-point",
        "point_count": 5,
    }


def test_point_started_events_include_target_coordinates():
    sequence = build_pikachu_calibration_sequence()
    clock = ManualClock()
    event_sink = RecordingEventSink()

    FakeCalibrationPresenter().present(sequence, clock, event_sink)

    point_started_events = [
        event for event in event_sink.events if event.name == "calibration.point.started"
    ]
    assert point_started_events[0].payload == {
        "label": "center",
        "x": 0.5,
        "y": 0.5,
    }


def test_manual_clock_rejects_negative_time():
    clock = ManualClock()

    with pytest.raises(ValueError, match="seconds must be non-negative"):
        clock.advance(-1)


def test_runtime_contract_does_not_import_backend_modules():
    assert "psychopy" not in sys.modules
    assert "titta" not in sys.modules
