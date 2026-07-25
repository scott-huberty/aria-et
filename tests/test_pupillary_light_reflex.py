import sys
from collections import Counter

from aria_et.pupillary_light_reflex import build_pupillary_light_reflex_sequence


def test_pupillary_light_reflex_sequence_matches_abcct_o1_order_files():
    sequence = build_pupillary_light_reflex_sequence()

    assert sequence.sequence_id == "pupillary-light-reflex"
    assert [block.block_id for block in sequence.blocks] == [
        f"PLR-B{index:02d}-O1" for index in range(1, 19)
    ]
    assert [trial.stimulus.sound.name for trial in sequence.trials] == [
        "plr78.wav",
        "plr65.wav",
        "plr71.wav",
        "plr65.wav",
        "plr78.wav",
        "plr71.wav",
        "plr78.wav",
        "plr71.wav",
        "plr65.wav",
        "plr71.wav",
        "plr65.wav",
        "plr78.wav",
        "plr65.wav",
        "plr71.wav",
        "plr78.wav",
        "plr71.wav",
        "plr78.wav",
        "plr65.wav",
    ]


def test_pupillary_light_reflex_sequence_has_expected_balance_and_blocks():
    sequence = build_pupillary_light_reflex_sequence()

    assert len(sequence.blocks) == 18
    assert [len(block.trials) for block in sequence.blocks] == [1] * 18
    assert Counter(trial.stimulus_id for trial in sequence.trials) == {
        "plr65": 6,
        "plr71": 6,
        "plr78": 6,
    }


def test_pupillary_light_reflex_sequence_tracks_clip_timing_metadata():
    sequence = build_pupillary_light_reflex_sequence()

    assert all(trial.presentation_seconds == 187 / 30 for trial in sequence.trials)
    assert all(trial.frame_rate_hz == 30 for trial in sequence.trials)
    assert all(trial.frame_count == 187 for trial in sequence.trials)
    assert all(trial.flash_frame_count == 4 for trial in sequence.trials)
    assert {
        trial.stimulus_id: trial.flash_frame_start for trial in sequence.trials
    } == {
        "plr65": 67,
        "plr71": 73,
        "plr78": 80,
    }


def test_pupillary_light_reflex_sequence_tracks_trial_numbering():
    sequence = build_pupillary_light_reflex_sequence()

    assert [trial.trial_id for trial in sequence.trials] == [
        f"plr-{index:02d}" for index in range(1, 19)
    ]
    assert [trial.block_number for trial in sequence.trials] == list(range(1, 19))
    assert all(trial.block_trial_number == 1 for trial in sequence.trials)
    assert [trial.sequence_trial_number for trial in sequence.trials] == list(
        range(1, 19)
    )


def test_pupillary_light_reflex_sequence_uses_bundled_video_assets():
    sequence = build_pupillary_light_reflex_sequence()

    assert all(trial.stimulus.sound.is_file() for trial in sequence.trials)
    assert all(len(trial.stimulus.frames) == 187 for trial in sequence.trials)
    assert all(
        frame.is_file()
        for trial in sequence.trials
        for frame in trial.stimulus.frames
    )


def test_pupillary_light_reflex_domain_does_not_import_runtime_backends():
    assert "psychopy" not in sys.modules
    assert "titta" not in sys.modules
