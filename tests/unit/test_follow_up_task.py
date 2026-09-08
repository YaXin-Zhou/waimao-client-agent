import pytest

from src.application.follow_up_task_service import FollowUpTaskService
from src.domain.follow_up_task import FollowUpStatus
from src.domain.reply_analysis import ReplyAnalysis, ReplyCategory


class Repository:
    def __init__(self):
        self.items = {}

    def save_new(self, task_id, lead_domain, message_id, title, description):
        from src.domain.follow_up_task import FollowUpTask
        item = FollowUpTask.create(task_id, lead_domain, message_id, title, description)
        self.items[item.id] = item
        return item

    def save(self, item):
        self.items[item.id] = item
        return item

    def get_by_message_id(self, message_id):
        return next((item for item in self.items.values() if item.message_id == message_id), None)

    def get(self, item_id):
        return self.items.get(item_id)

    def list_for_task(self, task_id):
        return [item for item in self.items.values() if item.task_id == task_id]


def analysis(category=ReplyCategory.PRICING):
    return ReplyAnalysis.create(
        "<message@example>", "task-1", "example.com", category, 0.9,
        "medium", "准备报价信息供人工确认", False, ("price",),
    )


def test_follow_up_creation_is_idempotent_and_status_is_human_controlled():
    repository = Repository()
    service = FollowUpTaskService(repository)

    first = service.create_for_analysis(analysis())
    second = service.create_for_analysis(analysis())

    assert first.id == second.id
    updated = service.change_status("task-1", first.id, FollowUpStatus.IN_PROGRESS.value)
    assert updated.status is FollowUpStatus.IN_PROGRESS
    completed = service.change_status("task-1", first.id, FollowUpStatus.COMPLETED.value)
    assert completed.completed_at


def test_rejected_reply_does_not_create_follow_up_task():
    repository = Repository()
    service = FollowUpTaskService(repository)

    assert service.create_for_analysis(analysis(ReplyCategory.NOT_INTERESTED)) is None
    assert repository.items == {}


def test_status_update_cannot_cross_task_boundary():
    repository = Repository()
    service = FollowUpTaskService(repository)
    item = service.create_for_analysis(analysis())

    with pytest.raises(KeyError):
        service.change_status("other-task", item.id, FollowUpStatus.COMPLETED.value)
