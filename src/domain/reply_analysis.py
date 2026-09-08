"""来信分类和安全跟进建议。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import uuid4


class ReplyCategory(StrEnum):
    INTERESTED = "interested"
    PRICING = "pricing"
    DELIVERY = "delivery"
    COMPLAINT = "complaint"
    BOUNCE = "bounce"
    NOT_INTERESTED = "not_interested"
    OTHER = "other"


@dataclass(frozen=True)
class ReplyAnalysis:
    id: str
    message_id: str
    task_id: str
    lead_domain: str
    category: ReplyCategory
    confidence: float
    risk_level: str
    suggested_action: str
    needs_human_review: bool
    evidence: tuple[str, ...] = ()

    @classmethod
    def create(
        cls, message_id, task_id, lead_domain, category, confidence,
        risk_level, suggested_action, needs_human_review, evidence=(),
    ) -> "ReplyAnalysis":
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return cls(
            str(uuid4()), message_id, task_id, lead_domain, category,
            confidence, risk_level, suggested_action, needs_human_review, evidence,
        )
