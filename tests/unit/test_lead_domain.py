import json
from pathlib import Path

import pytest

from src.domain.lead import (
    LeadRecord,
    LeadStatus,
    canonical_source_url,
    clean_leads,
    clean_company_name,
    evidence_level,
    identity_consistency,
    is_plausible_email,
    score_lead,
    infer_country_from_public_evidence,
)


def test_sample_dataset_produces_clean_records_for_sales_review():
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_leads.json"
    raw_records = json.loads(fixture.read_text(encoding="utf-8"))

    cleaned = clean_leads([LeadRecord(**record) for record in raw_records])

    assert len(cleaned) == 3
    assert cleaned[0].company_name == "Northwind Outdoor Ltd."
    assert cleaned[0].emails == (
        "sales@northwind-outdoor.example",
        "info@northwind-outdoor.example",
    )
    assert cleaned[1].quality == "complete"
    assert cleaned[2].quality == "needs_review"


def test_email_validation_accepts_dotted_business_mailboxes_and_rejects_urls():
    assert is_plausible_email("e.blake@centurymold.com") is True
    assert is_plausible_email("sales@stephensplasticmouldings.co.uk") is True
    assert is_plausible_email("https://centurymold.com/contact") is False
    assert is_plausible_email("hero@2x.png") is False


def test_email_validation_rejects_web_encoding_and_test_addresses():
    assert is_plausible_email("%20me@microplast.fr") is False
    assert is_plausible_email(
        "asuperlongemailadresstocheckreflowonmobile@testingtesting123.com"
    ) is False


def test_country_is_inferred_from_country_code_domain_without_search_title():
    cleaned = clean_leads(
        [
            LeadRecord(
                "French Precision Parts",
                "https://precision-parts.fr",
                "sales@precision-parts.fr",
                source_url="https://www.google.com/search?q=parts",
                source_excerpt="Top manufacturers in France",
            )
        ]
    )

    assert cleaned[0].country == "France"
    assert infer_country_from_public_evidence(
        "precision-parts.fr", cleaned[0].sources
    ) == "France"


def test_generic_domain_needs_explicit_location_context_for_country_inference():
    assert infer_country_from_public_evidence(
        "precision-parts.com",
        (("https://precision-parts.com", "We serve customers in France and Italy."),),
    ) == ""
    assert infer_country_from_public_evidence(
        "precision-parts.com",
        (("https://precision-parts.com/contact", "Registered office: Milan, Italy."),),
    ) == "Italy"


def test_generic_website_can_use_one_consistent_country_code_email_suffix():
    cleaned = clean_leads(
        [
            LeadRecord(
                "Langer Group",
                "https://langer-group.eu",
                "info@langer-group.de",
                source_url="https://langer-group.eu/contact",
                source_excerpt="Plastic injection molding and automotive production.",
            )
        ]
    )

    assert cleaned[0].country == "Germany"


def test_clean_company_name_removes_search_title_prefixes():
    assert clean_company_name(
        "automotiveAutomotive Injection Moulding - Plastic-IT"
    ) == "Automotive Injection Moulding - Plastic-IT"
    assert clean_company_name(
        "pacificparts.nethttps://www.pacificparts.netPACIFIC PARTS"
    ) == "PACIFIC PARTS"
    assert clean_company_name(
        "Top 10 Automotive Plastic Injection Molding Companies", "example.com"
    ) == "example.com"


def test_clean_company_name_replaces_information_page_titles_with_domain():
    assert clean_company_name("Injection - healthencyclopedia.org", "health.example") == "health.example"
    assert clean_company_name("Intramuscular Injection: Sites, Techniques, and Tips", "clinic.example") == "clinic.example"
    assert clean_company_name("Startseite - Otto Werkzeugbau") == "Otto Werkzeugbau"
    assert clean_company_name("Xometry duplicate") == "Xometry"
    assert clean_company_name("加入我们", "zybang.com") == "zybang.com"
    assert clean_company_name("SoundCloud 这款互联网音乐产品做的如何？", "zhihu.com") == "zhihu.com"


def test_clean_company_name_prefers_legal_company_segment_over_marketing_title():
    assert clean_company_name(
        "Top quality plastic products - Geiger Automotive GmbH", "geiger.example"
    ) == "Geiger Automotive GmbH"
    assert clean_company_name(
        "USA Injection Molding - Taking Your Idea From Design to Production",
        "usa-molding.example",
    ) == "usa-molding.example"


def test_clean_leads_preserves_source_evidence_when_merging_records():
    cleaned = clean_leads(
        [
            LeadRecord(
                "Acme Outdoor",
                "https://acme.example",
                "sales@acme.example",
                "DE",
                "https://search.example/acme",
                "Search result snippet",
            ),
            LeadRecord(
                "Acme Outdoor",
                "https://acme.example/contact",
                "info@acme.example",
                "Germany",
                "https://acme.example/contact",
                "Official contact page",
            ),
        ]
    )

    assert cleaned[0].sources == (
        ("https://search.example/acme", "Search result snippet"),
        ("https://acme.example/contact", "Official contact page"),
    )


def test_evidence_level_distinguishes_search_and_website_provenance():
    no_source = clean_leads([LeadRecord("No source")])[0]
    search_only = clean_leads(
        [
            LeadRecord(
                "Search result",
                "https://search.example",
                source_url="https://www.google.com/search?q=x",
                source_excerpt="result",
            )
        ]
    )[0]
    single = clean_leads(
        [
            LeadRecord(
                "Single source",
                "https://single.example",
                source_url="https://single.example/about",
                source_excerpt="About",
            )
        ]
    )[0]
    multiple = clean_leads(
        [
            LeadRecord(
                "Multiple sources",
                "https://multi.example",
                source_url="https://multi.example/about",
                source_excerpt="About",
            ),
            LeadRecord(
                "Multiple sources",
                "https://multi.example/contact",
                source_url="https://multi.example/contact",
                source_excerpt="Contact",
            ),
        ]
    )[0]

    assert evidence_level(no_source) == "none"
    assert evidence_level(search_only) == "search_only"
    assert evidence_level(single) == "single_source"
    assert evidence_level(multiple) == "multi_source"


def test_canonical_source_url_deduplicates_trailing_slash_and_fragment_for_counts():
    assert canonical_source_url("HTTPS://Example.com/about/#team") == (
        "https://example.com/about"
    )
    assert canonical_source_url("https://example.com/about") == (
        "https://example.com/about"
    )


def test_identity_consistency_uses_same_domain_company_and_domain_signals():
    lead = clean_leads(
        [
            LeadRecord(
                "Elmag GmbH",
                "https://elmag.eu",
                source_url="https://elmag.eu/en/home/company",
                source_excerpt="ELMAG GmbH develops power stations and electricity storage.",
            )
        ]
    )[0]

    result = identity_consistency(lead)

    assert result["status"] == "strong"
    assert result["score"] >= 70
    assert "elmag" in result["matched_tokens"]


def test_identity_consistency_does_not_treat_search_only_as_company_evidence():
    lead = clean_leads(
        [
            LeadRecord(
                "Example Buyer",
                "https://example-buyer.test",
                source_url="https://www.google.com/search?q=example+buyer",
                source_excerpt="Example Buyer - official company result",
            )
        ]
    )[0]

    assert identity_consistency(lead)["status"] == "unknown"


def test_clean_leads_normalizes_and_merges_same_company_by_domain():
    records = [
        LeadRecord(
            company_name=" Acme  GmbH ",
            website="https://www.acme.example/about",
            email=" SALES@ACME.EXAMPLE ",
            country="DE",
        ),
        LeadRecord(
            company_name="Acme",
            website="http://acme.example",
            email="info@acme.example",
            country="Germany",
        ),
    ]

    cleaned = clean_leads(records)

    assert len(cleaned) == 1
    assert cleaned[0].company_name == "Acme GmbH"
    assert cleaned[0].domain == "acme.example"
    assert cleaned[0].emails == ("sales@acme.example", "info@acme.example")
    assert cleaned[0].country == "Germany"
    assert cleaned[0].quality == "complete"


def test_clean_leads_marks_missing_evidence_for_manual_review():
    cleaned = clean_leads([LeadRecord(company_name="Unknown Co", website="", email="not-an-email")])

    assert cleaned[0].quality == "needs_review"
    assert "invalid_email" in cleaned[0].flags
    assert "missing_website" in cleaned[0].flags


def test_clean_leads_marks_public_email_on_a_different_domain():
    cleaned = clean_leads(
        [LeadRecord("ELMAG", "https://elmag.eu", "office@elmag.at", "Austria")]
    )

    assert "email_domain_mismatch" in cleaned[0].flags
    assert cleaned[0].quality == "needs_review"


def test_clean_leads_prefers_same_domain_email_for_primary_contact():
    cleaned = clean_leads(
        [
            LeadRecord("ELMAG", "https://elmag.eu", "office@elmag.at", "Austria"),
            LeadRecord("ELMAG", "https://elmag.eu", "sales@elmag.eu", "Austria"),
        ]
    )

    assert cleaned[0].emails == ("sales@elmag.eu", "office@elmag.at")
    assert "email_domain_mismatch" in cleaned[0].flags


def test_clean_leads_prioritizes_business_development_mailboxes():
    cleaned = clean_leads(
        [
            LeadRecord("Alpine", "https://alpine.example", "support@alpine.example", "Germany"),
            LeadRecord("Alpine", "https://alpine.example", "purchasing@alpine.example", "Germany"),
            LeadRecord("Alpine", "https://alpine.example", "info@alpine.example", "Germany"),
        ]
    )

    assert cleaned[0].emails == (
        "purchasing@alpine.example",
        "info@alpine.example",
        "support@alpine.example",
    )


def test_clean_leads_flags_company_name_missing_from_website_evidence():
    cleaned = clean_leads(
        [
            LeadRecord(
                "Unrelated Trading Co",
                "https://acme.example",
                "sales@acme.example",
                source_url="https://acme.example/contact",
                source_excerpt="ACME official contact page.",
            )
        ]
    )

    assert "company_identity_unconfirmed" in cleaned[0].flags
    assert cleaned[0].quality == "needs_review"


def test_clean_leads_accepts_brand_token_in_website_evidence():
    cleaned = clean_leads(
        [
            LeadRecord(
                "Alpine Outdoor",
                "https://alpine.example",
                "sales@alpine.example",
                source_url="https://alpine.example/about",
                source_excerpt="Alpine Outdoor company profile.",
            )
        ]
    )

    assert "company_identity_unconfirmed" not in cleaned[0].flags
    assert cleaned[0].quality == "complete"


def test_clean_leads_rejects_generic_company_words_without_domain_alignment():
    cleaned = clean_leads(
        [
            LeadRecord(
                "Power Solutions",
                "https://acme.example",
                "sales@acme.example",
                source_url="https://acme.example/about",
                source_excerpt="Power systems for industrial teams.",
            )
        ]
    )

    assert "company_identity_unconfirmed" in cleaned[0].flags
    assert cleaned[0].quality == "needs_review"


def test_clean_leads_drops_asset_and_placeholder_only_source_excerpts():
    cleaned = clean_leads(
        [
            LeadRecord(
                "Supplier",
                "https://supplier.example",
                "sales@supplier.example",
                source_url="https://supplier.example",
                source_excerpt="Public sales contact",
            ),
            LeadRecord(
                "Supplier",
                "https://supplier.example",
                source_url="https://supplier.example",
                source_excerpt="hero-banner.png",
            ),
            LeadRecord(
                "Supplier",
                "https://supplier.example",
                source_url="https://supplier.example",
                source_excerpt="contoso@example.com",
            ),
        ]
    )

    assert cleaned[0].sources == (("https://supplier.example", "Public sales contact"),)


def test_clean_leads_normalizes_explicitly_obfuscated_public_email():
    cleaned = clean_leads(
        [
            LeadRecord(
                "GBT GmbH",
                "https://portable-power-stations.com",
                "Info(at)gbt-international.com",
            )
        ]
    )

    assert cleaned[0].emails == ("info@gbt-international.com",)
    assert cleaned[0].quality == "needs_review"


def test_score_lead_uses_configured_weights_and_returns_priority():
    lead = clean_leads(
        [
            LeadRecord(
                company_name="Acme",
                website="https://acme.example",
                email="sales@acme.example",
            )
        ]
    )[0]
    weights = {
        "product_match": 30,
        "market_match": 20,
        "buying_signal": 20,
        "email_quality": 15,
        "company_size": 10,
        "evidence_quality": 5,
    }
    signals = {
        "product_match": 30,
        "market_match": 20,
        "buying_signal": 10,
        "email_quality": 15,
        "company_size": 5,
        "evidence_quality": 5,
    }
    score = score_lead(lead, weights, signals)

    assert score.total == 85
    assert score.priority == "A"
    assert score.breakdown["buying_signal"] == 10


def test_lead_status_transition_is_explicit_and_rejects_skipping_review():
    lead = clean_leads([
        LeadRecord("Alpine", "https://alpine.example", "sales@alpine.example", "DE")
    ])[0]

    ready = lead.transition_to(LeadStatus.AWAITING_SCORE)

    assert ready.status is LeadStatus.AWAITING_SCORE
    with pytest.raises(ValueError, match="Invalid lead transition"):
        ready.transition_to(LeadStatus.CONTACTED)
