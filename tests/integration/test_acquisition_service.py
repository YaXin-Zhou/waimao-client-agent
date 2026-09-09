import pytest

from src.application.acquisition_service import AcquisitionService, AssessedLead
from src.domain.custom_research import BusinessOffering, ResearchFieldDefinition
from src.domain.lead import LeadRecord, LeadScore, clean_leads
from src.domain.task import AcquisitionCriteria
from src.infrastructure.memory_repositories import InMemoryLeadRepository, InMemoryTaskRepository
from src.infrastructure.website_fetcher import PublicEmail, SourceDocument


class FakeSearchProvider:
    def search(self, criteria):
        assert criteria.product == "portable power station"
        return [
            LeadRecord(
                "Alpine Camp Supply",
                "https://alpine.example",
                "sales@alpine.example",
                "DE",
            )
        ]


class ContactFetcher:
    def fetch(self, url):
        return SourceDocument(
            url,
            "Contact",
            "Contact Alpine",
            (PublicEmail("sales@alpine.example", url, "Contact sales@alpine.example"),),
        )


def test_service_creates_task_and_assesses_imported_leads():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())
    task = service.create_task(
        "EU outdoor leads",
        AcquisitionCriteria(product="portable power station", countries=("Germany",)),
    )

    results = service.assess_leads(
        task.id,
        [
            LeadRecord(
                "Alpine Camp Supply",
                "https://alpine.example",
                "sales@alpine.example",
                "DE",
            ),
            LeadRecord(
                "Alpine Camp Supply",
                "https://www.alpine.example/contact",
                "info@alpine.example",
                "Germany",
            ),
        ],
        weights={"product_match": 30, "market_match": 20, "email_quality": 15},
        signals_by_domain={
            "alpine.example": {
                "product_match": 30,
                "market_match": 20,
                "email_quality": 15,
            }
        },
    )

    assert len(results) == 1
    assert results[0].lead.domain == "alpine.example"
    assert results[0].score.total == 65
    assert service.list_leads(task.id) == results


def test_service_rejects_unknown_task_before_processing_leads():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())

    with pytest.raises(KeyError, match="Task not found"):
        service.assess_leads("missing-task", [], {}, {})


def test_service_discovers_candidates_through_replaceable_provider():
    service = AcquisitionService(
        InMemoryTaskRepository(), InMemoryLeadRepository(), search_provider=FakeSearchProvider()
    )
    task = service.create_task(
        "EU outdoor leads",
        AcquisitionCriteria(product="portable power station"),
    )

    results = service.discover_and_assess(
        task.id,
        weights={"product_match": 30},
        signals_by_domain={"alpine.example": {"product_match": 30}},
    )

    assert results[0].lead.company_name == "Alpine Camp Supply"
    assert results[0].score.total == 30


def test_derived_product_signal_requires_candidate_source_text():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())
    task = service.create_task(
        "Product signal boundary",
        AcquisitionCriteria(product="portable solar generator", minimum_qualification_score=0),
    )

    result = service.assess_leads(
        task.id,
        [
            LeadRecord(
                "Portable Apps",
                "https://portableapps.example",
                "sales@portableapps.example",
                source_url="https://www.google.com/search?q=portable",
                source_excerpt="Portable software for USB and cloud storage",
            )
        ],
        weights={"product_match": 30},
        signals_by_domain={},
    )[0]

    assert result.score.total == 0


def test_derived_signals_ignore_search_result_page_as_business_evidence():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())
    task = service.create_task(
        "Search source boundary",
        AcquisitionCriteria(product="portable solar generator"),
    )

    result = service.assess_leads(
        task.id,
        [
            LeadRecord(
                "Portable Apps",
                "https://portableapps.example",
                "sales@portableapps.example",
                source_url="https://www.google.com.hk/search?q=portable+solar+generator",
                source_excerpt="Portable solar generator results",
            )
        ],
        weights={"product_match": 30, "evidence_quality": 5},
        signals_by_domain={},
    )[0]

    assert result.score.breakdown == {"product_match": 0, "evidence_quality": 0}


def test_service_enriches_automatic_search_with_real_public_website_emails():
    class Search:
        def search(self, criteria):
            return [LeadRecord("Alpine", "https://alpine.example", "", "Germany")]

    tasks = InMemoryTaskRepository()
    leads = InMemoryLeadRepository()
    service = AcquisitionService(
        tasks,
        leads,
        search_provider=Search(),
        website_reader=ContactFetcher(),
    )
    task = service.create_task(
        "Website enrichment",
        AcquisitionCriteria(product="portable power station", minimum_qualification_score=0),
    )

    results = service.discover_and_assess(task.id, {}, {})

    assert results[0].lead.emails == ("sales@alpine.example",)
    assert results[0].qualified
    assert results[0].lead.sources[-1][0] == "https://alpine.example"


def test_service_uses_fetched_website_text_as_match_evidence_without_query_injection():
    class Search:
        def search(self, criteria):
            return [LeadRecord("Alpine", "https://alpine.example", "", "Germany")]

    class Reader:
        def fetch(self, url):
            return SourceDocument(
                url,
                "Alpine portable power station",
                "We distribute portable power stations for outdoor retailers.",
            )

    tasks = InMemoryTaskRepository()
    service = AcquisitionService(
        tasks,
        InMemoryLeadRepository(),
        search_provider=Search(),
        website_reader=Reader(),
    )
    task = service.create_task(
        "Website evidence", AcquisitionCriteria(product="portable power station")
    )

    result = service.discover_and_assess(
        task.id, {"product_match": 30}, {}
    )[0]

    assert result.score.breakdown["product_match"] == 30
    assert "portable power stations" in result.lead.sources[0][1]


def test_service_updates_configurable_criteria_without_recreating_task():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())
    task = service.create_task("EU outdoor leads", AcquisitionCriteria(product="old service"))
    criteria = AcquisitionCriteria(
        product="new service",
        business_offerings=(BusinessOffering("CNC", "cnc_service", keywords=("CNC",)),),
        research_fields=(ResearchFieldDefinition("Buyer role", "buyer_role"),),
    )

    updated = service.update_criteria(task.id, criteria)

    assert updated.id == task.id
    assert service._tasks.get(task.id).criteria.business_offerings[0].key == "cnc_service"


def test_service_discovers_public_contacts_and_preserves_source_evidence():
    tasks = InMemoryTaskRepository()
    leads = InMemoryLeadRepository()
    service = AcquisitionService(tasks, leads)
    task = service.create_task(
        "EU outdoor leads", AcquisitionCriteria(product="portable power station")
    )
    service.assess_leads(
        task.id,
        [
            LeadRecord(
                "Alpine",
                "https://alpine.example",
                "",
                "Germany",
                "https://google.example",
                "result",
            )
        ],
        weights={},
        signals_by_domain={},
    )

    result = service.discover_public_contacts(task.id, "alpine.example", ContactFetcher())

    assert result.lead.emails == ("sales@alpine.example",)
    assert result.lead.sources[-1] == (
        "https://alpine.example",
        "Contact sales@alpine.example",
    )


def test_service_removes_invalid_persisted_contact_when_rechecking_public_pages():
    tasks = InMemoryTaskRepository()
    leads = InMemoryLeadRepository()
    service = AcquisitionService(tasks, leads)
    task = service.create_task(
        "Clean public contacts",
        AcquisitionCriteria(product="portable power station", require_public_email=True),
    )
    service.assess_leads(
        task.id,
        [LeadRecord("Example", "https://example.test", "contoso@example.com")],
        {},
        {},
    )

    class Reader:
        def fetch_contact_pages(self, url, max_pages, allow_external_sources, max_external_pages):
            return (type("Document", (), {"public_emails": ()})(),)

    result = service.discover_public_contacts(task.id, "example.test", Reader())

    assert result.lead.emails == ()
    assert "missing_public_email" in result.rejection_reasons


def test_service_keeps_only_qualified_leads_marked_and_records_rejection_reasons():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())
    task = service.create_task(
        "Qualified leads",
        AcquisitionCriteria(
            product="portable power station",
            qualified_lead_limit=1,
            minimum_qualification_score=40,
            require_public_email=True,
            candidate_limit=5,
        ),
    )

    results = service.assess_leads(
        task.id,
        [
            LeadRecord("Strong Supply", "https://strong.example", "sales@strong.example"),
            LeadRecord("No Email", "https://no-email.example", ""),
            LeadRecord("Low Score", "https://low-score.example", "info@low-score.example"),
        ],
        weights={"fit": 60},
        signals_by_domain={
            "strong.example": {"fit": 55},
            "no-email.example": {"fit": 60},
            "low-score.example": {"fit": 20},
        },
    )

    assert [item.lead.domain for item in results if item.qualified] == ["strong.example"]
    no_email = next(item for item in results if item.lead.domain == "no-email.example")
    low_score = next(item for item in results if item.lead.domain == "low-score.example")
    assert "missing_public_email" in no_email.rejection_reasons
    assert "score_below_threshold" in low_score.rejection_reasons


def test_service_explains_missing_product_evidence_separately():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())
    task = service.create_task(
        "Product evidence reason",
        AcquisitionCriteria(
            product="portable power station",
            minimum_qualification_score=0,
            require_public_email=False,
            candidate_limit=1,
            qualified_lead_limit=1,
        ),
    )

    result = service.assess_leads(
        task.id,
        [LeadRecord("Unrelated", "https://unrelated.example")],
        {"product_match": 30},
        {},
    )[0]

    assert not result.qualified
    assert "missing_product_evidence" in result.rejection_reasons


def test_service_requalifies_legacy_assessments_when_reading_task_leads():
    tasks = InMemoryTaskRepository()
    leads = InMemoryLeadRepository()
    service = AcquisitionService(tasks, leads)
    task = service.create_task(
        "Legacy records",
        AcquisitionCriteria(product="portable power station", minimum_qualification_score=0),
    )
    leads.save_assessments(
        task.id,
        [
            AssessedLead(
                clean_leads(
                    [LeadRecord("Legacy Supply", "https://legacy.example", "sales@legacy.example")]
                )[0],
                LeadScore(50, "B", {}),
            )
        ],
    )

    result = service.list_leads(task.id)[0]

    assert result.qualified
