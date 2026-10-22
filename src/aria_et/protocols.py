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

__all__ = [
    "CalibratedTracker",
    "CalibrationSource",
    "ClockLike",
    "ClosableWindow",
    "DetoxController",
    "DisplayArea",
    "DrawableLike",
    "DrawingWindow",
    "FadingSound",
    "GazeCallback",
    "GazeSample",
    "GazeSource",
    "GazeTracker",
    "ImportModule",
    "MovieLike",
    "PsychoPyModule",
    "ScreenBasedCalibration",
    "SoundLike",
    "StatusSink",
    "TobiiEyeTracker",
    "TrackerIdentity",
    "Wait",
    "WindowLike",
]

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
    def address(self) -> str:
        """The network address, for example ``"tobii-prp://169.254.10.180"``."""
        ...

    @property
    def model(self) -> str:
        """The model name, for example ``"Tobii Pro Spectrum"``."""
        ...

    @property
    def serial_number(self) -> str:
        """The serial number."""
        ...

    @property
    def firmware_version(self) -> str:
        """The firmware version."""
        ...


class GazeSource(Protocol):
    """A Tobii eye tracker that streams samples to a callback."""

    def subscribe_to(
        self,
        stream: str,
        callback: GazeCallback,
        /,
        as_dictionary: bool = False,
    ) -> object:
        """Start to send the samples of one stream to a callback.

        Parameters
        ----------
        stream : str
            The stream, for example ``tobii_research.EYETRACKER_GAZE_DATA``.
        callback : GazeCallback
            Receives each sample, on a thread of the Tobii SDK.
        as_dictionary : bool
            True sends each sample as a dictionary. aria-et always uses True.
        """
        ...

    def unsubscribe_from(self, stream: str, callback: GazeCallback, /) -> object:
        """Stop to send the samples of one stream to a callback.

        Parameters
        ----------
        stream : str
            The stream that ``subscribe_to`` started.
        callback : GazeCallback
            The callback that ``subscribe_to`` received.
        """
        ...


class CalibrationSource(Protocol):
    """A Tobii eye tracker that can return its active calibration."""

    def retrieve_calibration_data(self) -> bytes | None:
        """Read the active calibration from the tracker.

        Returns
        -------
        bytes or None
            The calibration data, or None if the tracker has no calibration.
        """
        ...


class ScreenBasedCalibration(Protocol):
    """``tobii_research.ScreenBasedCalibration``."""

    def compute_and_apply(self) -> object:
        """Compute a calibration from the collected points and apply it.

        Returns
        -------
        object
            The calibration result of the Tobii SDK.
        """
        ...


class DisplayArea(Protocol):
    """The tracker's display area corners, in user coordinates (mm)."""

    @property
    def top_left(self) -> Sequence[float]:
        """The top-left corner (x, y, z)."""
        ...

    @property
    def top_right(self) -> Sequence[float]:
        """The top-right corner (x, y, z)."""
        ...

    @property
    def bottom_left(self) -> Sequence[float]:
        """The bottom-left corner (x, y, z)."""
        ...


class GazeTracker(TrackerIdentity, GazeSource, Protocol):
    """A tracker that the gaze recorder can identify and record from."""


class CalibratedTracker(TrackerIdentity, CalibrationSource, Protocol):
    """A tracker whose active calibration aria-et saves."""


class TobiiEyeTracker(TrackerIdentity, GazeSource, CalibrationSource, Protocol):
    """``tobii_research.EyeTracker``: the members that aria-et uses."""

    def get_display_area(self) -> DisplayArea:
        """Read the display area that the tracker uses.

        Returns
        -------
        DisplayArea
            The corners of the display area.
        """
        ...


# -- PsychoPy -----------------------------------------------------------------


class DrawingWindow(Protocol):
    """``psychopy.visual.Window``: a window to draw into and flip."""

    @property
    def size(self) -> Sequence[float]:
        """The width and height of the window in pixels."""
        ...

    def flip(self) -> object:
        """Show the frame that was drawn, at the next screen refresh.

        Returns
        -------
        object
            Not used by aria-et.
        """
        ...


class WindowLike(DrawingWindow, Protocol):
    """``psychopy.visual.Window``: the members that the presenters use.

    Attributes
    ----------
    color : str or tuple of (float, float, float)
        The background colour that the next ``flip`` shows.
    """

    color: str | tuple[float, float, float]


class ClosableWindow(WindowLike, Protocol):
    """A window that the caller opened and must close."""

    def close(self) -> object:
        """Close the window.

        Returns
        -------
        object
            Not used by aria-et.
        """
        ...


class DrawableLike(Protocol):
    """A PsychoPy stimulus, for example ``psychopy.visual.ImageStim``."""

    def draw(self) -> object:
        """Draw the stimulus into the next frame.

        Returns
        -------
        object
            Not used by aria-et.
        """
        ...


class MovieLike(DrawableLike, Protocol):
    """``psychopy.visual.MovieStim``."""

    def play(self) -> object:
        """Start the movie.

        Returns
        -------
        object
            Not used by aria-et.
        """
        ...

    def unload(self) -> object:
        """Stop the movie and release its decoder and texture.

        Returns
        -------
        object
            Not used by aria-et.
        """
        ...


class SoundLike(Protocol):
    """``psychopy.sound.Sound``."""

    def play(self) -> object:
        """Start the sound.

        Returns
        -------
        object
            Not used by aria-et.
        """
        ...

    def stop(self) -> object:
        """Stop the sound.

        Returns
        -------
        object
            Not used by aria-et.
        """
        ...


class FadingSound(SoundLike, Protocol):
    """A ``psychopy.sound.Sound`` whose volume changes while it plays."""

    def setVolume(self, volume: float) -> object:
        """Set the volume.

        Parameters
        ----------
        volume : float
            The volume, from 0 (silent) to 1 (full).

        Returns
        -------
        object
            Not used by aria-et.
        """
        ...


class ClockLike(Protocol):
    """``psychopy.core.Clock``."""

    def getTime(self) -> float:
        """Return the time since the clock started.

        Returns
        -------
        float
            The time in seconds.
        """
        ...
