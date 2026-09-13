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


def test_qualification_accepts_search_only_email_when_email_is_available():
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

    assert result.qualified is True
    assert "missing_website_evidence" not in result.rejection_reasons


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


def test_qualification_accepts_plausible_industry_use_without_exact_product_phrase():
    criteria = AcquisitionCriteria(
        product="injection molded parts",
        countries=("德国",),
        industries=("汽车",),
    )
    result = AcquisitionService._qualify(
        [
            assessed(
                LeadRecord(
                    "German Automotive Components",
                    "https://german-components.example",
                    "sales@german-components.example",
                    country="Germany",
                    source_url="https://german-components.example/about",
                    source_excerpt="Automotive components manufacturer and OEM production partner.",
                )
            )
        ],
        criteria,
    )[0]

    assert result.qualified is True


def test_qualification_accepts_unknown_country_when_email_is_available():
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

    assert result.qualified is True
    assert "country_unconfirmed" not in result.rejection_reasons


def test_qualification_accepts_country_outside_target_markets_when_email_is_available():
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

    assert result.qualified is True
    assert "country_not_target" not in result.rejection_reasons


def test_qualification_accepts_public_email_even_when_domain_differs():
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

    assert result.qualified is True
    assert "email_domain_mismatch" not in result.rejection_reasons


def test_qualification_accepts_email_when_company_identity_is_weak():
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

    assert result.qualified is True
    assert "company_identity_unconfirmed" not in result.rejection_reasons


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
