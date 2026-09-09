import pytest

from src.application.acquisition_service import AcquisitionService
from src.domain.custom_research import BusinessOffering, ResearchFieldDefinition
from src.domain.lead import LeadRecord
from src.domain.task import AcquisitionCriteria
from src.infrastructure.memory_repositories import InMemoryLeadRepository, InMemoryTaskRepository


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
