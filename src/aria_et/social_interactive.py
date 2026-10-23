"""Social Interactive task sequence model."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.abc import Traversable
from typing import Literal

from aria_et.assets import SocialInteractiveAssets, social_interactive_assets

__all__ = [
    "SocialInteractiveBlock",
    "SocialInteractivePlayCondition",
    "SocialInteractiveSequence",
    "SocialInteractiveStimulus",
    "SocialInteractiveTrial",
    "build_social_interactive_sequence",
]


SocialInteractivePlayCondition = Literal["parallel-play", "cooperative-play"]


@dataclass(frozen=True)
class SocialInteractiveStimulus:
    """The video of one Social Interactive trial.

    Attributes
    ----------
    video : Traversable
        The video file, with its own audio.
    """

    video: Traversable


@dataclass(frozen=True)
class SocialInteractiveTrial:
    """One Social Interactive trial.

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
    source_index : int
        The one-based position of the trial in the source trial list.
    source_id : str
        The id of the source video, for example ``"05"`` for ``sibs5_*``.
    play_condition : SocialInteractivePlayCondition
        ``"parallel-play"`` or ``"cooperative-play"``.
    stimulus : SocialInteractiveStimulus
        The video of the trial.
    fixation_seconds : float
        The blank interval before the video.
    presentation_seconds : float
        The video duration.
    post_blank_seconds : float
        The blank interval after the video.
    """

    trial_id: str
    block_number: int
    block_trial_number: int
    sequence_trial_number: int
    source_index: int
    source_id: str
    play_condition: SocialInteractivePlayCondition
    stimulus: SocialInteractiveStimulus
    fixation_seconds: float
    presentation_seconds: float
    post_blank_seconds: float


@dataclass(frozen=True)
class SocialInteractiveBlock:
    """One block of Social Interactive trials.

    Attributes
    ----------
    block_id : str
        The block id.
    block_number : int
        The one-based number of the block in the sequence.
    trials : tuple of SocialInteractiveTrial
        The trials of the block, in presentation order.
    """

    block_id: str
    block_number: int
    trials: tuple[SocialInteractiveTrial, ...]


@dataclass(frozen=True)
class SocialInteractiveSequence:
    """The complete Social Interactive sequence.

    Attributes
    ----------
    sequence_id : str
        The sequence id.
    blocks : tuple of SocialInteractiveBlock
        The blocks, in presentation order.
    """

    sequence_id: str
    blocks: tuple[SocialInteractiveBlock, ...]

    @property
    def trials(self) -> tuple[SocialInteractiveTrial, ...]:
        """Return all trials of all blocks.

        Returns
        -------
        tuple of SocialInteractiveTrial
            The trials, in presentation order.
        """
        return tuple(trial for block in self.blocks for trial in block.trials)


@dataclass(frozen=True)
class _TrialDefinition:
    block_id: str
    source_index: int
    source_id: str
    play_condition: SocialInteractivePlayCondition
    filename: str


_TRIAL_DEFINITIONS: tuple[_TrialDefinition, ...] = (
    _TrialDefinition("SI-B1", 1, "01", "parallel-play", "sibs1_non_15s.mp4"),
    _TrialDefinition("SI-B1", 2, "05", "parallel-play", "sibs5_non_15s.mp4"),
    _TrialDefinition("SI-B1", 3, "04", "parallel-play", "sibs4_non_15s.mp4"),
    _TrialDefinition("SI-B1", 4, "08", "cooperative-play", "sibs8_soc_15s.mp4"),
    _TrialDefinition("SI-B1", 5, "10", "cooperative-play", "sibs10_soc_15s.mp4"),
    _TrialDefinition("SI-B1", 6, "03", "parallel-play", "sibs3_non_15s.mp4"),
    _TrialDefinition("SI-B2", 7, "02", "cooperative-play", "sibs2_soc_15s.mp4"),
    _TrialDefinition("SI-B2", 8, "06", "parallel-play", "sibs6_non_15s.mp4"),
    _TrialDefinition("SI-B2", 9, "09", "cooperative-play", "sibs9_soc_15s.mp4"),
    _TrialDefinition("SI-B2", 10, "11", "parallel-play", "sibs11_non_15s.mp4"),
    _TrialDefinition("SI-B2", 11, "12", "cooperative-play", "sibs12_soc_15s.mp4"),
    _TrialDefinition("SI-B3", 12, "01", "cooperative-play", "sibs1_soc_15s.mp4"),
    _TrialDefinition("SI-B3", 13, "08", "parallel-play", "sibs8_non_15s.mp4"),
    _TrialDefinition("SI-B3", 14, "05", "cooperative-play", "sibs5_soc_15s.mp4"),
    _TrialDefinition("SI-B3", 15, "04", "cooperative-play", "sibs4_soc_15s.mp4"),
    _TrialDefinition("SI-B3", 16, "03", "cooperative-play", "sibs3_soc_15s.mp4"),
    _TrialDefinition("SI-B3", 17, "10", "parallel-play", "sibs10_non_15s.mp4"),
    _TrialDefinition("SI-B4", 18, "02", "parallel-play", "sibs2_non_15s.mp4"),
    _TrialDefinition("SI-B4", 19, "06", "cooperative-play", "sibs6_soc_15s.mp4"),
    _TrialDefinition("SI-B4", 20, "12", "parallel-play", "sibs12_non_15s.mp4"),
    _TrialDefinition("SI-B4", 21, "09", "parallel-play", "sibs9_non_15s.mp4"),
    _TrialDefinition("SI-B4", 22, "11", "cooperative-play", "sibs11_soc_15s.mp4"),
)


def build_social_interactive_sequence() -> SocialInteractiveSequence:
    """Build the Social Interactive sequence from the bundled stimuli.

    Returns
    -------
    SocialInteractiveSequence
        The sequence, with the trial order and timing of the ABCCT battery.
    """
    assets = social_interactive_assets()
    blocks: list[SocialInteractiveBlock] = []

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
            SocialInteractiveBlock(
                block_id=block_id,
                block_number=block_number,
                trials=block_trials,
            )
        )

    return SocialInteractiveSequence(
        sequence_id="social-interactive",
        blocks=tuple(blocks),
    )


def _build_trial(
    definition: _TrialDefinition,
    assets: SocialInteractiveAssets,
    block_number: int,
    block_trial_number: int,
    sequence_trial_number: int,
) -> SocialInteractiveTrial:
    return SocialInteractiveTrial(
        trial_id=f"si-{sequence_trial_number:02d}",
        block_number=block_number,
        block_trial_number=block_trial_number,
        sequence_trial_number=sequence_trial_number,
        source_index=definition.source_index,
        source_id=definition.source_id,
        play_condition=definition.play_condition,
        stimulus=SocialInteractiveStimulus(video=assets.video(definition.filename)),
        fixation_seconds=1,
        presentation_seconds=15,
        post_blank_seconds=0.25,
    )


def _block_ids() -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(definition.block_id for definition in _TRIAL_DEFINITIONS)
    )
