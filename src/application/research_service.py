"""公司背调用例：使用来源文本生成可校验的结构化结果。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.domain.lead import CleanLead


class StructuredProvider(Protocol):
    def generate_json(self, prompt: str) -> dict: ...


@dataclass(frozen=True)
class ResearchResult:
    company_name: str
    business_summary: str
    customer_type: str
    products: tuple[str, ...]
    country: str
    confidence: float
    evidence_url: str


def research_company(
    provider: StructuredProvider,
    lead: CleanLead,
    source_url: str,
    website_text: str,
) -> ResearchResult:
    if not source_url.strip() or not website_text.strip():
        raise ValueError("source_url and website_text are required")
    prompt = (
        "Analyze the company using only the supplied source text. Do not invent facts. "
        "Return JSON with exactly these fields: business_summary (string), customer_type "
        "(string or unknown), products (array of strings), country (string or unknown), "
        "confidence (number 0 to 1).\n"
        f"Company name: {lead.company_name}\nSource URL: {source_url}\n"
        f"Source text:\n{website_text}"
    )
    data = provider.generate_json(prompt)
    required = ("business_summary", "customer_type", "products", "country", "confidence")
    missing = [field for field in required if field not in data]
    if missing:
        raise ValueError(f"missing required research field: {', '.join(missing)}")
    confidence = float(data["confidence"])
    if not 0 <= confidence <= 1:
        raise ValueError("research confidence must be between 0 and 1")
    products = data["products"]
    if not isinstance(products, list) or not all(isinstance(item, str) for item in products):
        raise ValueError("research products must be a list of strings")
    return ResearchResult(
        company_name=lead.company_name,
        business_summary=str(data["business_summary"]),
        customer_type=str(data["customer_type"]),
        products=tuple(products),
        country=str(data["country"]),
        confidence=confidence,
        evidence_url=source_url,
    )
