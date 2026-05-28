from aria_et.assets import (
    abcct_asset,
    activity_monitoring_assets,
    pikachu_calibration_assets,
    static_social_scenes_assets,
)


def test_can_resolve_bundled_abcct_asset():
    asset = abcct_asset("calibration/pikachu/sounds/pikachu.wav")

    assert asset.is_file()


def test_pikachu_calibration_assets_include_ordered_animation_frames():
    assets = pikachu_calibration_assets()

    assert [frame.name for frame in assets.animation_frames] == [
        "imrewspn_001.bmp",
        "imrewspn_002.bmp",
        "imrewspn_003.bmp",
        "imrewspn_004.bmp",
        "imrewspn_005.bmp",
        "imrewspn_006.bmp",
        "imrewspn_007.bmp",
        "imrewspn_008.bmp",
        "imrewspn_009.bmp",
        "imrewspn_010.bmp",
    ]
    assert all(frame.is_file() for frame in assets.animation_frames)


def test_pikachu_calibration_assets_include_sound():
    assets = pikachu_calibration_assets()

    assert assets.sound.name == "pikachu.wav"
    assert assets.sound.is_file()


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
