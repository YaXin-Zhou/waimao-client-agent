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


def normalize_criteria_values(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Normalize multi-value criteria, including legacy slash-separated input."""
    normalized: list[str] = []
    for value in values:
        parts = (
            str(value)
            .replace("，", ",")
            .replace("、", ",")
            .replace("；", ",")
            .replace(";", ",")
            .replace("|", ",")
            .replace("/", ",")
            .split(",")
        )
        for part in parts:
            item = part.strip()
            if item and item not in normalized:
                normalized.append(item)
    return tuple(normalized)


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

    product: str = ""
    countries: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    customer_types: tuple[str, ...] = ()
    language: str = "auto"
    daily_limit: int = 30
    qualified_lead_limit: int = 30
    minimum_qualification_score: int = 40
    require_public_email: bool = True
    # 搜索候选上限；未配置时沿用 daily_limit，接口层可显式扩大候选池。
    candidate_limit: int | None = None
    keywords: tuple[str, ...] = ()
    business_offerings: tuple[BusinessOffering, ...] = ()
    research_fields: tuple[ResearchFieldDefinition, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "countries", normalize_criteria_values(self.countries))
        object.__setattr__(self, "industries", normalize_criteria_values(self.industries))
        object.__setattr__(self, "customer_types", normalize_criteria_values(self.customer_types))
        object.__setattr__(self, "keywords", normalize_criteria_values(self.keywords))
        if not configured_research_terms(self):
            raise ValueError("at least one product, keyword, or business offering term is required")
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


def configured_research_terms(criteria: AcquisitionCriteria) -> tuple[str, ...]:
    """Return user-provided terms used for discovery and evidence matching."""
    values: list[str] = [criteria.product, *criteria.keywords]
    for offering in criteria.business_offerings:
        values.extend((offering.name, *offering.keywords))
    return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


def configured_product_evidence_terms(criteria: AcquisitionCriteria) -> tuple[str, ...]:
    """Return only terms that can prove the configured product or service.

    Search-intent keywords such as ``manufacturer`` and ``supplier`` help find
    websites but are too generic to prove that a buyer needs the product.
    """
    values: list[str] = [criteria.product]
    for offering in criteria.business_offerings:
        values.extend((offering.name, *offering.keywords))
    terms = tuple(dict.fromkeys(value.strip() for value in values if value.strip()))
    generic_intent = {
        "manufacturer", "supplier", "factory", "distributor", "purchaser",
        "purchasing", "procurement", "buyer", "buyers", "importer", "wholesaler",
    }
    keyword_terms = tuple(
        value.strip()
        for value in criteria.keywords
        if value.strip() and value.strip().casefold() not in generic_intent
    )
    # Tasks may intentionally use only keywords, so retain product-like
    # keywords when no product/offering was configured at all.
    return tuple(dict.fromkeys((*terms, *keyword_terms)))


def effective_candidate_limit(criteria: AcquisitionCriteria) -> int:
    """Return the search pool size without confusing it with the send quota.

    A default pool of at least 100 gives the qualification stage enough room
    to discard inaccessible, irrelevant, or unverifiable companies before it
    tries to deliver the daily qualified-lead target. An explicit smaller
    limit remains available for controlled tests or deliberate user choice.
    """
    if criteria.candidate_limit is not None:
        return criteria.candidate_limit
    return max(100, criteria.daily_limit)


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
