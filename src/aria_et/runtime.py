"""Backend-neutral runtime contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from aria_et.calibration import CalibrationPoint, CalibrationSequence, NormalizedPoint


class Clock(Protocol):
    def now(self) -> float:
        """Return the current runtime timestamp in seconds."""


@dataclass(frozen=True)
class RuntimeEvent:
    name: str
    timestamp: float
    payload: dict[str, object] = field(default_factory=dict)


class EventSink(Protocol):
    def emit(self, event: RuntimeEvent) -> None:
        """Record a runtime event."""


@dataclass(frozen=True)
class PresentedCalibrationPoint:
    label: str
    position: NormalizedPoint
    started_at: float
    ended_at: float


@dataclass(frozen=True)
class CalibrationRunResult:
    sequence_id: str
    presented_points: tuple[PresentedCalibrationPoint, ...]
    started_at: float
    ended_at: float


class CalibrationPresenter(Protocol):
    def present(
        self,
        sequence: CalibrationSequence,
        clock: Clock,
        event_sink: EventSink,
    ) -> CalibrationRunResult:
        """Present a calibration sequence and return a backend-neutral result."""


@dataclass
class ManualClock:
    timestamp: float = 0.0

    def now(self) -> float:
        return self.timestamp

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError(f"seconds must be non-negative: {seconds}")
        self.timestamp += seconds


@dataclass
class RecordingEventSink:
    events: list[RuntimeEvent] = field(default_factory=list)

    def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)


@dataclass(frozen=True)
class FakeCalibrationPresenter:
    point_duration_seconds: float = 1.0

    def present(
        self,
        sequence: CalibrationSequence,
        clock: Clock,
        event_sink: EventSink,
    ) -> CalibrationRunResult:
        started_at = clock.now()
        event_sink.emit(
            RuntimeEvent(
                "calibration.started",
                started_at,
                {"sequence_id": sequence.sequence_id},
            )
        )

        presented_points = tuple(
            self._present_point(point, started_at, index, event_sink)
            for index, point in enumerate(sequence.points)
        )

        ended_at = started_at + (len(sequence.points) * self.point_duration_seconds)
        event_sink.emit(
            RuntimeEvent(
                "calibration.ended",
                ended_at,
                {
                    "sequence_id": sequence.sequence_id,
                    "point_count": len(presented_points),
                },
            )
        )

        return CalibrationRunResult(
            sequence_id=sequence.sequence_id,
            presented_points=presented_points,
            started_at=started_at,
            ended_at=ended_at,
        )

    def _present_point(
        self,
        point: CalibrationPoint,
        sequence_started_at: float,
        index: int,
        event_sink: EventSink,
    ) -> PresentedCalibrationPoint:
        started_at = sequence_started_at + (index * self.point_duration_seconds)
        event_sink.emit(
            RuntimeEvent(
                "calibration.point.started",
                started_at,
                {
                    "label": point.target.label,
                    "x": point.target.position.x,
                    "y": point.target.position.y,
                },
            )
        )

        ended_at = started_at + self.point_duration_seconds
        event_sink.emit(
            RuntimeEvent(
                "calibration.point.ended",
                ended_at,
                {"label": point.target.label},
            )
        )

        return PresentedCalibrationPoint(
            label=point.target.label,
            position=point.target.position,
            started_at=started_at,
            ended_at=ended_at,
        )
