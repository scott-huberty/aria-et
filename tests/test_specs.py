import pytest

from aria_et.specs import TASK_SPECS, get_task_spec
from aria_et.tasks import STANDALONE_TASKS


def test_specs_exist_for_each_standalone_task():
    assert set(TASK_SPECS) == {task.task_id for task in STANDALONE_TASKS}


@pytest.mark.parametrize(
    ("task_id", "trial_count", "block_count", "trials_per_block"),
    [
        ("activity-monitoring", 16, 4, (4, 4, 4, 4)),
        ("social-interactive", 22, 4, (6, 5, 6, 5)),
        ("static-social-scenes", 12, 2, (6, 6)),
        ("pupillary-light-reflex", 18, 18, (1,) * 18),
    ],
)
def test_specs_match_mop_trial_and_block_counts(
    task_id, trial_count, block_count, trials_per_block
):
    spec = get_task_spec(task_id)

    assert spec.trial_count == trial_count
    assert spec.block_count == block_count
    assert spec.trials_per_block == trials_per_block
    assert sum(spec.trials_per_block) == spec.trial_count


@pytest.mark.parametrize(
    ("task_id", "trial_type_counts"),
    [
        ("activity-monitoring", {"static-image": 8, "dynamic-video": 8}),
        ("social-interactive", {"parallel-play": 11, "cooperative-play": 11}),
        ("static-social-scenes", {"visual-search": 6, "static-scene": 6}),
        ("pupillary-light-reflex", {"light-flash": 18}),
    ],
)
def test_specs_match_published_condition_counts(task_id, trial_type_counts):
    spec = get_task_spec(task_id)

    assert {trial_type.name: trial_type.trial_count for trial_type in spec.trial_types} == (
        trial_type_counts
    )
    assert spec.specified_trial_count == spec.trial_count


@pytest.mark.parametrize(
    ("task_id", "trial_seconds", "approximate_duration_seconds"),
    [
        ("activity-monitoring", 240, 300),
        ("social-interactive", 330, 300),
        ("static-social-scenes", 192, 180),
        ("pupillary-light-reflex", 108, 120),
    ],
)
def test_specs_capture_trial_timing_and_mop_approximate_duration(
    task_id, trial_seconds, approximate_duration_seconds
):
    spec = get_task_spec(task_id)

    assert spec.specified_trial_seconds == trial_seconds
    assert spec.approximate_duration_seconds == approximate_duration_seconds


def test_unknown_task_spec_raises_clear_error():
    with pytest.raises(ValueError, match="Unknown task spec: unknown"):
        get_task_spec("unknown")
