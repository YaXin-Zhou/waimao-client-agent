import pytest

from src.domain.task import AcquisitionCriteria, AcquisitionTask, TaskStatus


def test_task_keeps_business_criteria_configurable():
    criteria = AcquisitionCriteria(
        product="portable power station",
        countries=("Germany", "France"),
        industries=("outdoor distributor",),
        customer_types=("wholesaler",),
        language="English",
        daily_limit=25,
    )

    task = AcquisitionTask.create("EU outdoor leads", criteria)

    assert task.status is TaskStatus.DRAFT
    assert task.criteria.product == "portable power station"
    assert task.criteria.countries == ("Germany", "France")
    assert task.criteria.daily_limit == 25


def test_task_moves_through_allowed_states():
    task = AcquisitionTask.create("Test task", AcquisitionCriteria(product="solar lamp"))

    task = task.transition_to(TaskStatus.READY)
    task = task.transition_to(TaskStatus.RUNNING)
    task = task.transition_to(TaskStatus.WAITING_REVIEW)

    assert task.status is TaskStatus.WAITING_REVIEW


def test_task_rejects_invalid_state_transition():
    task = AcquisitionTask.create("Test task", AcquisitionCriteria(product="solar lamp"))

    with pytest.raises(ValueError, match="Invalid task transition"):
        task.transition_to(TaskStatus.COMPLETED)
