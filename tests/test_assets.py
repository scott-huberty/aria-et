from aria_et.assets import abcct_asset, pikachu_calibration_assets


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
