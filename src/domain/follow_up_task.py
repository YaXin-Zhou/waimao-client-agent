"""来自真实来信分析的人工跟进待办。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4


class FollowUpStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class FollowUpTask:
    id: str
    task_id: str
    lead_domain: str
    message_id: str
    title: str
    description: str
    status: FollowUpStatus = FollowUpStatus.OPEN
    created_at: str = ""
    completed_at: str = ""

    @classmethod
    def create(cls, task_id, lead_domain, message_id, title, description):
        if not task_id or not lead_domain or not message_id:
            raise ValueError("follow-up task identity is required")
        if not title.strip() or not description.strip():
            raise ValueError("follow-up task content is required")
        return cls(
            id=str(uuid4()), task_id=task_id, lead_domain=lead_domain,
            message_id=message_id, title=title.strip(), description=description.strip(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def change_status(self, status: FollowUpStatus) -> "FollowUpTask":
        if status is self.status:
            return self
        completed_at = (
            datetime.now(timezone.utc).isoformat()
            if status is FollowUpStatus.COMPLETED
            else self.completed_at
        )
        return replace(self, status=status, completed_at=completed_at)
