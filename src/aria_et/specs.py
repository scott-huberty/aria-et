"""Static task specifications for the ABCCT battery recreation."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "TASK_SPECS",
    "TaskSpec",
    "TrialTypeSpec",
    "get_task_spec",
]


@dataclass(frozen=True)
class TrialTypeSpec:
    """The specified count and duration of one trial type of a task.

    Attributes
    ----------
    name : str
        The trial type, for example ``"static-image"``.
    trial_count : int
        The number of trials of this type.
    duration_seconds : float
        The duration of one trial of this type.
    """

    name: str
    trial_count: int
    duration_seconds: float

    @property
    def total_seconds(self) -> float:
        """Return the total duration of all trials of this type.

        Returns
        -------
        float
            The duration in seconds.
        """
        return self.trial_count * self.duration_seconds


@dataclass(frozen=True)
class TaskSpec:
    """The specified structure of a task, from the ABCCT protocol.

    Attributes
    ----------
    task_id : str
        The task id, for example ``"activity-monitoring"``.
    trial_count : int
        The number of trials.
    block_count : int
        The number of blocks.
    trials_per_block : tuple of int
        The number of trials in each block.
    approximate_duration_seconds : float
        The approximate duration of the task.
    trial_types : tuple of TrialTypeSpec
        The count and duration of each trial type.
    """

    task_id: str
    trial_count: int
    block_count: int
    trials_per_block: tuple[int, ...]
    approximate_duration_seconds: float
    trial_types: tuple[TrialTypeSpec, ...]

    @property
    def specified_trial_count(self) -> int:
        """Return the sum of the trial counts of all trial types.

        Returns
        -------
        int
            The number of trials.
        """
        return sum(trial_type.trial_count for trial_type in self.trial_types)

    @property
    def specified_trial_seconds(self) -> float:
        """Return the sum of the durations of all trials.

        Returns
        -------
        float
            The duration in seconds.
        """
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
        trial_types=(TrialTypeSpec("light-flash", trial_count=18, duration_seconds=6),),
    ),
}


def get_task_spec(task_id: str) -> TaskSpec:
    """Return the specification of one task.

    Parameters
    ----------
    task_id : str
        The task id, for example ``"activity-monitoring"``.

    Returns
    -------
    TaskSpec
        The specification.

    Raises
    ------
    ValueError
        If the task has no specification.
    """
    try:
        return TASK_SPECS[task_id]
    except KeyError as error:
        raise ValueError(f"Unknown task spec: {task_id}") from error
