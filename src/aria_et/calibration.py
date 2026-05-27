"""Calibration sequence domain model."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources.abc import Traversable

from aria_et.assets import CalibrationAssets, pikachu_calibration_assets


DEFAULT_CALIBRATION_INSET = 0.1


@dataclass(frozen=True)
class NormalizedPoint:
    x: float
    y: float

    def __post_init__(self) -> None:
        if not 0 <= self.x <= 1:
            raise ValueError(f"x must be between 0 and 1: {self.x}")
        if not 0 <= self.y <= 1:
            raise ValueError(f"y must be between 0 and 1: {self.y}")


@dataclass(frozen=True)
class CalibrationTarget:
    label: str
    position: NormalizedPoint


@dataclass(frozen=True)
class CalibrationStimulus:
    animation_frames: tuple[Traversable, ...]
    sound: Traversable


@dataclass(frozen=True)
class CalibrationPoint:
    target: CalibrationTarget
    stimulus: CalibrationStimulus


@dataclass(frozen=True)
class CalibrationSequence:
    sequence_id: str
    points: tuple[CalibrationPoint, ...]


def five_point_targets(inset: float = DEFAULT_CALIBRATION_INSET) -> tuple[CalibrationTarget, ...]:
    if not 0 < inset < 0.5:
        raise ValueError(f"inset must be greater than 0 and less than 0.5: {inset}")

    return (
        CalibrationTarget("center", NormalizedPoint(0.5, 0.5)),
        CalibrationTarget("top-left", NormalizedPoint(inset, inset)),
        CalibrationTarget("top-right", NormalizedPoint(1 - inset, inset)),
        CalibrationTarget("bottom-right", NormalizedPoint(1 - inset, 1 - inset)),
        CalibrationTarget("bottom-left", NormalizedPoint(inset, 1 - inset)),
    )


def calibration_stimulus_from_assets(assets: CalibrationAssets) -> CalibrationStimulus:
    if not assets.animation_frames:
        raise ValueError("Calibration animation must include at least one frame.")

    return CalibrationStimulus(
        animation_frames=assets.animation_frames,
        sound=assets.sound,
    )


def build_pikachu_calibration_sequence(
    inset: float = DEFAULT_CALIBRATION_INSET,
) -> CalibrationSequence:
    stimulus = calibration_stimulus_from_assets(pikachu_calibration_assets())

    return CalibrationSequence(
        sequence_id="pikachu-5-point",
        points=tuple(
            CalibrationPoint(target=target, stimulus=stimulus)
            for target in five_point_targets(inset)
        ),
    )
