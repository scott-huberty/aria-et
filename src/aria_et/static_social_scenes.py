"""Static Social Scenes / Visual Search task sequence model."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.abc import Traversable
from typing import Literal

from aria_et.assets import StaticSocialScenesAssets, static_social_scenes_assets

__all__ = [
    "StaticSocialScenesBlock",
    "StaticSocialScenesSequence",
    "StaticSocialScenesStimulus",
    "StaticSocialScenesTrial",
    "StaticSocialScenesTrialType",
    "build_static_social_scenes_sequence",
]


StaticSocialScenesTrialType = Literal["static-scene", "visual-search"]


@dataclass(frozen=True)
class StaticSocialScenesStimulus:
    """The image and soundtrack of one Static Social Scenes trial.

    Attributes
    ----------
    image : Traversable
        The image file.
    soundtrack : Traversable
        The soundtrack. It starts with the image and stops at the trial end.
    """

    image: Traversable
    soundtrack: Traversable


@dataclass(frozen=True)
class StaticSocialScenesTrial:
    """One Static Social Scenes trial.

    Attributes
    ----------
    trial_id : str
        The trial id, unique in the sequence.
    block_number : int
        The one-based number of the block of the trial.
    block_trial_number : int
        The one-based position of the trial in its block.
    sequence_trial_number : int
        The one-based position of the trial in the sequence.
    trial_type : StaticSocialScenesTrialType
        ``"static-scene"`` or ``"visual-search"``.
    stimulus : StaticSocialScenesStimulus
        The image and soundtrack of the trial.
    background_rgb : tuple of (int, int, int)
        The background colour (0-255): black for a static scene, white for
        a visual search.
    preblank_seconds : float
        The first interval on the background colour, at the trial start.
    fixation_seconds : float
        The second interval on the background colour, before the image.
    presentation_seconds : float
        The image duration.
    post_blank_seconds : float
        The blank interval after the image.
    """

    trial_id: str
    block_number: int
    block_trial_number: int
    sequence_trial_number: int
    trial_type: StaticSocialScenesTrialType
    stimulus: StaticSocialScenesStimulus
    background_rgb: tuple[int, int, int]
    preblank_seconds: float
    fixation_seconds: float
    presentation_seconds: float
    post_blank_seconds: float


@dataclass(frozen=True)
class StaticSocialScenesBlock:
    """One block of Static Social Scenes trials.

    Attributes
    ----------
    block_id : str
        The block id.
    block_number : int
        The one-based number of the block in the sequence.
    trials : tuple of StaticSocialScenesTrial
        The trials of the block, in presentation order.
    """

    block_id: str
    block_number: int
    trials: tuple[StaticSocialScenesTrial, ...]


@dataclass(frozen=True)
class StaticSocialScenesSequence:
    """The complete Static Social Scenes sequence.

    Attributes
    ----------
    sequence_id : str
        The sequence id.
    blocks : tuple of StaticSocialScenesBlock
        The blocks, in presentation order.
    """

    sequence_id: str
    blocks: tuple[StaticSocialScenesBlock, ...]

    @property
    def trials(self) -> tuple[StaticSocialScenesTrial, ...]:
        """Return all trials of all blocks.

        Returns
        -------
        tuple of StaticSocialScenesTrial
            The trials, in presentation order.
        """
        return tuple(trial for block in self.blocks for trial in block.trials)


@dataclass(frozen=True)
class _TrialDefinition:
    block_id: str
    trial_type: StaticSocialScenesTrialType
    image_filename: str
    sound_filename: str
    background_rgb: tuple[int, int, int]


_TRIAL_DEFINITIONS: tuple[_TrialDefinition, ...] = (
    _TrialDefinition(
        "VSS-B1", "static-scene", "static1_f0.jpg", "si_song2_vp080.wav", (0, 0, 0)
    ),
    _TrialDefinition(
        "VSS-B1",
        "visual-search",
        "popout1_f0.jpg",
        "si_song3_vp080.wav",
        (255, 255, 255),
    ),
    _TrialDefinition(
        "VSS-B1", "static-scene", "static2_f0.jpg", "si_song4_vp080.wav", (0, 0, 0)
    ),
    _TrialDefinition(
        "VSS-B1",
        "visual-search",
        "popout2_f0.jpg",
        "si_song5_vp080.wav",
        (255, 255, 255),
    ),
    _TrialDefinition(
        "VSS-B1", "static-scene", "static3_f0.jpg", "si_song6_vp080.wav", (0, 0, 0)
    ),
    _TrialDefinition(
        "VSS-B1",
        "visual-search",
        "popout3_f0.jpg",
        "si_song7_vp080.wav",
        (255, 255, 255),
    ),
    _TrialDefinition(
        "VSS-B2", "static-scene", "static4_f0.jpg", "si_song8_vp080.wav", (0, 0, 0)
    ),
    _TrialDefinition(
        "VSS-B2",
        "visual-search",
        "popout4_f0.jpg",
        "si_song9_vp080.wav",
        (255, 255, 255),
    ),
    _TrialDefinition(
        "VSS-B2", "static-scene", "static5_f0.jpg", "si_song3_vp080.wav", (0, 0, 0)
    ),
    _TrialDefinition(
        "VSS-B2",
        "visual-search",
        "popout5_f0.jpg",
        "si_song5_vp080.wav",
        (255, 255, 255),
    ),
    _TrialDefinition(
        "VSS-B2", "static-scene", "static6_f0.jpg", "si_song2_vp080.wav", (0, 0, 0)
    ),
    _TrialDefinition(
        "VSS-B2",
        "visual-search",
        "popout6_f0.jpg",
        "si_song6_vp080.wav",
        (255, 255, 255),
    ),
)


def build_static_social_scenes_sequence() -> StaticSocialScenesSequence:
    """Build the Static Social Scenes sequence from the bundled stimuli.

    Returns
    -------
    StaticSocialScenesSequence
        The sequence, with the trial order and timing of the ABCCT battery.
    """
    assets = static_social_scenes_assets()
    blocks: list[StaticSocialScenesBlock] = []

    for block_number, block_id in enumerate(_block_ids(), start=1):
        block_trials = tuple(
            _build_trial(
                definition,
                assets,
                block_number,
                block_trial_number,
                sequence_trial_number,
            )
            for block_trial_number, (sequence_trial_number, definition) in enumerate(
                (
                    (index, definition)
                    for index, definition in enumerate(_TRIAL_DEFINITIONS, start=1)
                    if definition.block_id == block_id
                ),
                start=1,
            )
        )
        blocks.append(
            StaticSocialScenesBlock(
                block_id=block_id,
                block_number=block_number,
                trials=block_trials,
            )
        )

    return StaticSocialScenesSequence(
        sequence_id="static-social-scenes",
        blocks=tuple(blocks),
    )


def _build_trial(
    definition: _TrialDefinition,
    assets: StaticSocialScenesAssets,
    block_number: int,
    block_trial_number: int,
    sequence_trial_number: int,
) -> StaticSocialScenesTrial:
    return StaticSocialScenesTrial(
        trial_id=f"ss-{sequence_trial_number:02d}",
        block_number=block_number,
        block_trial_number=block_trial_number,
        sequence_trial_number=sequence_trial_number,
        trial_type=definition.trial_type,
        stimulus=StaticSocialScenesStimulus(
            image=assets.image(definition.image_filename),
            soundtrack=assets.sound(definition.sound_filename),
        ),
        background_rgb=definition.background_rgb,
        preblank_seconds=0.1,
        fixation_seconds=1.5,
        presentation_seconds=20 if definition.trial_type == "static-scene" else 12,
        post_blank_seconds=0,
    )


def _block_ids() -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(definition.block_id for definition in _TRIAL_DEFINITIONS)
    )
