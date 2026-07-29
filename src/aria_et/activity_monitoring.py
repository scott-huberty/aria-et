"""Activity Monitoring task sequence model."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.abc import Traversable
from typing import Literal

from aria_et.assets import ActivityMonitoringAssets, activity_monitoring_assets


ActivityMonitoringMediaType = Literal["dynamic-video", "static-image"]
ActivityMonitoringGazeCondition = Literal["activity-gaze", "mutual-gaze"]


@dataclass(frozen=True)
class ActivityMonitoringStimulus:
    media: Traversable
    soundtrack: Traversable | None = None


@dataclass(frozen=True)
class ActivityMonitoringTrial:
    trial_id: str
    block_number: int
    block_trial_number: int
    sequence_trial_number: int
    media_type: ActivityMonitoringMediaType
    gaze_condition: ActivityMonitoringGazeCondition
    stimulus: ActivityMonitoringStimulus
    fixation_seconds: float
    presentation_seconds: float
    post_blank_seconds: float


@dataclass(frozen=True)
class ActivityMonitoringBlock:
    block_id: str
    block_number: int
    trials: tuple[ActivityMonitoringTrial, ...]


@dataclass(frozen=True)
class ActivityMonitoringSequence:
    sequence_id: str
    blocks: tuple[ActivityMonitoringBlock, ...]

    @property
    def trials(self) -> tuple[ActivityMonitoringTrial, ...]:
        return tuple(trial for block in self.blocks for trial in block.trials)


@dataclass(frozen=True)
class _TrialDefinition:
    block_id: str
    media_type: ActivityMonitoringMediaType
    gaze_condition: ActivityMonitoringGazeCondition
    filename: str


_TRIAL_DEFINITIONS: tuple[_TrialDefinition, ...] = (
    _TrialDefinition(
        "AM-B1-R", "dynamic-video", "mutual-gaze", "am_a3_s5_b3_gm_d1_f0.mp4"
    ),
    _TrialDefinition(
        "AM-B1-R", "static-image", "activity-gaze", "ams_a4_s6_b4_ga_d1_f1.jpg"
    ),
    _TrialDefinition(
        "AM-B1-R", "dynamic-video", "activity-gaze", "am_a6_s3_b5_ga_d1_f1.mp4"
    ),
    _TrialDefinition(
        "AM-B1-R", "static-image", "mutual-gaze", "ams_a7_s0_b7_gm_d1_f1.jpg"
    ),
    _TrialDefinition(
        "AM-B2-R", "dynamic-video", "mutual-gaze", "am_a1_s2_b0_gm_d1_f1.mp4"
    ),
    _TrialDefinition(
        "AM-B2-R", "dynamic-video", "activity-gaze", "am_a2_s7_b2_ga_d1_f0.mp4"
    ),
    _TrialDefinition(
        "AM-B2-R", "static-image", "mutual-gaze", "ams_a0_s3_b3_gm_d1_f1.jpg"
    ),
    _TrialDefinition(
        "AM-B2-R", "static-image", "activity-gaze", "ams_a1_s2_b0_ga_d1_f0.jpg"
    ),
    _TrialDefinition(
        "AM-B3-R", "dynamic-video", "mutual-gaze", "am_a7_s4_b6_gm_d1_f0.mp4"
    ),
    _TrialDefinition(
        "AM-B3-R", "static-image", "activity-gaze", "ams_a6_s2_b2_ga_d1_f0.jpg"
    ),
    _TrialDefinition(
        "AM-B3-R", "dynamic-video", "activity-gaze", "am_a0_s6_b1_ga_d1_f0.mp4"
    ),
    _TrialDefinition(
        "AM-B3-R", "static-image", "mutual-gaze", "ams_a3_s7_b4_gm_d1_f0.jpg"
    ),
    _TrialDefinition(
        "AM-B4-R", "dynamic-video", "activity-gaze", "am_a5_s0_b6_ga_d1_f1.mp4"
    ),
    _TrialDefinition(
        "AM-B4-R", "static-image", "activity-gaze", "ams_a2_s0_b4_ga_d1_f1.jpg"
    ),
    _TrialDefinition(
        "AM-B4-R", "static-image", "mutual-gaze", "ams_a5_s2_b5_gm_d1_f0.jpg"
    ),
    _TrialDefinition(
        "AM-B4-R", "dynamic-video", "mutual-gaze", "am_a4_s1_b3_gm_d1_f1.mp4"
    ),
)


def build_activity_monitoring_sequence() -> ActivityMonitoringSequence:
    assets = activity_monitoring_assets()
    blocks: list[ActivityMonitoringBlock] = []

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
            ActivityMonitoringBlock(
                block_id=block_id,
                block_number=block_number,
                trials=block_trials,
            )
        )

    return ActivityMonitoringSequence(
        sequence_id="activity-monitoring",
        blocks=tuple(blocks),
    )


def _build_trial(
    definition: _TrialDefinition,
    assets: ActivityMonitoringAssets,
    block_number: int,
    block_trial_number: int,
    sequence_trial_number: int,
) -> ActivityMonitoringTrial:
    media = (
        assets.video(definition.filename)
        if definition.media_type == "dynamic-video"
        else assets.image(definition.filename)
    )
    return ActivityMonitoringTrial(
        trial_id=f"am-{sequence_trial_number:02d}",
        block_number=block_number,
        block_trial_number=block_trial_number,
        sequence_trial_number=sequence_trial_number,
        media_type=definition.media_type,
        gaze_condition=definition.gaze_condition,
        stimulus=ActivityMonitoringStimulus(
            media=media,
            soundtrack=assets.soundtrack if definition.media_type == "static-image" else None,
        ),
        fixation_seconds=1,
        presentation_seconds=20 if definition.media_type == "dynamic-video" else 10,
        post_blank_seconds=0.25 if definition.media_type == "dynamic-video" else 0.5,
    )


def _block_ids() -> tuple[str, ...]:
    return tuple(dict.fromkeys(definition.block_id for definition in _TRIAL_DEFINITIONS))
