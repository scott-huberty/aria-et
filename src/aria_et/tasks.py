"""Task registry for the ABCCT battery recreation."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "ACTIVITY_MONITORING",
    "BATTERY_ORDER",
    "CALIBRATION",
    "PUPILLARY_LIGHT_REFLEX",
    "SOCIAL_INTERACTIVE",
    "STANDALONE_TASKS",
    "STATIC_SOCIAL_SCENES",
    "TaskDefinition",
    "task_ids",
]


@dataclass(frozen=True)
class TaskDefinition:
    """Static metadata for a task that can be exposed by runners and tests."""

    task_id: str
    display_name: str


CALIBRATION = TaskDefinition("calibration", "5-point calibration")
ACTIVITY_MONITORING = TaskDefinition("activity-monitoring", "Activity Monitoring")
SOCIAL_INTERACTIVE = TaskDefinition("social-interactive", "Social Interactive")
STATIC_SOCIAL_SCENES = TaskDefinition("static-social-scenes", "Static Social Scenes")
PUPILLARY_LIGHT_REFLEX = TaskDefinition(
    "pupillary-light-reflex", "Pupillary Light Reflex"
)

BATTERY_ORDER: tuple[TaskDefinition, ...] = (
    CALIBRATION,
    ACTIVITY_MONITORING,
    SOCIAL_INTERACTIVE,
    STATIC_SOCIAL_SCENES,
    PUPILLARY_LIGHT_REFLEX,
)

STANDALONE_TASKS: tuple[TaskDefinition, ...] = (
    ACTIVITY_MONITORING,
    SOCIAL_INTERACTIVE,
    STATIC_SOCIAL_SCENES,
    PUPILLARY_LIGHT_REFLEX,
)


def task_ids(tasks: tuple[TaskDefinition, ...] = BATTERY_ORDER) -> tuple[str, ...]:
    """Return the ids of some tasks.

    Parameters
    ----------
    tasks : tuple of TaskDefinition
        The tasks. The default is the battery order.

    Returns
    -------
    tuple of str
        The task ids, in the same order.
    """
    return tuple(task.task_id for task in tasks)
