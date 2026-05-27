"""Static task specifications for the ABCCT battery recreation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrialTypeSpec:
    name: str
    trial_count: int
    duration_seconds: float

    @property
    def total_seconds(self) -> float:
        return self.trial_count * self.duration_seconds


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    trial_count: int
    block_count: int
    trials_per_block: tuple[int, ...]
    approximate_duration_seconds: float
    trial_types: tuple[TrialTypeSpec, ...]

    @property
    def specified_trial_count(self) -> int:
        return sum(trial_type.trial_count for trial_type in self.trial_types)

    @property
    def specified_trial_seconds(self) -> float:
        return sum(trial_type.total_seconds for trial_type in self.trial_types)


TASK_SPECS: dict[str, TaskSpec] = {
    "activity-monitoring": TaskSpec(
        task_id="activity-monitoring",
        trial_count=16,
        block_count=4,
        trials_per_block=(4, 4, 4, 4),
        approximate_duration_seconds=5 * 60,
        trial_types=(
            TrialTypeSpec("static-image", trial_count=8, duration_seconds=10),
            TrialTypeSpec("dynamic-video", trial_count=8, duration_seconds=20),
        ),
    ),
    "social-interactive": TaskSpec(
        task_id="social-interactive",
        trial_count=22,
        block_count=4,
        trials_per_block=(6, 5, 6, 5),
        approximate_duration_seconds=5 * 60,
        trial_types=(
            TrialTypeSpec("parallel-play", trial_count=11, duration_seconds=15),
            TrialTypeSpec("cooperative-play", trial_count=11, duration_seconds=15),
        ),
    ),
    "static-social-scenes": TaskSpec(
        task_id="static-social-scenes",
        trial_count=12,
        block_count=2,
        trials_per_block=(6, 6),
        approximate_duration_seconds=3 * 60,
        trial_types=(
            TrialTypeSpec("visual-search", trial_count=6, duration_seconds=12),
            TrialTypeSpec("static-scene", trial_count=6, duration_seconds=20),
        ),
    ),
    "pupillary-light-reflex": TaskSpec(
        task_id="pupillary-light-reflex",
        trial_count=18,
        block_count=18,
        trials_per_block=(1,) * 18,
        approximate_duration_seconds=2 * 60,
        trial_types=(
            TrialTypeSpec("light-flash", trial_count=18, duration_seconds=6),
        ),
    ),
}


def get_task_spec(task_id: str) -> TaskSpec:
    try:
        return TASK_SPECS[task_id]
    except KeyError as error:
        raise ValueError(f"Unknown task spec: {task_id}") from error
