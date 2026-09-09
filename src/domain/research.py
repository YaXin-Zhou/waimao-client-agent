"""公司背调结果的受约束领域模型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.domain.custom_research import ResearchFieldValue


class CustomerType(StrEnum):
    DISTRIBUTOR = "distributor"
    WHOLESALER = "wholesaler"
    RETAILER = "retailer"
    MANUFACTURER = "manufacturer"
    CONSUMER = "consumer"
    SERVICE_PROVIDER = "service_provider"
    UNKNOWN = "unknown"


class EvidenceStatus(StrEnum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class ResearchResult:
    company_name: str
    business_summary: str
    customer_type: CustomerType
    products: tuple[str, ...]
    country: str
    confidence: float
    evidence_url: str
    evidence_status: EvidenceStatus
    website_language: str = "unknown"
    custom_fields: dict[str, ResearchFieldValue] | None = None
    evidence_urls: tuple[str, ...] = ()
    country_conflict: bool = False

    def __post_init__(self) -> None:
        if self.custom_fields is None:
            object.__setattr__(self, "custom_fields", {})
        if not self.evidence_urls and self.evidence_url.strip():
            object.__setattr__(self, "evidence_urls", (self.evidence_url,))
