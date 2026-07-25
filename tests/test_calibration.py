import sys
from random import Random

import pytest

from aria_et.calibration import (
    CalibrationAssets,
    NormalizedPoint,
    build_gap_overlap_reward_calibration_sequence,
    build_pikachu_calibration_sequence,
    calibration_stimulus_from_assets,
    calibration_stimuli_from_reward_assets,
    five_point_targets,
)
from aria_et.assets import CalibrationRewardAnimation, CalibrationRewardAssets


def test_five_point_targets_have_deterministic_order():
    targets = five_point_targets()

    assert [target.label for target in targets] == [
        "center",
        "top-left",
        "top-right",
        "bottom-right",
        "bottom-left",
    ]
    assert [(target.position.x, target.position.y) for target in targets] == [
        (0.5, 0.5),
        (0.1, 0.1),
        (0.9, 0.1),
        (0.9, 0.9),
        (0.1, 0.9),
    ]


def test_five_point_targets_accept_custom_inset():
    targets = five_point_targets(inset=0.2)

    assert [(target.position.x, target.position.y) for target in targets] == [
        (0.5, 0.5),
        (0.2, 0.2),
        (0.8, 0.2),
        (0.8, 0.8),
        (0.2, 0.8),
    ]


@pytest.mark.parametrize("inset", [0, -0.1, 0.5, 1])
def test_five_point_targets_reject_invalid_inset(inset):
    with pytest.raises(ValueError, match="inset must be greater than 0"):
        five_point_targets(inset=inset)


@pytest.mark.parametrize(
    ("x", "y"),
    [
        (-0.1, 0.5),
        (1.1, 0.5),
        (0.5, -0.1),
        (0.5, 1.1),
    ],
)
def test_normalized_points_must_stay_in_bounds(x, y):
    with pytest.raises(ValueError):
        NormalizedPoint(x, y)


def test_gap_overlap_reward_calibration_sequence_has_five_bundled_asset_points():
    sequence = build_gap_overlap_reward_calibration_sequence(rng=Random(1))

    assert sequence.sequence_id == "gap-overlap-reward-5-point"
    assert len(sequence.points) == 5
    assert [point.target.label for point in sequence.points] == [
        "center",
        "top-left",
        "top-right",
        "bottom-right",
        "bottom-left",
    ]
    assert all(point.stimulus.sound is None for point in sequence.points)
    assert all(
        point.stimulus.animation_frames[0].name == "frame_001.png"
        for point in sequence.points
    )
    assert all(len(point.stimulus.animation_frames) in {36, 37} for point in sequence.points)


def test_gap_overlap_reward_calibration_sequence_selects_per_point_with_rng():
    sequence = build_gap_overlap_reward_calibration_sequence(rng=Random(4))

    assert [point.stimulus.animation_frames[0].parent.name for point in sequence.points] == [
        "Face_Animation",
        "Mini_Animation",
        "Bear_Animation",
        "Pig_Rotate_Animation",
        "Pig_Rotate_Animation",
    ]


def test_pikachu_calibration_sequence_name_is_a_compatibility_wrapper():
    sequence = build_pikachu_calibration_sequence()

    assert sequence.sequence_id == "gap-overlap-reward-5-point"


def test_calibration_stimulus_requires_animation_frames():
    with pytest.raises(ValueError, match="at least one frame"):
        calibration_stimulus_from_assets(
            CalibrationAssets(animation_frames=(), sound="pikachu.wav")
        )


def test_calibration_reward_stimuli_require_animations():
    with pytest.raises(ValueError, match="at least one animation"):
        calibration_stimuli_from_reward_assets(CalibrationRewardAssets(animations=()))


def test_calibration_reward_stimuli_require_animation_frames():
    with pytest.raises(ValueError, match="at least one frame"):
        calibration_stimuli_from_reward_assets(
            CalibrationRewardAssets(
                animations=(CalibrationRewardAnimation(name="empty", frames=()),)
            )
        )


def test_calibration_domain_does_not_import_runtime_backends():
    assert "psychopy" not in sys.modules
    assert "titta" not in sys.modules
