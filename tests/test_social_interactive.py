import sys
from collections import Counter

from aria_et.social_interactive import build_social_interactive_sequence


def test_social_interactive_sequence_matches_abcct_order_files():
    sequence = build_social_interactive_sequence()

    assert sequence.sequence_id == "social-interactive"
    assert [block.block_id for block in sequence.blocks] == [
        "SI-B1",
        "SI-B2",
        "SI-B3",
        "SI-B4",
    ]
    assert [trial.stimulus.video.name for trial in sequence.trials] == [
        "sibs1_non_15s.avi",
        "sibs5_non_15s.avi",
        "sibs4_non_15s.avi",
        "sibs8_soc_15s.avi",
        "sibs10_soc_15s.avi",
        "sibs3_non_15s.avi",
        "sibs2_soc_15s.avi",
        "sibs6_non_15s.avi",
        "sibs9_soc_15s.avi",
        "sibs11_non_15s.avi",
        "sibs12_soc_15s.avi",
        "sibs1_soc_15s.avi",
        "sibs8_non_15s.avi",
        "sibs5_soc_15s.avi",
        "sibs4_soc_15s.avi",
        "sibs3_soc_15s.avi",
        "sibs10_non_15s.avi",
        "sibs2_non_15s.avi",
        "sibs6_soc_15s.avi",
        "sibs12_non_15s.avi",
        "sibs9_non_15s.avi",
        "sibs11_soc_15s.avi",
    ]


def test_social_interactive_sequence_has_expected_conditions_and_durations():
    sequence = build_social_interactive_sequence()

    assert len(sequence.blocks) == 4
    assert [len(block.trials) for block in sequence.blocks] == [6, 5, 6, 5]
    assert Counter(trial.play_condition for trial in sequence.trials) == {
        "parallel-play": 11,
        "cooperative-play": 11,
    }
    assert all(trial.presentation_seconds == 15 for trial in sequence.trials)
    assert all(trial.fixation_seconds == 1 for trial in sequence.trials)
    assert all(trial.post_blank_seconds == 0.25 for trial in sequence.trials)


def test_social_interactive_sequence_tracks_source_ids():
    sequence = build_social_interactive_sequence()

    assert [(trial.source_index, trial.source_id) for trial in sequence.trials[:6]] == [
        (1, "01"),
        (2, "05"),
        (3, "04"),
        (4, "08"),
        (5, "10"),
        (6, "03"),
    ]


def test_social_interactive_sequence_uses_bundled_video_assets():
    sequence = build_social_interactive_sequence()

    assert all(trial.stimulus.video.is_file() for trial in sequence.trials)


def test_social_interactive_domain_does_not_import_runtime_backends():
    assert "psychopy" not in sys.modules
    assert "titta" not in sys.modules
