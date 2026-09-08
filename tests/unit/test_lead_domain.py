from src.domain.lead import LeadRecord, clean_leads, score_lead


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
