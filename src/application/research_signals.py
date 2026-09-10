"""把受约束背调结果转换为评分引擎使用的信号。"""

from __future__ import annotations

import re

from src.domain.lead import CleanLead
from src.domain.research import EvidenceStatus, ResearchResult
from src.domain.task import AcquisitionCriteria, configured_product_evidence_terms


def _matches(left: str, right: str) -> bool:
    left_tokens = {token.rstrip("s") for token in re.findall(r"[a-z0-9]+", left.lower())}
    right_tokens = {token.rstrip("s") for token in re.findall(r"[a-z0-9]+", right.lower())}
    return bool(
        left_tokens
        and right_tokens
        and (left_tokens <= right_tokens or right_tokens <= left_tokens)
    )


def build_research_signals(
    lead: CleanLead, research: ResearchResult, criteria: AcquisitionCriteria
) -> dict[str, int]:
    product_terms = configured_product_evidence_terms(criteria)
    product_match = (
        30
        if any(_matches(term, product) for term in product_terms for product in research.products)
        else 0
    )
    market_match = (
        20 if any(_matches(country, research.country) for country in criteria.countries) else 0
    )
    email_quality = 15 if lead.emails else 0
    evidence_quality = 5 if research.evidence_status is EvidenceStatus.SUFFICIENT else 0
    signals = {
        "product_match": product_match,
        "market_match": market_match,
        "buying_signal": 0,
        "email_quality": email_quality,
        "company_size": 0,
        "evidence_quality": evidence_quality,
    }
    if criteria.business_offerings:
        searchable_text = " ".join(
            [research.business_summary, *research.products]
            + [field.value for field in research.custom_fields.values()]
        )
        offering_match = any(
            _matches(term, searchable_text)
            for offering in criteria.business_offerings
            for term in (offering.name, *offering.keywords)
        )
        signals["configured_service_match"] = 30 if offering_match else 0
    return signals
