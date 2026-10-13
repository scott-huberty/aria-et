"""Child-friendly calibration settings.

The calibration itself is run by DeToX (``aria_et.psychopy.calibration``). This
module holds the defaults the CLI and GUI share, without importing PsychoPy.
"""

from __future__ import annotations

# Number of calibration targets: DeToX supports a 5-point (corners + center) and
# a 9-point layout.
CALIBRATION_POINT_CHOICES = (5, 9)
DEFAULT_CALIBRATION_POINTS = 5

# DeToX target animations: "zoom" pulses the size, "trill" wiggles the target.
ANIMATION_CHOICES = ("zoom", "trill")
DEFAULT_ANIMATION = "zoom"

DEFAULT_SHUFFLE_POINTS = True
DEFAULT_SHOW_POSITIONING = True

# How DeToX draws collected gaze against each target on its results screen.
RESULTS_VISUALIZATION_STYLE = "circles"
