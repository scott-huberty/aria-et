"""Pupillary Light Reflex task sequence model."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.abc import Traversable

from aria_et.assets import PupillaryLightReflexAssets, pupillary_light_reflex_assets


@dataclass(frozen=True)
class PupillaryLightReflexStimulus:
    frames: tuple[Traversable, ...]
    sound: Traversable


@dataclass(frozen=True)
class PupillaryLightReflexTrial:
    trial_id: str
    block_number: int
    block_trial_number: int
    sequence_trial_number: int
    stimulus_id: str
    stimulus: PupillaryLightReflexStimulus
    presentation_seconds: float
    frame_rate_hz: float
    frame_count: int
    flash_frame_start: int
    flash_frame_count: int


@dataclass(frozen=True)
class PupillaryLightReflexBlock:
    block_id: str
    block_number: int
    trials: tuple[PupillaryLightReflexTrial, ...]


@dataclass(frozen=True)
class PupillaryLightReflexSequence:
    sequence_id: str
    blocks: tuple[PupillaryLightReflexBlock, ...]

    @property
    def trials(self) -> tuple[PupillaryLightReflexTrial, ...]:
        return tuple(trial for block in self.blocks for trial in block.trials)


@dataclass(frozen=True)
class _TrialDefinition:
    block_id: str
    stimulus_id: str
    flash_frame_start: int


_TRIAL_DEFINITIONS: tuple[_TrialDefinition, ...] = (
    _TrialDefinition("PLR-B01-O1", "plr78", 80),
    _TrialDefinition("PLR-B02-O1", "plr65", 67),
    _TrialDefinition("PLR-B03-O1", "plr71", 73),
    _TrialDefinition("PLR-B04-O1", "plr65", 67),
    _TrialDefinition("PLR-B05-O1", "plr78", 80),
    _TrialDefinition("PLR-B06-O1", "plr71", 73),
    _TrialDefinition("PLR-B07-O1", "plr78", 80),
    _TrialDefinition("PLR-B08-O1", "plr71", 73),
    _TrialDefinition("PLR-B09-O1", "plr65", 67),
    _TrialDefinition("PLR-B10-O1", "plr71", 73),
    _TrialDefinition("PLR-B11-O1", "plr65", 67),
    _TrialDefinition("PLR-B12-O1", "plr78", 80),
    _TrialDefinition("PLR-B13-O1", "plr65", 67),
    _TrialDefinition("PLR-B14-O1", "plr71", 73),
    _TrialDefinition("PLR-B15-O1", "plr78", 80),
    _TrialDefinition("PLR-B16-O1", "plr71", 73),
    _TrialDefinition("PLR-B17-O1", "plr78", 80),
    _TrialDefinition("PLR-B18-O1", "plr65", 67),
)


def build_pupillary_light_reflex_sequence() -> PupillaryLightReflexSequence:
    assets = pupillary_light_reflex_assets()
    blocks = tuple(
        PupillaryLightReflexBlock(
            block_id=definition.block_id,
            block_number=sequence_trial_number,
            trials=(
                _build_trial(
                    definition,
                    assets,
                    sequence_trial_number,
                ),
            ),
        )
        for sequence_trial_number, definition in enumerate(_TRIAL_DEFINITIONS, start=1)
    )

    return PupillaryLightReflexSequence(
        sequence_id="pupillary-light-reflex",
        blocks=blocks,
    )


def _build_trial(
    definition: _TrialDefinition,
    assets: PupillaryLightReflexAssets,
    sequence_trial_number: int,
) -> PupillaryLightReflexTrial:
    frames = assets.frames(definition.stimulus_id)
    return PupillaryLightReflexTrial(
        trial_id=f"plr-{sequence_trial_number:02d}",
        block_number=sequence_trial_number,
        block_trial_number=1,
        sequence_trial_number=sequence_trial_number,
        stimulus_id=definition.stimulus_id,
        stimulus=PupillaryLightReflexStimulus(
            frames=frames,
            sound=assets.sound(definition.stimulus_id),
        ),
        presentation_seconds=len(frames) / 30,
        frame_rate_hz=30,
        frame_count=len(frames),
        flash_frame_start=definition.flash_frame_start,
        flash_frame_count=4,
    )
