"""Access to bundled stimulus assets."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable


ASSET_PACKAGE = "aria_et"
ASSET_ROOT = "assets/abcct"


@dataclass(frozen=True)
class CalibrationAssets:
    animation_frames: tuple[Traversable, ...]
    sound: Traversable | None = None


@dataclass(frozen=True)
class CalibrationRewardAssets:
    animations: tuple["CalibrationRewardAnimation", ...]


@dataclass(frozen=True)
class CalibrationRewardAnimation:
    name: str
    frames: tuple[Traversable, ...]


@dataclass(frozen=True)
class ActivityMonitoringAssets:
    soundtrack: Traversable

    def image(self, filename: str) -> Traversable:
        return abcct_asset(f"activity-monitoring/images/{filename}")

    def video(self, filename: str) -> Traversable:
        return abcct_asset(f"activity-monitoring/videos/{filename}")


@dataclass(frozen=True)
class StaticSocialScenesAssets:
    def image(self, filename: str) -> Traversable:
        return abcct_asset(f"static-social-scenes/images/{filename}")

    def sound(self, filename: str) -> Traversable:
        return abcct_asset(f"static-social-scenes/sounds/{filename}")


@dataclass(frozen=True)
class SocialInteractiveAssets:
    def video(self, filename: str) -> Traversable:
        return abcct_asset(f"social-interactive/videos/{filename}")


@dataclass(frozen=True)
class PupillaryLightReflexAssets:
    def video(self, filename: str) -> Traversable:
        return abcct_asset(f"pupillary-light-reflex/videos/{filename}")


def abcct_asset(relative_path: str) -> Traversable:
    return files(ASSET_PACKAGE).joinpath(ASSET_ROOT, relative_path)


def pikachu_calibration_assets() -> CalibrationAssets:
    frame_dir = abcct_asset("calibration/pikachu/frames")
    frames = tuple(
        sorted(
            (path for path in frame_dir.iterdir() if path.name.endswith(".bmp")),
            key=lambda path: path.name,
        )
    )
    sound = abcct_asset("calibration/pikachu/sounds/pikachu.wav")

    return CalibrationAssets(animation_frames=frames, sound=sound)


def gap_overlap_reward_calibration_assets() -> CalibrationRewardAssets:
    animation_dir = abcct_asset("calibration/Gap-Overlap/Frames/Reward")
    animations = tuple(
        CalibrationRewardAnimation(
            name=animation.name,
            frames=tuple(
                sorted(
                    (path for path in animation.iterdir() if path.name.endswith(".png")),
                    key=lambda path: path.name,
                )
            ),
        )
        for animation in sorted(
            (path for path in animation_dir.iterdir() if path.is_dir()),
            key=lambda path: path.name,
        )
    )

    return CalibrationRewardAssets(animations=animations)


def activity_monitoring_assets() -> ActivityMonitoringAssets:
    return ActivityMonitoringAssets(
        soundtrack=abcct_asset("activity-monitoring/sounds/satie.wav")
    )


def static_social_scenes_assets() -> StaticSocialScenesAssets:
    return StaticSocialScenesAssets()


def social_interactive_assets() -> SocialInteractiveAssets:
    return SocialInteractiveAssets()


def pupillary_light_reflex_assets() -> PupillaryLightReflexAssets:
    return PupillaryLightReflexAssets()
