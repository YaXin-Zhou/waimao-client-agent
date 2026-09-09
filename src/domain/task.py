"""获客任务配置与状态转换。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import uuid4

from src.domain.custom_research import (
    BusinessOffering,
    ResearchFieldDefinition,
    validate_unique_keys,
)
from src.domain.sender_profile import SenderProfile


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
    language: str = "auto"
    daily_limit: int = 10
    qualified_lead_limit: int = 10
    minimum_qualification_score: int = 40
    require_public_email: bool = True
    # 搜索候选上限；未配置时沿用 daily_limit，接口层可显式扩大候选池。
    candidate_limit: int | None = None
    keywords: tuple[str, ...] = ()
    business_offerings: tuple[BusinessOffering, ...] = ()
    research_fields: tuple[ResearchFieldDefinition, ...] = ()

    def __post_init__(self) -> None:
        if not self.product.strip():
            raise ValueError("product is required")
        if self.daily_limit <= 0:
            raise ValueError("daily_limit must be positive")
        if self.qualified_lead_limit <= 0:
            raise ValueError("qualified_lead_limit must be positive")
        if self.minimum_qualification_score < 0:
            raise ValueError("minimum_qualification_score must not be negative")
        if self.candidate_limit is not None and self.candidate_limit < self.qualified_lead_limit:
            raise ValueError("candidate_limit must cover qualified_lead_limit")
        validate_unique_keys(self.business_offerings)
        validate_unique_keys(self.research_fields)


@dataclass(frozen=True)
class AcquisitionTask:
    id: str
    name: str
    criteria: AcquisitionCriteria
    status: TaskStatus = TaskStatus.DRAFT
    sender_profile: SenderProfile = SenderProfile()

    @classmethod
    def create(
        cls,
        name: str,
        criteria: AcquisitionCriteria,
        sender_profile: SenderProfile | None = None,
    ) -> "AcquisitionTask":
        if not name.strip():
            raise ValueError("task name is required")
        return cls(
            id=str(uuid4()),
            name=name.strip(),
            criteria=criteria,
            sender_profile=sender_profile or SenderProfile(),
        )

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
