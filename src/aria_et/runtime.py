"""Backend-neutral runtime contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


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
