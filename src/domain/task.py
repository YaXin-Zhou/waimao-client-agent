"""获客任务配置与状态转换。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import uuid4


class TaskStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass(frozen=True)
class AcquisitionCriteria:
    """由用户填写或选择的获客条件，不包含行业固定规则。"""

    product: str
    countries: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    customer_types: tuple[str, ...] = ()
    language: str = "English"
    daily_limit: int = 10

    def __post_init__(self) -> None:
        if not self.product.strip():
            raise ValueError("product is required")
        if self.daily_limit <= 0:
            raise ValueError("daily_limit must be positive")


@dataclass(frozen=True)
class AcquisitionTask:
    id: str
    name: str
    criteria: AcquisitionCriteria
    status: TaskStatus = TaskStatus.DRAFT

    @classmethod
    def create(cls, name: str, criteria: AcquisitionCriteria) -> "AcquisitionTask":
        if not name.strip():
            raise ValueError("task name is required")
        return cls(id=str(uuid4()), name=name.strip(), criteria=criteria)

    def transition_to(self, target: TaskStatus) -> "AcquisitionTask":
        allowed = {
            TaskStatus.DRAFT: {TaskStatus.READY},
            TaskStatus.READY: {TaskStatus.RUNNING},
            TaskStatus.RUNNING: {
                TaskStatus.WAITING_REVIEW,
                TaskStatus.PAUSED,
                TaskStatus.FAILED,
                TaskStatus.COMPLETED,
            },
            TaskStatus.WAITING_REVIEW: {TaskStatus.RUNNING, TaskStatus.PAUSED},
            TaskStatus.PAUSED: {TaskStatus.READY, TaskStatus.RUNNING},
            TaskStatus.FAILED: {TaskStatus.READY, TaskStatus.RUNNING},
            TaskStatus.COMPLETED: set(),
        }
        if target not in allowed[self.status]:
            raise ValueError(f"Invalid task transition: {self.status} -> {target}")
        return replace(self, status=target)
