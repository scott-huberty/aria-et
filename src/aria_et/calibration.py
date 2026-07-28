"""Calibration sequence domain model."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.abc import Traversable
from random import Random

from aria_et.assets import (
    CalibrationRewardAssets,
    gap_overlap_reward_calibration_assets,
)


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
    sound: Traversable | None = None


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


def calibration_stimuli_from_reward_assets(
    assets: CalibrationRewardAssets,
) -> tuple[CalibrationStimulus, ...]:
    if not assets.animations:
        raise ValueError("Calibration reward assets must include at least one animation.")

    if any(not animation.frames for animation in assets.animations):
        raise ValueError("Calibration reward animations must include at least one frame.")

    if not assets.sounds:
        raise ValueError("Calibration reward assets must include at least one sound.")

    return tuple(
        CalibrationStimulus(animation_frames=animation.frames, sound=sound)
        for animation in assets.animations
        for sound in assets.sounds
    )


def build_gap_overlap_reward_calibration_sequence(
    inset: float = DEFAULT_CALIBRATION_INSET,
    rng: Random | None = None,
) -> CalibrationSequence:
    randomizer = rng or Random()
    stimuli = calibration_stimuli_from_reward_assets(gap_overlap_reward_calibration_assets())

    return CalibrationSequence(
        sequence_id="gap-overlap-reward-5-point",
        points=tuple(
            CalibrationPoint(target=target, stimulus=randomizer.choice(stimuli))
            for target in five_point_targets(inset)
        ),
    )
