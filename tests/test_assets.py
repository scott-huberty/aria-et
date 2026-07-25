from aria_et.assets import (
    activity_monitoring_assets,
    gap_overlap_reward_calibration_assets,
    pupillary_light_reflex_assets,
    social_interactive_assets,
    static_social_scenes_assets,
)


def test_gap_overlap_reward_calibration_assets_include_ordered_frame_animations():
    assets = gap_overlap_reward_calibration_assets()

    assert [animation.name for animation in assets.animations] == [
        "Bear_Animation",
        "Face_Animation",
        "Pig_Rotate_Animation",
        "Star_Rotate_Animation",
    ]
    assert [len(animation.frames) for animation in assets.animations] == [36, 37, 37, 36]
    assert all(animation.frames[0].name == "frame_001.png" for animation in assets.animations)
    assert all(
        frame.is_file()
        for animation in assets.animations
        for frame in animation.frames
    )
    assert [sound.name for sound in assets.sounds] == [
        "snd_gap_rew01.wav",
        "snd_gap_rew02.wav",
        "snd_gap_rew03.wav",
        "snd_gap_rew05.wav",
    ]
    assert all(sound.is_file() for sound in assets.sounds)


def test_activity_monitoring_assets_resolve_bundled_media_and_soundtrack():
    assets = activity_monitoring_assets()

    assert assets.image("ams_a4_s6_b4_ga_d1_f1.jpg").is_file()
    assert assets.video("am_a3_s5_b3_gm_d1_f0.avi").is_file()
    assert assets.soundtrack.name == "satie.wav"
    assert assets.soundtrack.is_file()


def test_static_social_scenes_assets_resolve_bundled_images_and_soundtracks():
    assets = static_social_scenes_assets()

    assert assets.image("static1_f0.jpg").is_file()
    assert assets.image("popout1_f0.jpg").is_file()
    assert assets.sound("si_song2_vp080.wav").is_file()


def test_social_interactive_assets_resolve_bundled_videos():
    assets = social_interactive_assets()

    assert assets.video("sibs1_non_15s.avi").is_file()
    assert assets.video("sibs11_soc_15s.avi").is_file()


def test_pupillary_light_reflex_assets_resolve_bundled_videos():
    assets = pupillary_light_reflex_assets()

    assert assets.video("plr65.avi").is_file()
    assert assets.video("plr71.avi").is_file()
    assert assets.video("plr78.avi").is_file()
