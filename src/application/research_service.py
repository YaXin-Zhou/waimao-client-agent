"""公司背调用例：使用来源文本生成可校验的结构化结果。"""

from __future__ import annotations

from typing import Protocol

from src.domain.custom_research import ResearchFieldDefinition, ResearchFieldValue
from src.domain.lead import CleanLead
from src.domain.research import CustomerType, EvidenceStatus, ResearchResult


class StructuredProvider(Protocol):
    def generate_json(self, prompt: str) -> dict: ...


def _customer_type(value: object) -> CustomerType:
    label = str(value).strip().lower()
    if any(alias in label for alias in ("online shop", "e-commerce", "ecommerce", "b2c", "retail")):
        return CustomerType.RETAILER
    if any(alias in label for alias in ("b2b distributor", "dealer", "reseller")):
        return CustomerType.DISTRIBUTOR
    for customer_type in CustomerType:
        if customer_type is not CustomerType.UNKNOWN and customer_type.value in label:
            return customer_type
    return CustomerType.UNKNOWN


def _custom_field_value(
    raw: dict,
    allowed_sources: tuple[str, ...],
) -> ResearchFieldValue:
    """Normalize one model field and force review when cited values disagree."""
    allowed = set(allowed_sources)
    candidates = raw.get("candidates", [])
    if isinstance(candidates, list):
        parsed = [
            item
            for item in candidates
            if isinstance(item, dict)
            and str(item.get("value", "")).strip()
            and str(item.get("source", "")) in allowed
        ]
        values = list(dict.fromkeys(str(item["value"]).strip() for item in parsed))
        if len(values) > 1:
            return ResearchFieldValue(
                value=" / ".join(values),
                status="conflicting",
                confidence=0.0,
                sources=tuple(dict.fromkeys(str(item["source"]) for item in parsed)),
                checked_at=str(raw.get("checked_at", "")),
            )

    return ResearchFieldValue(
        value=str(raw.get("value", "")),
        status=str(raw.get("status", "unknown")),
        confidence=float(raw.get("confidence", 0)),
        sources=tuple(str(item) for item in raw.get("sources", []) if str(item) in allowed),
        checked_at=str(raw.get("checked_at", "")),
    )


def research_company(
    provider: StructuredProvider,
    lead: CleanLead,
    source_url: str,
    website_text: str,
    field_definitions: tuple[ResearchFieldDefinition, ...] = (),
    source_urls: tuple[str, ...] = (),
) -> ResearchResult:
    if not source_url.strip() or not website_text.strip():
        raise ValueError("source_url and website_text are required")
    custom_instruction = ""
    if field_definitions:
        fields = ", ".join(
            f"{field.key}: {field.name} "
            f"({field.description or 'no extra description'}; "
            f"keywords={list(field.keywords)})"
            for field in field_definitions
        )
        custom_instruction = (
            f" Also return custom_fields as an object with exactly these keys: {fields}. "
            "Each value must be an object with value, status (verified, reported, unknown, "
            "or conflicting), confidence, sources (array of URLs), and checked_at. "
            "When allowed sources disagree, also return candidates as an array of objects "
            "with value and source; do not silently choose one value. "
            "Use unknown and empty sources when the supplied text does not support a fact."
        )
    normalized_sources = tuple(
        dict.fromkeys(url.strip() for url in source_urls if url.strip())
    ) or (source_url.strip(),)
    source_catalog = "\n".join(f"- {url}" for url in normalized_sources)
    prompt = (
        "Analyze the company using only the supplied source text. Do not invent facts. "
        "For every custom field, cite only URLs from the supplied source list.\n"
        "Return JSON with exactly these fields: business_summary (string), customer_type "
        "(one of distributor, wholesaler, retailer, manufacturer, consumer, "
        "service_provider, unknown), products (array of strings), country (string or unknown), "
        "confidence (number 0 to 1), website_language (English, Spanish, Russian, "
        f"German, French, Italian, Portuguese, Chinese, or unknown).{custom_instruction}\n"
        f"Company name: {lead.company_name}\nSource list:\n{source_catalog}\n"
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
    custom_fields = {}
    raw_custom_fields = data.get("custom_fields", {})
    if not isinstance(raw_custom_fields, dict):
        raise ValueError("research custom_fields must be an object")
    for field in field_definitions:
        raw = raw_custom_fields.get(field.key, {})
        if not isinstance(raw, dict):
            raise ValueError(f"research custom field must be an object: {field.key}")
        custom_fields[field.key] = _custom_field_value(raw, normalized_sources)
    reported_country = str(data["country"]).strip()
    country_conflict = bool(
        lead.country.strip()
        and reported_country
        and reported_country.lower() not in {"unknown", "n/a", "not found"}
        and reported_country.casefold() != lead.country.strip().casefold()
    )
    return ResearchResult(
        company_name=lead.company_name,
        business_summary=str(data["business_summary"]),
        customer_type=_customer_type(data["customer_type"]),
        products=tuple(products),
        country=reported_country,
        confidence=confidence,
        evidence_url=source_url,
        evidence_status=(
            EvidenceStatus.SUFFICIENT
            if len(website_text.strip()) >= 40 and confidence >= 0.5 and not country_conflict
            else EvidenceStatus.INSUFFICIENT
        ),
        website_language=str(data.get("website_language", "unknown")),
        custom_fields=custom_fields,
        evidence_urls=normalized_sources,
        country_conflict=country_conflict,
    )
