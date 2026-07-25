"""Access to bundled stimulus assets."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable


ASSET_PACKAGE = "aria_et"
ASSET_ROOT = "assets/abcct"


@dataclass(frozen=True)
class CalibrationRewardAssets:
    animations: tuple["CalibrationRewardAnimation", ...]
    sounds: tuple[Traversable, ...]


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
    def frames(self, stimulus_id: str) -> tuple[Traversable, ...]:
        frame_dir = abcct_asset(f"pupillary-light-reflex/frames/{stimulus_id}")
        return tuple(
            sorted(
                (path for path in frame_dir.iterdir() if path.name.endswith(".png")),
                key=lambda path: path.name,
            )
        )

    def sound(self, stimulus_id: str) -> Traversable:
        return abcct_asset(f"pupillary-light-reflex/sounds/{stimulus_id}.wav")


def abcct_asset(relative_path: str) -> Traversable:
    return files(ASSET_PACKAGE).joinpath(ASSET_ROOT, relative_path)


def gap_overlap_reward_calibration_assets() -> CalibrationRewardAssets:
    animation_dir = abcct_asset("calibration/Gap-Overlap/Frames/Reward")
    sound_dir = abcct_asset("calibration/Gap-Overlap/Auditory")
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
    sounds = tuple(
        sorted(
            (
                path
                for path in sound_dir.iterdir()
                if path.name.startswith("snd_gap_rew") and path.name.endswith(".wav")
            ),
            key=lambda path: path.name,
        )
    )

    return CalibrationRewardAssets(animations=animations, sounds=sounds)


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
