import sys

import pytest

from aria_et.calibration import (
    CalibrationAssets,
    NormalizedPoint,
    build_pikachu_calibration_sequence,
    calibration_stimulus_from_assets,
    five_point_targets,
)


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


def test_pikachu_calibration_sequence_has_five_bundled_asset_points():
    sequence = build_pikachu_calibration_sequence()

    assert sequence.sequence_id == "pikachu-5-point"
    assert len(sequence.points) == 5
    assert [point.target.label for point in sequence.points] == [
        "center",
        "top-left",
        "top-right",
        "bottom-right",
        "bottom-left",
    ]
    assert all(len(point.stimulus.animation_frames) == 10 for point in sequence.points)
    assert all(point.stimulus.sound.name == "pikachu.wav" for point in sequence.points)
    assert all(
        frame.name.endswith(".bmp")
        for point in sequence.points
        for frame in point.stimulus.animation_frames
    )


def test_pikachu_calibration_sequence_reuses_one_stimulus_definition():
    sequence = build_pikachu_calibration_sequence()
    first_stimulus = sequence.points[0].stimulus

    assert all(point.stimulus is first_stimulus for point in sequence.points)


def test_calibration_stimulus_requires_animation_frames():
    with pytest.raises(ValueError, match="at least one frame"):
        calibration_stimulus_from_assets(
            CalibrationAssets(animation_frames=(), sound="pikachu.wav")
        )


def test_calibration_domain_does_not_import_runtime_backends():
    assert "psychopy" not in sys.modules
    assert "titta" not in sys.modules
