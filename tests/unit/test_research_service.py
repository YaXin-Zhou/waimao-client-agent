import pytest

from src.application.research_service import research_company
from src.domain.custom_research import ResearchFieldDefinition
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


def test_research_company_maps_online_shop_language_to_retailer():
    provider = FakeStructuredProvider(
        {
            "business_summary": "Online shop for solar equipment.",
            "customer_type": "online shop / e-commerce",
            "products": ["solar generators"],
            "country": "Germany",
            "confidence": 0.8,
        }
    )
    lead = CleanLead("Shop", "shop.example", (), "Germany", "complete")

    result = research_company(
        provider,
        lead,
        "https://shop.example",
        "A sufficiently long source text for review.",
    )

    assert result.customer_type is CustomerType.RETAILER


def test_research_company_keeps_only_allowed_multi_source_urls_for_custom_fields():
    provider = FakeStructuredProvider(
        {
            "business_summary": "Manufacturer of precision parts.",
            "customer_type": "manufacturer",
            "products": ["precision parts"],
            "country": "Germany",
            "confidence": 0.8,
            "custom_fields": {
                "buyer_role": {
                    "value": "Sourcing Manager",
                    "status": "verified",
                    "confidence": 0.8,
                    "sources": ["https://alpine.example/team", "https://untrusted.example"],
                    "checked_at": "2026-09-09",
                }
            },
        }
    )
    field = ResearchFieldDefinition("Buyer role", "buyer_role", keywords=("sourcing",))

    result = research_company(
        provider,
        CleanLead("Alpine", "alpine.example", (), "Germany", "needs_review"),
        "https://alpine.example/about",
        "About Alpine. The team includes a Sourcing Manager.",
        (field,),
        ("https://alpine.example/about", "https://alpine.example/team"),
    )

    assert result.evidence_urls == ("https://alpine.example/about", "https://alpine.example/team")
    assert result.custom_fields["buyer_role"].sources == ("https://alpine.example/team",)
    assert "https://untrusted.example" not in provider.prompt


def test_research_company_marks_conflicting_source_candidates_for_review():
    provider = FakeStructuredProvider(
        {
            "business_summary": "Manufacturer of precision parts.",
            "customer_type": "manufacturer",
            "products": ["precision parts"],
            "country": "Germany",
            "confidence": 0.8,
            "custom_fields": {
                "buyer_role": {
                    "value": "Sourcing Manager",
                    "status": "verified",
                    "confidence": 0.8,
                    "candidates": [
                        {"value": "Sourcing Manager", "source": "https://alpine.example/team"},
                        {
                            "value": "Purchasing Director",
                            "source": "https://alpine.example/contact",
                        },
                    ],
                }
            },
        }
    )
    field = ResearchFieldDefinition("Buyer role", "buyer_role")

    result = research_company(
        provider,
        CleanLead("Alpine", "alpine.example", (), "Germany", "needs_review"),
        "https://alpine.example/about",
        "About Alpine. The team and contact pages provide buyer information.",
        (field,),
        (
            "https://alpine.example/about",
            "https://alpine.example/team",
            "https://alpine.example/contact",
        ),
    )

    value = result.custom_fields["buyer_role"]
    assert value.status == "conflicting"
    assert value.confidence == 0
    assert value.value == "Sourcing Manager / Purchasing Director"
    assert value.sources == (
        "https://alpine.example/team",
        "https://alpine.example/contact",
    )


def test_research_company_marks_country_conflict_between_lead_and_website():
    provider = FakeStructuredProvider(
        {
            "business_summary": "Retailer of portable power equipment.",
            "customer_type": "retailer",
            "products": ["portable power stations"],
            "country": "Austria",
            "confidence": 0.9,
        }
    )

    result = research_company(
        provider,
        CleanLead("ELMAG", "elmag.eu", (), "Germany", "needs_review"),
        "https://www.elmag.eu/products",
        "ELMAG is based in Austria and sells portable power stations internationally.",
    )

    assert result.country == "Austria"
    assert result.country_conflict is True
    assert result.evidence_status is EvidenceStatus.INSUFFICIENT


def test_research_company_requires_evidence_for_required_custom_fields():
    provider = FakeStructuredProvider(
        {
            "business_summary": "Manufacturer of precision parts.",
            "customer_type": "manufacturer",
            "products": ["precision parts"],
            "country": "Germany",
            "confidence": 0.9,
            "custom_fields": {
                "buyer_role": {"value": "", "status": "unknown", "sources": []}
            },
        }
    )

    result = research_company(
        provider,
        CleanLead("Alpine", "alpine.example", (), "Germany", "needs_review"),
        "https://alpine.example/about",
        "A sufficiently long source text for the research report.",
        (ResearchFieldDefinition("Buyer role", "buyer_role", required=True),),
        ("https://alpine.example/about",),
    )

    assert result.evidence_status is EvidenceStatus.INSUFFICIENT


def test_research_company_requires_sources_when_configured_for_a_field():
    provider = FakeStructuredProvider(
        {
            "business_summary": "Manufacturer of precision parts.",
            "customer_type": "manufacturer",
            "products": ["precision parts"],
            "country": "Germany",
            "confidence": 0.9,
            "custom_fields": {
                "company_type": {"value": "GmbH", "status": "reported", "sources": []}
            },
        }
    )

    result = research_company(
        provider,
        CleanLead("Alpine", "alpine.example", (), "Germany", "needs_review"),
        "https://alpine.example/about",
        "A sufficiently long source text for the research report.",
        (ResearchFieldDefinition("Company type", "company_type"),),
    )

    assert result.evidence_status is EvidenceStatus.INSUFFICIENT
