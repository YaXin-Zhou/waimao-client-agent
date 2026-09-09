from src.application.research_signals import build_research_signals
from src.domain.custom_research import BusinessOffering, ResearchFieldValue
from src.domain.lead import CleanLead
from src.domain.research import CustomerType, EvidenceStatus, ResearchResult
from src.domain.task import AcquisitionCriteria


def test_research_signals_are_deterministic_and_bounded_by_configured_weights():
    lead = CleanLead("Alpine", "alpine.example", ("sales@alpine.example",), "Germany", "complete")
    research = ResearchResult(
        company_name="Alpine",
        business_summary="Distributor of portable power stations.",
        customer_type=CustomerType.DISTRIBUTOR,
        products=("portable power stations",),
        country="Germany",
        confidence=0.9,
        evidence_url="https://alpine.example/about",
        evidence_status=EvidenceStatus.SUFFICIENT,
    )
    criteria = AcquisitionCriteria(
        product="portable power station",
        countries=("Germany",),
        customer_types=("distributor",),
    )

    signals = build_research_signals(lead, research, criteria)

    assert signals == {
        "product_match": 30,
        "market_match": 20,
        "buying_signal": 0,
        "email_quality": 15,
        "company_size": 0,
        "evidence_quality": 5,
    }


def test_configured_business_offerings_create_a_relevance_signal_from_research_text():
    lead = CleanLead("Alpine", "alpine.example", (), "Germany", "needs_review")
    research = ResearchResult(
        "Alpine", "Manufacturer sourcing precision parts", CustomerType.MANUFACTURER,
        ("industrial components",), "Germany", 0.8, "https://alpine.example/about",
        EvidenceStatus.SUFFICIENT,
        custom_fields={"purchase_need": ResearchFieldValue("CNC machining", "verified", 0.9)},
    )
    criteria = AcquisitionCriteria(
        "configured services",
        business_offerings=(BusinessOffering("CNC machining", "cnc", keywords=("CNC",)),),
    )

    signals = build_research_signals(lead, research, criteria)

    assert signals["configured_service_match"] == 30
