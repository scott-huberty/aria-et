"""Structural types for the objects aria-et receives from other libraries.

The Tobii Pro SDK, PsychoPy and DeToX have no type stubs. These protocols
state the members that aria-et uses, so the type checker can check the calls
and so the tests can pass small fakes instead of the real objects.

A method that returns ``object`` means that aria-et ignores its return value.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from types import ModuleType
from typing import Any, Protocol

StatusSink = Callable[[str], None]
"""Receives one line of operator-facing status text."""

ImportModule = Callable[[str], ModuleType]
"""``importlib.import_module``, or a replacement in the tests."""

Wait = Callable[[float], object]
"""Blocks for a number of seconds, for example ``psychopy.core.wait``."""

GazeSample = Mapping[str, Any]
"""One Tobii SDK stream sample (``as_dictionary=True``).

The value type depends on the key, for example a validity flag, a 2D point on
the display area, or a 3D point in user coordinates.
"""

GazeCallback = Callable[[GazeSample], object]

PsychoPyModule = Any
"""A PsychoPy module, for example ``psychopy.visual`` or ``psychopy.event``.

PsychoPy has no type stubs, and ty treats its imports as ``Any`` (see
``pyproject.toml``). The tests pass small fakes in its place.
"""

DetoxController = Any
"""A ``DeToX.ETracker``. DeToX has no type stubs."""


# -- Tobii Pro SDK ------------------------------------------------------------


class TrackerIdentity(Protocol):
    """The fields that identify a Tobii eye tracker."""

    @property
    def address(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def serial_number(self) -> str: ...

    @property
    def firmware_version(self) -> str: ...


class GazeSource(Protocol):
    """A Tobii eye tracker that streams samples to a callback."""

    def subscribe_to(
        self,
        stream: str,
        callback: GazeCallback,
        /,
        as_dictionary: bool = False,
    ) -> object: ...

    def unsubscribe_from(self, stream: str, callback: GazeCallback, /) -> object: ...


class CalibrationSource(Protocol):
    """A Tobii eye tracker that can return its active calibration."""

    def retrieve_calibration_data(self) -> bytes | None: ...


class ScreenBasedCalibration(Protocol):
    """``tobii_research.ScreenBasedCalibration``."""

    def compute_and_apply(self) -> object: ...


class DisplayArea(Protocol):
    """The tracker's display area corners, in user coordinates (mm)."""

    @property
    def top_left(self) -> Sequence[float]: ...

    @property
    def top_right(self) -> Sequence[float]: ...

    @property
    def bottom_left(self) -> Sequence[float]: ...


class GazeTracker(TrackerIdentity, GazeSource, Protocol):
    """A tracker that the gaze recorder can identify and record from."""


class CalibratedTracker(TrackerIdentity, CalibrationSource, Protocol):
    """A tracker whose active calibration aria-et saves."""


class TobiiEyeTracker(TrackerIdentity, GazeSource, CalibrationSource, Protocol):
    """``tobii_research.EyeTracker``: the members that aria-et uses."""

    def get_display_area(self) -> DisplayArea: ...


# -- PsychoPy -----------------------------------------------------------------


class DrawingWindow(Protocol):
    """``psychopy.visual.Window``: a window to draw into and flip."""

    @property
    def size(self) -> Sequence[float]: ...

    def flip(self) -> object: ...


class WindowLike(DrawingWindow, Protocol):
    """``psychopy.visual.Window``: the members that the presenters use."""

    color: str | tuple[float, float, float]


class ClosableWindow(WindowLike, Protocol):
    """A window that the caller opened and must close."""

    def close(self) -> object: ...


class DrawableLike(Protocol):
    """A PsychoPy stimulus, for example ``psychopy.visual.ImageStim``."""

    def draw(self) -> object: ...


class MovieLike(DrawableLike, Protocol):
    """``psychopy.visual.MovieStim``."""

    def play(self) -> object: ...

    def unload(self) -> object: ...


class SoundLike(Protocol):
    """``psychopy.sound.Sound``."""

    def play(self) -> object: ...

    def stop(self) -> object: ...


class FadingSound(SoundLike, Protocol):
    """A ``psychopy.sound.Sound`` whose volume changes while it plays."""

    def setVolume(self, volume: float) -> object: ...


class ClockLike(Protocol):
    """``psychopy.core.Clock``."""

    def getTime(self) -> float: ...
