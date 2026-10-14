"""Live child position from the Tobii user position guide, for the GUI panel.

The tracker reports where each eye is inside its track box (x, y, z, each 0-1).
The GUI subscribes to this stream in its own process, alongside whatever
subprocess is calibrating or recording: Tobii Pro trackers accept several
client connections. The Tobii callback runs on the SDK's thread and only stores
the latest sample; the GUI reads it on a timer. Nothing here imports Qt.
"""

from __future__ import annotations

import contextlib
import importlib
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from types import ModuleType

from aria_et.calibration import (
    POSITION_CENTRE_RANGE,
    POSITION_IDEAL_Z,
    POSITION_STALE_SECONDS,
    POSITION_Z_TOLERANCE,
)

ImportModule = Callable[[str], ModuleType]
EYES = ("left", "right")
Position = tuple[float, float, float]

# classify() outcomes, and the status line the panel shows for each.
STATUS_TEXT = {
    "good": "Position good",
    "too_close": "Too close",
    "too_far": "Too far",
    "off_centre": "Move to centre",
    "no_eyes": "Eyes not found",
    "stale": "No position data",
    "no_tracker": "No tracker",
}


@dataclass(frozen=True)
class PositionSample:
    left: Position | None
    right: Position | None
    received_at: float

    def eyes(self) -> dict[str, Position]:
        """The valid eyes, by name."""
        return {
            eye: position
            for eye, position in (("left", self.left), ("right", self.right))
            if position is not None
        }


def sample_from_guide(data: dict, received_at: float) -> PositionSample:
    """Build a sample from a Tobii user position guide dictionary."""

    def position(eye: str) -> Position | None:
        if not data.get(f"{eye}_user_position_validity"):
            return None
        values = data.get(f"{eye}_user_position")
        if values is None or len(values) != 3:
            return None
        x, y, z = (float(value) for value in values)
        if not all(math.isfinite(value) for value in (x, y, z)):
            return None
        return (x, y, z)

    return PositionSample(position("left"), position("right"), received_at)


def panel_position(x: float, y: float) -> tuple[float, float]:
    """Track-box x, y to panel x, y (0-1, origin top-left), as DeToX draws it.

    The tracker reports x from its own point of view, so it is mirrored to
    match what the operator sees (DeToX Coords.get_psychopy_pos_from_user_position).
    """
    return (1.0 - x, y)


def mean_distance(sample: PositionSample | None) -> float | None:
    """Track-box z averaged over the valid eyes, or None."""
    if sample is None:
        return None
    depths = [position[2] for position in sample.eyes().values()]
    return sum(depths) / len(depths) if depths else None


def classify(sample: PositionSample | None, now: float) -> str:
    """One of the STATUS_TEXT keys (except "no_tracker") for a sample."""
    if sample is None or now - sample.received_at > POSITION_STALE_SECONDS:
        return "stale"
    eyes = sample.eyes()
    if not eyes:
        return "no_eyes"
    z = mean_distance(sample)
    if z < POSITION_IDEAL_Z - POSITION_Z_TOLERANCE:
        return "too_close"
    if z > POSITION_IDEAL_Z + POSITION_Z_TOLERANCE:
        return "too_far"
    low, high = POSITION_CENTRE_RANGE
    for x, y, _z in eyes.values():
        if not (low <= x <= high and low <= y <= high):
            return "off_centre"
    return "good"


class PositionMonitor:
    """Subscribes to the user position guide and keeps the latest sample.

    ``start`` opens the tracker on a background thread (discovery can take a
    few seconds) so the GUI never blocks. Failures never raise: they set
    ``status`` to "unavailable" with a ``message``.
    """

    def __init__(
        self,
        *,
        import_module: ImportModule = importlib.import_module,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._import_module = import_module
        self._clock = clock
        self._lock = threading.Lock()
        self._latest: PositionSample | None = None
        self._tracker = None
        self._stream = None
        self._generation = 0
        self.status = "stopped"  # stopped | connecting | running | unavailable
        self.message = ""

    def start(
        self,
        *,
        address: str | None = None,
        serial_number: str | None = None,
        background: bool = True,
    ) -> None:
        """Connect and subscribe; restarts if already running."""
        self.stop()
        with self._lock:
            self._generation += 1
            generation = self._generation
            self.status = "connecting"
            self.message = ""
        if background:
            threading.Thread(
                target=self._connect,
                args=(generation, address, serial_number),
                name="aria-et-position-monitor",
                daemon=True,
            ).start()
        else:
            self._connect(generation, address, serial_number)

    def stop(self) -> None:
        """Unsubscribe; safe to call at any time, including twice."""
        with self._lock:
            self._generation += 1
            tracker, stream = self._tracker, self._stream
            self._tracker = self._stream = None
            self._latest = None
            self.status = "stopped"
        if tracker is not None:
            self._unsubscribe_quietly(tracker, stream)

    def latest(self) -> PositionSample | None:
        with self._lock:
            return self._latest

    def now(self) -> float:
        return self._clock()

    def _connect(
        self, generation: int, address: str | None, serial_number: str | None
    ) -> None:
        from aria_et.eyetracker import load_tobii_research, open_eyetracker

        try:
            tobii_research = load_tobii_research(import_module=self._import_module)
            tracker = open_eyetracker(
                address=address,
                serial_number=serial_number,
                import_module=self._import_module,
                error_sink=lambda _message: None,
            )
            stream = tobii_research.EYETRACKER_USER_POSITION_GUIDE
            tracker.subscribe_to(stream, self._on_sample, as_dictionary=True)
        except Exception as error:  # noqa: BLE001 - optional panel; never crash the GUI
            with self._lock:
                if generation == self._generation:
                    self.status = "unavailable"
                    self.message = str(error)
            return
        with self._lock:
            if generation == self._generation:
                self._tracker, self._stream = tracker, stream
                self.status = "running"
                return
        # stop() or a newer start() happened while connecting.
        self._unsubscribe_quietly(tracker, stream)

    def _unsubscribe_quietly(self, tracker, stream) -> None:
        # Shutting down: a tracker that has gone away can't be unsubscribed from,
        # and there is nothing to recover.
        with contextlib.suppress(Exception):
            tracker.unsubscribe_from(stream, self._on_sample)

    def _on_sample(self, data: dict) -> None:
        sample = sample_from_guide(data, self._clock())
        with self._lock:
            self._latest = sample
