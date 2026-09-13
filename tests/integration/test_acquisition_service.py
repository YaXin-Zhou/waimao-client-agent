import threading
import time

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
            "Contact Alpine portable power station supplier",
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


def test_derived_score_reflects_partial_evidence_instead_of_fixed_buckets():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())
    task = service.create_task(
        "Partial evidence scoring",
        AcquisitionCriteria(
            product="portable power station",
            keywords=("OEM", "battery storage"),
            countries=("Germany",),
        ),
    )

    results = service.assess_leads(
        task.id,
        [
            LeadRecord(
                "Alpine Camp Supply",
                "https://alpine.example",
                "sales@alpine.example",
                "Germany",
                source_url="https://alpine.example/products",
                source_excerpt="Alpine sells portable power station products.",
            )
        ],
        weights={
            "product_match": 30,
            "market_match": 20,
            "email_quality": 15,
            "evidence_quality": 5,
        },
        signals_by_domain={},
    )

    score = results[0].score
    assert 0 < score.breakdown["product_match"] < 30


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


def test_product_evidence_does_not_match_inside_unrelated_english_word():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())
    task = service.create_task(
        "Product boundary", AcquisitionCriteria(product="art", minimum_qualification_score=0)
    )

    result = service.assess_leads(
        task.id,
        [
            LeadRecord(
                "Cartography Co",
                "https://cartography.example",
                source_url="https://cartography.example/products",
                source_excerpt="Cartography software and mapping tools.",
            )
        ],
        weights={"product_match": 30},
        signals_by_domain={},
    )[0]

    assert result.score.breakdown["product_match"] == 0


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


def test_product_evidence_funnel_uses_current_website_sources_not_old_score_breakdown():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())
    criteria = AcquisitionCriteria(product="portable power station")
    with_evidence = clean_leads(
        [
            LeadRecord(
                "Supply Co",
                "https://supply.example",
                source_url="https://www.google.com/search?q=portable+power+station",
                source_excerpt="search result",
            ),
            LeadRecord(
                "Supply Co",
                "https://supply.example",
                source_url="https://supply.example/about",
                source_excerpt="We distribute portable power stations.",
            ),
        ]
    )[0]

    assert service.has_product_evidence(with_evidence, criteria)


def test_generic_search_keywords_cannot_prove_product_need():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())
    criteria = AcquisitionCriteria(
        product="injection molding",
        keywords=("manufacturer", "supplier"),
    )
    lead = clean_leads(
        [
            LeadRecord(
                "Import Your Car",
                "https://cars.example",
                "sales@cars.example",
                "United Kingdom",
                "https://cars.example/about",
                "We are a leading car importer and supplier.",
            )
        ]
    )[0]

    assert service.has_product_evidence(lead, criteria) is False


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


def test_service_enriches_multiple_websites_with_bounded_concurrency():
    class Search:
        def search(self, criteria):
            return [
                LeadRecord("Alpine", "https://alpine.example", "", "Germany"),
                LeadRecord("North", "https://north.example", "", "Germany"),
            ]

    state = {"active": 0, "max_active": 0}
    lock = threading.Lock()

    class Reader:
        def fetch(self, url):
            with lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            time.sleep(0.05)
            with lock:
                state["active"] -= 1
            return SourceDocument(url, "Company", "plastic components manufacturer")

    tasks = InMemoryTaskRepository()
    service = AcquisitionService(
        tasks,
        InMemoryLeadRepository(),
        search_provider=Search(),
        website_reader=Reader(),
        website_workers=2,
    )
    task = service.create_task(
        "Concurrent website enrichment",
        AcquisitionCriteria(product="plastic components", minimum_qualification_score=0),
    )

    service.discover_and_assess(task.id, {}, {})

    assert state["max_active"] == 2


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


def test_contact_refresh_recalculates_default_score_for_unscored_import():
    tasks = InMemoryTaskRepository()
    leads = InMemoryLeadRepository()
    service = AcquisitionService(tasks, leads)
    task = service.create_task(
        "Re-score imported contacts",
        AcquisitionCriteria(product="portable power station", minimum_qualification_score=40),
    )
    service.assess_leads(
        task.id,
        [
            LeadRecord(
                "Alpine",
                "https://alpine.example",
                "",
                source_url="https://google.example/result",
                source_excerpt="Alpine portable power station supplier",
            )
        ],
        weights={},
        signals_by_domain={},
    )

    result = service.discover_public_contacts(task.id, "alpine.example", ContactFetcher())

    assert result.score.total == 50
    assert result.qualified is True


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


def test_service_recheck_replaces_stale_website_email_and_sources():
    tasks = InMemoryTaskRepository()
    leads = InMemoryLeadRepository()
    service = AcquisitionService(tasks, leads)
    task = service.create_task(
        "Replace stale contact evidence",
        AcquisitionCriteria(product="portable power station", require_public_email=False),
    )
    service.assess_leads(
        task.id,
        [
            LeadRecord(
                "Alpine",
                "https://alpine.example",
                "old@alpine.example",
                "Germany",
                "https://alpine.example/old-contact",
                "Old contact old@alpine.example",
            ),
        ],
        weights={},
        signals_by_domain={},
    )

    class Reader:
        def fetch_contact_pages(self, url, max_pages, allow_external_sources, max_external_pages):
            return (
                SourceDocument(
                    url,
                    "Alpine Products",
                    "Alpine portable power station products",
                ),
            )

    result = service.discover_public_contacts(task.id, "alpine.example", Reader())

    assert result.lead.emails == ()
    assert "old@alpine.example" not in " ".join(excerpt for _, excerpt in result.lead.sources)
    assert result.lead.sources == (
        ("https://alpine.example", "Alpine Products - Alpine portable power station products"),
    )


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
                LeadRecord(
                    "Strong Supply",
                    "https://strong.example",
                    "sales@strong.example",
                    source_url="https://strong.example/contact",
                        source_excerpt=(
                            "Strong Supply public sales contact for portable power station"
                        ),
                ),
            LeadRecord("No Email", "https://no-email.example", ""),
                LeadRecord(
                    "Low Score",
                    "https://low-score.example",
                    "info@low-score.example",
                    source_url="https://low-score.example/contact",
                        source_excerpt="Low Score public contact for portable power station",
                ),
        ],
        weights={"fit": 60},
        signals_by_domain={
            "strong.example": {"fit": 55},
            "no-email.example": {"fit": 60},
            "low-score.example": {"fit": 20},
        },
    )

    assert [item.lead.domain for item in results if item.qualified] == [
        "strong.example",
        "low-score.example",
    ]
    no_email = next(item for item in results if item.lead.domain == "no-email.example")
    low_score = next(item for item in results if item.lead.domain == "low-score.example")
    assert "missing_public_email" in no_email.rejection_reasons
    assert "qualified_quota_exceeded" not in low_score.rejection_reasons


def test_service_keeps_country_and_email_match_when_product_evidence_is_implicit():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())
    task = service.create_task(
        "Product evidence reason",
        AcquisitionCriteria(
            product="portable power station",
            countries=("德国",),
            minimum_qualification_score=0,
            require_public_email=True,
            candidate_limit=1,
            qualified_lead_limit=1,
        ),
    )

    result = service.assess_leads(
        task.id,
        [LeadRecord(
            "Unrelated Manufacturing",
            "https://unrelated.example",
            "info@unrelated.example",
            country="DE",
            source_url="https://unrelated.example/company",
            source_excerpt="Unrelated Manufacturing GmbH develops industrial equipment.",
        )],
        {"product_match": 30},
        {},
    )[0]

    assert result.qualified is True
    assert "missing_product_evidence" not in result.rejection_reasons


def test_service_keeps_public_email_when_identity_conflicts():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())
    task = service.create_task(
        "Identity gate",
        AcquisitionCriteria(
            product="portable power station",
            minimum_qualification_score=0,
            require_public_email=True,
        ),
    )

    result = service.assess_leads(
        task.id,
        [
            LeadRecord(
                "ELMAG",
                "https://elmag.eu",
                "office@elmag.at",
                "Austria",
                "https://elmag.eu/en/home/company",
                "ELMAG company profile and public contact.",
            )
        ],
        weights={},
        signals_by_domain={},
    )[0]

    assert result.qualified
    assert "email_domain_mismatch" not in result.rejection_reasons


def test_service_accepts_email_without_same_domain_product_evidence():
    service = AcquisitionService(InMemoryTaskRepository(), InMemoryLeadRepository())
    task = service.create_task(
        "External evidence boundary",
        AcquisitionCriteria(
            product="portable power station",
            minimum_qualification_score=0,
            require_public_email=True,
        ),
    )

    result = service.assess_leads(
        task.id,
        [
                LeadRecord(
                    "Alpine",
                    "https://alpine.example",
                    "info@alpine.example",
                    source_url="https://group.example/products",
                source_excerpt="Alpine group portable power station products",
            )
        ],
        weights={"product_match": 30},
        signals_by_domain={},
    )[0]

    assert result.score.breakdown["product_match"] == 0
    assert result.qualified is True


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
                        [
                            LeadRecord(
                                "Legacy Supply",
                                "https://legacy.example",
                                "sales@legacy.example",
                                source_url="https://legacy.example/contact",
                                    source_excerpt=(
                                        "Legacy Supply public contact for portable power station"
                                    ),
                            )
                        ]
                )[0],
                LeadScore(50, "B", {}),
            )
        ],
    )

    result = service.list_leads(task.id)[0]

    assert result.qualified
