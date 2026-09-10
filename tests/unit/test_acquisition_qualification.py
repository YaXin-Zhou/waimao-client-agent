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


def test_qualification_rejects_unknown_country_when_targets_are_configured():
    criteria = AcquisitionCriteria(product="CNC machining", countries=("德国", "美国", "英国"))
    result = AcquisitionService._qualify(
        [
            assessed(
                LeadRecord(
                    "Unknown Country Parts",
                    "https://unknown.example",
                    "info@unknown.example",
                    country="",
                    source_url="https://unknown.example/products",
                    source_excerpt="Unknown Country Parts provides CNC machining.",
                )
            )
        ],
        criteria,
    )[0]

    assert result.qualified is False
    assert "country_unconfirmed" in result.rejection_reasons


def test_qualification_rejects_known_country_outside_target_markets():
    criteria = AcquisitionCriteria(product="CNC machining", countries=("德国", "美国", "英国"))
    result = AcquisitionService._qualify(
        [
            assessed(
                LeadRecord(
                    "China Precision Parts",
                    "https://china-parts.example",
                    "sales@china-parts.example",
                    country="China",
                    source_url="https://china-parts.example/products",
                    source_excerpt="China Precision Parts provides CNC machining.",
                )
            )
        ],
        criteria,
    )[0]

    assert result.qualified is False
    assert "country_not_target" in result.rejection_reasons


def test_qualification_rejects_cross_domain_email_even_when_site_has_product_text():
    criteria = AcquisitionCriteria(product="CNC machining", countries=("德国",))
    result = AcquisitionService._qualify(
        [
            assessed(
                LeadRecord(
                    "German Precision Parts",
                    "https://german-parts.example",
                    "info@other-company.example",
                    country="DE",
                    source_url="https://german-parts.example/products",
                    source_excerpt="German Precision Parts provides CNC machining.",
                )
            )
        ],
        criteria,
    )[0]

    assert result.qualified is False
    assert "email_domain_mismatch" in result.rejection_reasons


def test_qualification_rejects_weak_company_identity_instead_of_sending_a_title():
    criteria = AcquisitionCriteria(product="CNC machining", countries=("德国",))
    result = AcquisitionService._qualify(
        [
            assessed(
                LeadRecord(
                    "Top CNC Machining Manufacturers in Germany",
                    "https://directory.example",
                    "sales@directory.example",
                    country="DE",
                    source_url="https://directory.example/list",
                    source_excerpt="Top CNC Machining Manufacturers in Germany",
                )
            )
        ],
        criteria,
    )[0]

    assert result.qualified is False
    assert "company_identity_unconfirmed" in result.rejection_reasons


def test_qualification_normalizes_country_names_and_abbreviations():
    criteria = AcquisitionCriteria(product="CNC machining", countries=("德国", "美国", "英国"))
    result = AcquisitionService._qualify(
        [
            assessed(
                LeadRecord(
                    "German Precision Parts",
                    "https://german-parts.example",
                    "sales@german-parts.example",
                    country="DE",
                    source_url="https://german-parts.example/products",
                    source_excerpt="German Precision Parts provides CNC machining.",
                )
            )
        ],
        criteria,
    )[0]

    assert result.qualified is True


def test_qualification_matches_french_and_italian_targets_after_country_inference():
    criteria = AcquisitionCriteria(product="CNC machining", countries=("法国", "意大利"))
    result = AcquisitionService._qualify(
        [
            assessed(
                LeadRecord(
                    "French Precision Parts",
                    "https://precision-parts.fr",
                    "sales@precision-parts.fr",
                    source_url="https://precision-parts.fr/products",
                    source_excerpt="French Precision Parts provides CNC machining.",
                )
            )
        ],
        criteria,
    )[0]

    assert result.lead.country == "France"
    assert result.qualified is True
