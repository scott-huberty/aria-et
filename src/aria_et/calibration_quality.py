"""Calibration quality from validation gaze: accuracy, precision, data loss.

After a calibration, the child looks at validation targets while live gaze is
recorded. For each target and eye this computes:

- accuracy: median angle (degrees) between the gaze vector and the vector from
  the eye to the target,
- precision: RMS of the angles between consecutive gaze vectors (RMS-S2S),
- data loss: fraction of samples without a valid gaze vector.

The method follows Titta's ``_compute_data_quality``
(https://github.com/marcus-nystrom/Titta, ``titta/Tobii.py``), which is
distributed under the MIT License, Copyright (c) 2017-2025 Marcus Nyström.
One deliberate difference: Titta's ``helpers.rms`` takes ``np.diff`` of the
sample-to-sample angles before the RMS; here precision is the standard RMS-S2S,
the RMS of the sample-to-sample angles themselves.

Gaze samples are Tobii Pro SDK gaze dictionaries (``as_dictionary=True``), in
user coordinates (UCS, millimetres). Targets are given in the active display
area coordinate system (ADCS: 0-1, origin top-left).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

EYES = ("left", "right")

Vector = Sequence[float]


@dataclass(frozen=True)
class EyeQuality:
    accuracy_deg: float
    precision_rms_deg: float
    data_loss: float
    n_samples: int

    def as_dict(self) -> dict[str, float | int | None]:
        return {
            "accuracy_deg": _finite_or_none(self.accuracy_deg),
            "precision_rms_deg": _finite_or_none(self.precision_rms_deg),
            "data_loss": _finite_or_none(self.data_loss),
            "n_samples": self.n_samples,
        }


def adcs_to_ucs(point: Vector, display_area: object) -> np.ndarray:
    """Position of an ADCS point in user coordinates, from the display area.

    ``display_area`` is the tracker's ``DisplayArea`` (``top_left``,
    ``top_right``, ``bottom_left`` corners in UCS mm), so the target position
    uses the tracker's own geometry rather than a configured viewing distance.
    """
    top_left = np.asarray(display_area.top_left, dtype=float)
    top_right = np.asarray(display_area.top_right, dtype=float)
    bottom_left = np.asarray(display_area.bottom_left, dtype=float)
    x, y = float(point[0]), float(point[1])
    return top_left + x * (top_right - top_left) + y * (bottom_left - top_left)


def point_quality(
    samples: Sequence[Mapping[str, object]], target_ucs: Vector, eye: str
) -> EyeQuality:
    """Accuracy, precision and data loss for one eye at one validation target."""
    target = np.asarray(target_ucs, dtype=float)
    deviations = []
    sample_to_sample = []
    previous_gaze = None
    invalid = 0
    for sample in samples:
        origin, gaze = _gaze_vectors(sample, eye)
        if origin is None or gaze is None:
            invalid += 1
            previous_gaze = None
            continue
        gaze_vector = gaze - origin
        deviations.append(_angle_between(gaze_vector, target - origin))
        if previous_gaze is not None:
            sample_to_sample.append(_angle_between(gaze_vector, previous_gaze))
        previous_gaze = gaze_vector

    n_samples = len(samples)
    return EyeQuality(
        accuracy_deg=math.degrees(float(np.median(deviations)))
        if deviations
        else math.nan,
        precision_rms_deg=math.degrees(
            float(np.sqrt(np.mean(np.square(sample_to_sample))))
        )
        if sample_to_sample
        else math.nan,
        data_loss=invalid / n_samples if n_samples else math.nan,
        n_samples=n_samples,
    )


def summarize(points: Iterable[Mapping[str, EyeQuality]]) -> dict[str, dict]:
    """Per-eye mean accuracy, precision and data loss, plus the worst accuracy.

    ``points`` holds, for each validation target, a mapping from eye name to
    its :class:`EyeQuality`. Targets with no valid data are ignored by the
    means (NaN-safe), so one missed target doesn't blank the summary.
    """
    points = list(points)
    summary = {}
    for eye in EYES:
        qualities = [point[eye] for point in points if eye in point]
        accuracy = [q.accuracy_deg for q in qualities]
        summary[eye] = {
            "accuracy_deg": _nan_mean(accuracy),
            "max_accuracy_deg": _nan_max(accuracy),
            "precision_rms_deg": _nan_mean([q.precision_rms_deg for q in qualities]),
            "data_loss": _nan_mean([q.data_loss for q in qualities]),
        }
    return summary


# The quality table shown on the GUI Calibration page and on the stimulus
# screen after validation: (label, summary key, scale, decimals). Both use
# format_quality so the two always show the same numbers.
QUALITY_COLUMNS = (
    ("Accuracy (deg)", "accuracy_deg", 1, 2),
    ("Precision (deg)", "precision_rms_deg", 1, 2),
    ("Data loss (%)", "data_loss", 100, 0),
)


def format_quality(summary: Mapping[str, Mapping] | None, key: str) -> tuple[str, str]:
    """(left, right) display strings for one quality column; "n/a" if missing."""
    _label, _key, scale, decimals = next(
        column for column in QUALITY_COLUMNS if column[1] == key
    )
    values = [((summary or {}).get(eye) or {}).get(key) for eye in EYES]
    return tuple(
        "n/a" if value is None else f"{value * scale:.{decimals}f}" for value in values
    )


def gaze_on_display(samples: Sequence[Mapping[str, object]], eye: str) -> list:
    """Valid on-screen gaze positions (ADCS, 0-1) of one eye, for plotting."""
    positions = []
    for sample in samples:
        if not sample.get(f"{eye}_gaze_point_validity"):
            continue
        point = sample.get(f"{eye}_gaze_point_on_display_area")
        if point is None or len(point) != 2:
            continue
        x, y = float(point[0]), float(point[1])
        if math.isfinite(x) and math.isfinite(y):
            positions.append((x, y))
    return positions


def _gaze_vectors(
    sample: Mapping[str, object], eye: str
) -> tuple[np.ndarray | None, np.ndarray | None]:
    if not sample.get(f"{eye}_gaze_point_validity") or not sample.get(
        f"{eye}_gaze_origin_validity"
    ):
        return None, None
    origin = _as_vector(sample.get(f"{eye}_gaze_origin_in_user_coordinate_system"))
    gaze = _as_vector(sample.get(f"{eye}_gaze_point_in_user_coordinate_system"))
    return origin, gaze


def _as_vector(value: object) -> np.ndarray | None:
    if value is None:
        return None
    vector = np.asarray(value, dtype=float)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        return None
    return vector


def _angle_between(first: np.ndarray, second: np.ndarray) -> float:
    """Angle in radians, robust to rounding at 0 and pi."""
    first_unit = first / np.linalg.norm(first)
    second_unit = second / np.linalg.norm(second)
    return float(np.arccos(np.clip(np.dot(first_unit, second_unit), -1.0, 1.0)))


def _finite_values(values: Iterable[float]) -> list[float]:
    return [value for value in values if math.isfinite(value)]


def _nan_mean(values: Iterable[float]) -> float | None:
    finite = _finite_values(values)
    return float(np.mean(finite)) if finite else None


def _nan_max(values: Iterable[float]) -> float | None:
    finite = _finite_values(values)
    return float(max(finite)) if finite else None


def _finite_or_none(value: float) -> float | None:
    return value if math.isfinite(value) else None
