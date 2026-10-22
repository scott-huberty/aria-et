"""Backend-neutral runtime contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

__all__ = [
    "Clock",
    "EventSink",
    "ManualClock",
    "RecordingEventSink",
    "RuntimeEvent",
]


class Clock(Protocol):
    """The time source of a task presenter."""

    def now(self) -> float:
        """Return the current time.

        Returns
        -------
        float
            The time in seconds. Only differences between times are meaningful.
        """


@dataclass(frozen=True)
class RuntimeEvent:
    """One task event, for example the start or the end of a trial.

    Attributes
    ----------
    name : str
        The event name, for example ``"activity-monitoring.trial.started"``.
    timestamp : float
        The time of the event, from the ``Clock`` of the task.
    payload : dict of str to object
        Event data, for example the trial id. The values must be
        JSON-serialisable.
    """

    name: str
    timestamp: float
    payload: dict[str, object] = field(default_factory=dict)


class EventSink(Protocol):
    """Receives the events of a task."""

    def emit(self, event: RuntimeEvent) -> None:
        """Record one event.

        Parameters
        ----------
        event : RuntimeEvent
            The event to record.
        """


@dataclass
class ManualClock:
    """A ``Clock`` that changes only when ``advance`` is called. For tests.

    Attributes
    ----------
    timestamp : float
        The current time in seconds.
    """

    timestamp: float = 0.0

    def now(self) -> float:
        """Return the current time.

        Returns
        -------
        float
            The time in seconds.
        """
        return self.timestamp

    def advance(self, seconds: float) -> None:
        """Move the time forward.

        Parameters
        ----------
        seconds : float
            The number of seconds to add. It must not be negative.
        """
        if seconds < 0:
            raise ValueError(f"seconds must be non-negative: {seconds}")
        self.timestamp += seconds


@dataclass
class RecordingEventSink:
    """An ``EventSink`` that keeps the events in a list.

    Attributes
    ----------
    events : list of RuntimeEvent
        The events, in the order that they were emitted.
    """

    events: list[RuntimeEvent] = field(default_factory=list)

    def emit(self, event: RuntimeEvent) -> None:
        """Add one event to ``events``.

        Parameters
        ----------
        event : RuntimeEvent
            The event to keep.
        """
        self.events.append(event)
