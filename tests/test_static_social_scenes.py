import sys
from collections import Counter

from aria_et.static_social_scenes import build_static_social_scenes_sequence


def test_static_social_scenes_sequence_matches_abcct_day_one_order_files():
    sequence = build_static_social_scenes_sequence()

    assert sequence.sequence_id == "static-social-scenes"
    assert [block.block_id for block in sequence.blocks] == ["VSS-B1", "VSS-B2"]
    assert [trial.stimulus.image.name for trial in sequence.trials] == [
        "static1_f0.jpg",
        "popout1_f0.jpg",
        "static2_f0.jpg",
        "popout2_f0.jpg",
        "static3_f0.jpg",
        "popout3_f0.jpg",
        "static4_f0.jpg",
        "popout4_f0.jpg",
        "static5_f0.jpg",
        "popout5_f0.jpg",
        "static6_f0.jpg",
        "popout6_f0.jpg",
    ]


def test_static_social_scenes_sequence_has_expected_trial_types_and_durations():
    sequence = build_static_social_scenes_sequence()

    assert len(sequence.blocks) == 2
    assert [len(block.trials) for block in sequence.blocks] == [6, 6]
    assert Counter(trial.trial_type for trial in sequence.trials) == {
        "static-scene": 6,
        "visual-search": 6,
    }
    assert all(
        trial.presentation_seconds == 20
        for trial in sequence.trials
        if trial.trial_type == "static-scene"
    )
    assert all(
        trial.presentation_seconds == 12
        for trial in sequence.trials
        if trial.trial_type == "visual-search"
    )
    assert all(trial.preblank_seconds == 0.1 for trial in sequence.trials)
    assert all(trial.fixation_seconds == 1.5 for trial in sequence.trials)
    assert all(trial.post_blank_seconds == 0 for trial in sequence.trials)


def test_static_social_scenes_sequence_tracks_background_color_and_soundtracks():
    sequence = build_static_social_scenes_sequence()

    assert [
        (trial.trial_type, trial.background_rgb, trial.stimulus.soundtrack.name)
        for trial in sequence.trials[:4]
    ] == [
        ("static-scene", (0, 0, 0), "si_song2_vp080.wav"),
        ("visual-search", (255, 255, 255), "si_song3_vp080.wav"),
        ("static-scene", (0, 0, 0), "si_song4_vp080.wav"),
        ("visual-search", (255, 255, 255), "si_song5_vp080.wav"),
    ]


def test_static_social_scenes_sequence_uses_bundled_assets():
    sequence = build_static_social_scenes_sequence()

    assert all(trial.stimulus.image.is_file() for trial in sequence.trials)
    assert all(trial.stimulus.soundtrack.is_file() for trial in sequence.trials)


def test_static_social_scenes_domain_does_not_import_runtime_backends():
    assert "psychopy" not in sys.modules
    assert "titta" not in sys.modules
