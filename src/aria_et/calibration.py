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

# Validation after calibration (Titta-style quality check) uses the same target
# positions as the calibration, so accuracy is measured across the calibrated
# area, including the corners where error is usually largest. The positions are
# read from the applied calibration; this is the fallback, matching DeToX's
# 5-point layout (normalized +/-0.8, i.e. 10% in from each edge). Coordinates are
# the Tobii active display area system (0-1, origin top-left).
DEFAULT_VALIDATION_POINTS = (
    (0.5, 0.5),
    (0.1, 0.1),
    (0.9, 0.1),
    (0.1, 0.9),
    (0.9, 0.9),
)
# After the operator presses Space, validation waits for the eyes to settle for
# DeToX's own ``focus_time`` (the same wait its calibration uses before
# collecting), then records gaze for this long.
VALIDATION_COLLECT_SECONDS = 1.0
