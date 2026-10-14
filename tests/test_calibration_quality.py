import math
from types import SimpleNamespace

import numpy as np
import pytest

from aria_et.calibration_quality import (
    EyeQuality,
    adcs_to_ucs,
    point_quality,
    summarize,
)

# A 527 x 296 mm screen, centred 650 mm in front of the tracker origin.
DISPLAY_AREA = SimpleNamespace(
    top_left=(-263.5, 148.0, 0.0),
    top_right=(263.5, 148.0, 0.0),
    bottom_left=(-263.5, -148.0, 0.0),
)
EYE = np.array([0.0, 0.0, 650.0])


def _sample(gaze_point, *, eye="left", origin=EYE, valid=True):
    other = "right" if eye == "left" else "left"
    return {
        f"{eye}_gaze_origin_in_user_coordinate_system": tuple(origin),
        f"{eye}_gaze_point_in_user_coordinate_system": tuple(gaze_point),
        f"{eye}_gaze_origin_validity": int(valid),
        f"{eye}_gaze_point_validity": int(valid),
        f"{other}_gaze_origin_validity": 0,
        f"{other}_gaze_point_validity": 0,
    }


def _point_at_angle(target, degrees):
    """A screen point whose direction from the eye is ``degrees`` off the target."""
    distance = EYE[2] - target[2]
    offset = distance * math.tan(math.radians(degrees))
    return target + np.array([offset, 0.0, 0.0])


def test_adcs_to_ucs_maps_corners_and_centre():
    assert np.allclose(adcs_to_ucs((0, 0), DISPLAY_AREA), (-263.5, 148.0, 0.0))
    assert np.allclose(adcs_to_ucs((1, 1), DISPLAY_AREA), (263.5, -148.0, 0.0))
    assert np.allclose(adcs_to_ucs((0.5, 0.5), DISPLAY_AREA), (0.0, 0.0, 0.0))


def test_accuracy_is_the_angle_between_gaze_and_target():
    target = adcs_to_ucs((0.5, 0.5), DISPLAY_AREA)
    samples = [_sample(_point_at_angle(target, 1.0)) for _ in range(10)]

    quality = point_quality(samples, target, "left")

    assert quality.accuracy_deg == pytest.approx(1.0, abs=1e-6)
    assert quality.precision_rms_deg == pytest.approx(0.0, abs=1e-6)
    assert quality.data_loss == 0.0
    assert quality.n_samples == 10


def test_precision_is_rms_of_sample_to_sample_angles():
    target = adcs_to_ucs((0.5, 0.5), DISPLAY_AREA)
    # Alternate between 0.0 and 0.2 deg off target: every step moves 0.2 deg.
    samples = [_sample(_point_at_angle(target, 0.2 * (i % 2))) for i in range(11)]

    quality = point_quality(samples, target, "left")

    assert quality.precision_rms_deg == pytest.approx(0.2, abs=1e-6)


def test_invalid_samples_count_as_data_loss():
    target = adcs_to_ucs((0.5, 0.5), DISPLAY_AREA)
    samples = [_sample(target)] * 3 + [_sample(target, valid=False)]

    quality = point_quality(samples, target, "left")

    assert quality.data_loss == pytest.approx(0.25)
    assert quality.accuracy_deg == pytest.approx(0.0, abs=1e-6)


def test_an_eye_with_no_valid_samples_is_nan_not_an_error():
    target = adcs_to_ucs((0.5, 0.5), DISPLAY_AREA)
    samples = [_sample(target, eye="left")] * 4

    quality = point_quality(samples, target, "right")

    assert math.isnan(quality.accuracy_deg)
    assert math.isnan(quality.precision_rms_deg)
    assert quality.data_loss == 1.0
    assert quality.as_dict()["accuracy_deg"] is None


def test_summarize_averages_points_and_ignores_missing_targets():
    good = EyeQuality(0.5, 0.05, 0.0, 10)
    worse = EyeQuality(1.5, 0.15, 0.2, 10)
    missing = EyeQuality(math.nan, math.nan, 1.0, 10)

    summary = summarize(
        [
            {"left": good, "right": good},
            {"left": worse, "right": missing},
        ]
    )

    assert summary["left"] == {
        "accuracy_deg": pytest.approx(1.0),
        "max_accuracy_deg": pytest.approx(1.5),
        "precision_rms_deg": pytest.approx(0.1),
        "max_precision_rms_deg": pytest.approx(0.15),
        "data_loss": pytest.approx(0.1),
        "max_data_loss": pytest.approx(0.2),
    }
    assert summary["right"]["accuracy_deg"] == pytest.approx(0.5)
    assert summary["right"]["data_loss"] == pytest.approx(0.5)


def test_summarize_with_no_data_returns_none():
    summary = summarize([])

    assert summary["left"]["accuracy_deg"] is None
    assert summary["right"]["max_accuracy_deg"] is None


def _summary(left, right, *, mean=0.5):
    """A summary with the given worst-target errors and a good mean."""
    return {
        "left": {"accuracy_deg": mean, "max_accuracy_deg": left},
        "right": {"accuracy_deg": mean, "max_accuracy_deg": right},
    }


def test_tolerance_judges_the_worst_target_not_the_mean():
    from aria_et.calibration_quality import tolerance_verdict

    # A good mean (0.5 deg) can't hide one corner at 3.1 deg in each eye.
    verdict = tolerance_verdict(_summary(3.1, 2.8, mean=0.5))

    assert verdict["passed"] is False
    assert verdict["metric"] == "max_accuracy_deg"
    assert verdict["worst_target_deg"] == {"left": 3.1, "right": 2.8}


def test_tolerance_passes_when_at_least_one_eye_has_every_target_within():
    from aria_et.calibration_quality import tolerance_verdict

    verdict = tolerance_verdict(_summary(1.2, 3.4))

    assert verdict["eyes"] == {"left": True, "right": False}
    assert verdict["passed"] is True
    assert verdict["tolerance_deg"] == 2.5
    assert verdict["rule"] == "worst target, at least one eye"


def test_tolerance_counts_the_boundary_as_within_and_handles_missing_eyes():
    from aria_et.calibration_quality import tolerance_verdict

    assert tolerance_verdict(_summary(2.6, 3.0))["passed"] is False
    assert tolerance_verdict(_summary(2.5, 9.0))["passed"] is True
    # An eye with no valid data can't pass on its own.
    assert tolerance_verdict(_summary(None, 3.0))["eyes"]["left"] is None
    assert tolerance_verdict(_summary(None, 3.0))["passed"] is False
    assert tolerance_verdict(None) is None


def test_describe_tolerance_is_a_short_instruction():
    from aria_et.calibration_quality import describe_tolerance, tolerance_verdict

    assert describe_tolerance(tolerance_verdict(_summary(1.2, 3.4))) == (
        "Within 2.5° tolerance: OK to proceed"
    )
    assert describe_tolerance(tolerance_verdict(_summary(2.6, None))) == (
        "Above 2.5° tolerance: re-calibrate"
    )
    assert describe_tolerance(
        tolerance_verdict(_summary(2.6, 3.0)), recalibrate_key="C"
    ) == ("Above 2.5° tolerance: re-calibrate (C)")
    assert describe_tolerance(None) == ""


def test_quality_table_has_mean_and_worst_per_eye_with_marks():
    from aria_et.calibration_quality import (
        FAIL_MARK,
        PASS_MARK,
        quality_table,
        tolerance_mark,
        tolerance_verdict,
    )

    summary = {
        "left": {
            "accuracy_deg": 0.76,
            "max_accuracy_deg": 5.3,
            "precision_rms_deg": 0.07,
            "max_precision_rms_deg": 0.11,
            "data_loss": 0.0,
            "max_data_loss": 0.0,
        },
        "right": {
            "accuracy_deg": 0.94,
            "max_accuracy_deg": 2.4,
            "precision_rms_deg": 0.06,
            "max_precision_rms_deg": None,
            "data_loss": 0.02,
            "max_data_loss": 0.08,
        },
    }

    assert quality_table(summary) == [
        ("Accuracy (deg)", {"left": ("0.76", "5.30"), "right": ("0.94", "2.40")}),
        ("Precision (deg)", {"left": ("0.07", "0.11"), "right": ("0.06", "n/a")}),
        ("Data loss (%)", {"left": ("0", "0"), "right": ("2", "8")}),
    ]
    verdict = tolerance_verdict(summary)
    assert tolerance_mark(verdict, "left") == FAIL_MARK
    assert tolerance_mark(verdict, "right") == PASS_MARK
    assert tolerance_mark(None, "left") == ""
