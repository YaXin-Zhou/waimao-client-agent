import pytest

from src.application.acquisition_execution import AcquisitionExecutionService
from src.application.acquisition_service import AcquisitionService
from src.domain.lead import LeadRecord
from src.domain.task import AcquisitionCriteria, TaskStatus
from src.infrastructure.memory_repositories import InMemoryLeadRepository, InMemoryTaskRepository


class SearchProvider:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.remembered = set()

    def remember_domains(self, domains):
        self.remembered.update(domains)

    def search(self, criteria):
        if self.should_fail:
            raise TimeoutError("search timeout")
        return [LeadRecord("Alpine Camp Supply", "https://alpine.example", "", "DE")]


def make_service(should_fail=False):
    tasks = InMemoryTaskRepository()
    leads = InMemoryLeadRepository()
    acquisition = AcquisitionService(
        tasks, leads, search_provider=SearchProvider(should_fail=should_fail)
    )
    task = acquisition.create_task(
        "EU outdoor leads", AcquisitionCriteria(product="portable power station")
    )
    return tasks, leads, acquisition, task


def test_execution_runs_provider_assessment_and_persists_completed_status():
    tasks, leads, acquisition, task = make_service()
    executor = AcquisitionExecutionService(tasks, acquisition)

    result = executor.execute(
        task.id,
        weights={"product_fit": 40},
        signals_by_domain={"alpine.example": {"product_fit": 35}},
    )

    assert result.task.status is TaskStatus.COMPLETED
    assert len(result.leads) == 1
    assert tasks.get(task.id).status is TaskStatus.COMPLETED
    assert leads.list_assessments(task.id)[0].score.total == 35


def test_execution_persists_failed_status_and_allows_retry():
    tasks, leads, acquisition, task = make_service(should_fail=True)
    executor = AcquisitionExecutionService(tasks, acquisition)

    with pytest.raises(TimeoutError):
        executor.execute(task.id, {}, {})

    assert tasks.get(task.id).status is TaskStatus.FAILED


def test_completed_task_is_not_executed_twice():
    tasks, _, acquisition, task = make_service()
    executor = AcquisitionExecutionService(tasks, acquisition)
    executor.execute(task.id, {}, {})

    with pytest.raises(ValueError, match="cannot be executed again"):
        executor.execute(task.id, {}, {})


def test_discovery_syncs_existing_domains_to_deduplicating_provider():
    tasks = InMemoryTaskRepository()
    leads = InMemoryLeadRepository()
    provider = SearchProvider()
    acquisition = AcquisitionService(tasks, leads, search_provider=provider)
    task = acquisition.create_task(
        "dedupe", AcquisitionCriteria(product="portable power station")
    )

    acquisition.discover_and_assess(task.id, {}, {}, search_round=0)

    assert provider.remembered == set()
    acquisition.discover_and_assess(task.id, {}, {}, search_round=1)
    assert provider.remembered == {"alpine.example"}
