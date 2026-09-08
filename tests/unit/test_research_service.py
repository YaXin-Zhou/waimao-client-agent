import pytest

from src.application.research_service import research_company
from src.domain.lead import CleanLead
from src.domain.research import CustomerType, EvidenceStatus


class FakeStructuredProvider:
    def __init__(self, result):
        self.result = result
        self.prompt = ""

    def generate_json(self, prompt):
        self.prompt = prompt
        return self.result


def test_research_company_returns_structured_result_with_source_evidence():
    provider = FakeStructuredProvider(
        {
            "business_summary": "Distributor of outdoor power equipment.",
            "customer_type": "distributor",
            "products": ["portable power stations"],
            "country": "Germany",
            "confidence": 0.86,
        }
    )
    lead = CleanLead(
        "Alpine Camp Supply",
        "alpine.example",
        ("sales@alpine.example",),
        "Germany",
        "complete",
    )

    result = research_company(
        provider,
        lead,
        source_url="https://alpine.example/about",
        website_text="Alpine Camp Supply distributes outdoor power equipment in Germany.",
    )

    assert result.company_name == "Alpine Camp Supply"
    assert result.customer_type is CustomerType.DISTRIBUTOR
    assert result.confidence == 0.86
    assert result.evidence_url == "https://alpine.example/about"
    assert result.evidence_status is EvidenceStatus.SUFFICIENT
    assert "Do not invent" in provider.prompt


def test_research_company_rejects_incomplete_model_output():
    provider = FakeStructuredProvider({"business_summary": "Unknown"})
    lead = CleanLead("Unknown", "unknown.example", (), "", "needs_review")

    with pytest.raises(ValueError, match="missing required research field"):
        research_company(provider, lead, "https://unknown.example", "No useful text")


def test_research_company_normalizes_unknown_customer_type_and_weak_evidence():
    provider = FakeStructuredProvider(
        {
            "business_summary": "Short",
            "customer_type": "some unclassified model label",
            "products": [],
            "country": "unknown",
            "confidence": 0.2,
        }
    )
    lead = CleanLead("Unknown", "unknown.example", (), "", "needs_review")

    result = research_company(provider, lead, "https://unknown.example", "Short")

    assert result.customer_type is CustomerType.UNKNOWN
    assert result.evidence_status is EvidenceStatus.INSUFFICIENT
