"""跟进待办用例，负责幂等创建和人工状态更新。"""

from __future__ import annotations

from src.domain.follow_up_task import FollowUpStatus


class FollowUpTaskService:
    def __init__(self, repository):
        self._repository = repository

    def create_for_analysis(self, analysis):
        if analysis.category.value == "not_interested":
            return None
        existing = self._repository.get_by_message_id(analysis.message_id)
        if existing is not None:
            return existing
        return self._repository.save_new(
            analysis.task_id,
            analysis.lead_domain,
            analysis.message_id,
            _title(analysis),
            analysis.suggested_action,
        )

    def list_for_task(self, task_id):
        return self._repository.list_for_task(task_id)

    def change_status(self, task_id, follow_up_id, status):
        item = self._repository.get(follow_up_id)
        if item is None or item.task_id != task_id:
            raise KeyError(f"Follow-up task not found: {follow_up_id}")
        return self._repository.save(item.change_status(FollowUpStatus(status)))


def _title(analysis):
    labels = {
        "interested": "跟进客户兴趣",
        "pricing": "准备报价信息",
        "delivery": "确认交期与物流",
        "complaint": "人工处理客户投诉",
        "bounce": "检查退信并处理地址",
        "other": "人工阅读来信并决定下一步",
    }
    return labels.get(analysis.category.value, "人工跟进客户")
