import sys
from collections import Counter

from aria_et.activity_monitoring import build_activity_monitoring_sequence


def test_activity_monitoring_sequence_matches_abcct_order_files():
    sequence = build_activity_monitoring_sequence()

    assert sequence.sequence_id == "activity-monitoring"
    assert [block.block_id for block in sequence.blocks] == [
        "AM-B1-R",
        "AM-B2-R",
        "AM-B3-R",
        "AM-B4-R",
    ]
    assert [trial.stimulus.media.name for trial in sequence.trials] == [
        "am_a3_s5_b3_gm_d1_f0.avi",
        "ams_a4_s6_b4_ga_d1_f1.jpg",
        "am_a6_s3_b5_ga_d1_f1.avi",
        "ams_a7_s0_b7_gm_d1_f1.jpg",
        "am_a1_s2_b0_gm_d1_f1.avi",
        "am_a2_s7_b2_ga_d1_f0.avi",
        "ams_a0_s3_b3_gm_d1_f1.jpg",
        "ams_a1_s2_b0_ga_d1_f0.jpg",
        "am_a7_s4_b6_gm_d1_f0.avi",
        "ams_a6_s2_b2_ga_d1_f0.jpg",
        "am_a0_s6_b1_ga_d1_f0.avi",
        "ams_a3_s7_b4_gm_d1_f0.jpg",
        "am_a5_s0_b6_ga_d1_f1.avi",
        "ams_a2_s0_b4_ga_d1_f1.jpg",
        "ams_a5_s2_b5_gm_d1_f0.jpg",
        "am_a4_s1_b3_gm_d1_f1.avi",
    ]


def test_activity_monitoring_sequence_has_expected_conditions_and_durations():
    sequence = build_activity_monitoring_sequence()

    assert len(sequence.blocks) == 4
    assert [len(block.trials) for block in sequence.blocks] == [4, 4, 4, 4]
    assert Counter(trial.media_type for trial in sequence.trials) == {
        "dynamic-video": 8,
        "static-image": 8,
    }
    assert Counter(trial.gaze_condition for trial in sequence.trials) == {
        "activity-gaze": 8,
        "mutual-gaze": 8,
    }
    assert all(
        trial.presentation_seconds == 20
        for trial in sequence.trials
        if trial.media_type == "dynamic-video"
    )
    assert all(
        trial.presentation_seconds == 10
        for trial in sequence.trials
        if trial.media_type == "static-image"
    )
    assert all(trial.fixation_seconds == 1 for trial in sequence.trials)


def test_activity_monitoring_static_trials_use_bundled_soundtrack():
    sequence = build_activity_monitoring_sequence()

    static_trials = [
        trial for trial in sequence.trials if trial.media_type == "static-image"
    ]
    assert all(trial.stimulus.soundtrack is not None for trial in static_trials)
    assert all(trial.stimulus.soundtrack.name == "satie.wav" for trial in static_trials)
    assert all(trial.stimulus.soundtrack.is_file() for trial in static_trials)


def test_activity_monitoring_sequence_uses_bundled_stimulus_files():
    sequence = build_activity_monitoring_sequence()

    assert all(trial.stimulus.media.is_file() for trial in sequence.trials)


def test_activity_monitoring_domain_does_not_import_runtime_backends():
    assert "psychopy" not in sys.modules
    assert "titta" not in sys.modules
