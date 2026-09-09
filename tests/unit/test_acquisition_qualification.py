from src.application.acquisition_service import AcquisitionService, AssessedLead
from src.domain.custom_research import BusinessOffering
from src.domain.lead import LeadRecord, LeadScore, clean_leads
from src.domain.task import AcquisitionCriteria


def assessed(*records, score=80):
    lead = clean_leads(list(records))[0]
    return AssessedLead(lead, LeadScore(score, "A", {"evidence": score}))


def test_qualification_rejects_candidate_without_public_email_even_with_high_score():
    criteria = AcquisitionCriteria(product="CNC machining")
    result = AcquisitionService._qualify(
        [
            assessed(
                LeadRecord(
                    "Alpine Manufacturing",
                    "https://alpine.example",
                    source_url="https://alpine.example/products",
                    source_excerpt="Alpine Manufacturing provides CNC machining.",
                )
            )
        ],
        criteria,
    )[0]

    assert result.qualified is False
    assert "missing_public_email" in result.rejection_reasons


def test_qualification_rejects_search_only_email_without_website_evidence():
    criteria = AcquisitionCriteria(product="CNC machining")
    result = AcquisitionService._qualify(
        [
            assessed(
                LeadRecord(
                    "Alpine Manufacturing",
                    "https://alpine.example",
                    "sales@alpine.example",
                    source_url="https://www.google.com/search?q=alpine",
                    source_excerpt="Alpine Manufacturing official result",
                )
            )
        ],
        criteria,
    )[0]

    assert result.qualified is False
    assert "missing_website_evidence" in result.rejection_reasons
    assert "missing_product_evidence" in result.rejection_reasons


def test_qualification_accepts_email_and_configured_product_evidence_from_same_domain():
    criteria = AcquisitionCriteria(
        product="CNC machining",
        business_offerings=(
            BusinessOffering(
                "Precision parts",
                "precision_parts",
                keywords=("CNC machining",),
            ),
        ),
    )
    result = AcquisitionService._qualify(
        [
            assessed(
                LeadRecord(
                    "Alpine Manufacturing",
                    "https://alpine.example",
                    "sales@alpine.example",
                    source_url="https://alpine.example/products",
                    source_excerpt="Alpine Manufacturing provides CNC machining.",
                )
            )
        ],
        criteria,
    )[0]

    assert result.qualified is True
    assert result.rejection_reasons == ()
