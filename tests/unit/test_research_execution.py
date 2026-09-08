import time

import pytest

from src.application.research_execution import ResearchExecutionService
from src.application.research_workflow import ResearchAssessment
from src.domain.lead import CleanLead, LeadScore
from src.domain.research import CustomerType, EvidenceStatus, ResearchResult
from src.domain.task import AcquisitionCriteria, AcquisitionTask


class FakeTaskRepository:
    def __init__(self, task):
        self.task = task

    def get(self, task_id):
        return self.task if task_id == self.task.id else None


class FlakyWorkflow:
    def __init__(self, failures=1, evidence_status=EvidenceStatus.SUFFICIENT):
        self.failures = failures
        self.calls = 0
        self.evidence_status = evidence_status

    def run(self, task_id, lead, source_url, weights, progress=None):
        self.calls += 1
        if self.calls <= self.failures:
            raise TimeoutError("temporary website timeout")
        return ResearchAssessment(
            ResearchResult(
                lead.company_name,
                "Distributor of portable power stations.",
                CustomerType.DISTRIBUTOR,
                ("portable power stations",),
                "Germany",
                0.9,
                source_url,
                self.evidence_status,
            ),
            LeadScore(70, "B", {"product_match": 30}),
        )


class MemoryRunRepository:
    def __init__(self):
        self.items = {}

    def save(self, run):
        self.items[run.id] = run


def clean_alpine():
    return CleanLead("Alpine", "alpine.example", ("sales@alpine.example",), "Germany", "complete")


def test_execution_retries_transient_failure_and_succeeds():
    task = AcquisitionTask.create("Test", AcquisitionCriteria(product="power station"))
    workflow = FlakyWorkflow(failures=1)
    repository = MemoryRunRepository()
    service = ResearchExecutionService(FakeTaskRepository(task), workflow, repository)

    result = service.execute(task.id, clean_alpine(), "https://alpine.example", {}, max_attempts=2)

    assert workflow.calls == 2
    assert result.run.status.value == "succeeded"
    assert result.run.attempts == 2


def test_execution_records_failed_run_after_retry_limit():
    task = AcquisitionTask.create("Test", AcquisitionCriteria(product="power station"))
    repository = MemoryRunRepository()
    service = ResearchExecutionService(
        FakeTaskRepository(task), FlakyWorkflow(failures=3), repository
    )

    with pytest.raises(TimeoutError, match="temporary website timeout"):
        service.execute(task.id, clean_alpine(), "https://alpine.example", {}, max_attempts=2)

    run = next(iter(repository.items.values()))
    assert run.status.value == "failed"
    assert run.attempts == 2
    assert run.error == "temporary website timeout"


def test_execution_marks_insufficient_evidence_for_review():
    task = AcquisitionTask.create("Test", AcquisitionCriteria(product="power station"))
    repository = MemoryRunRepository()
    service = ResearchExecutionService(
        FakeTaskRepository(task),
        FlakyWorkflow(failures=0, evidence_status=EvidenceStatus.INSUFFICIENT),
        repository,
    )

    result = service.execute(
        task.id,
        clean_alpine(),
        "https://alpine.example",
        {},
    )

    assert result.run.status.value == "review_required"
    assert result.run.attempts == 1


def test_execution_does_not_retry_invalid_workflow_input():
    task = AcquisitionTask.create("Test", AcquisitionCriteria(product="power station"))
    repository = MemoryRunRepository()
    workflow = FlakyWorkflow(failures=0)

    def invalid_run(*args, **kwargs):
        raise ValueError("invalid structured result")

    workflow.run = invalid_run
    service = ResearchExecutionService(FakeTaskRepository(task), workflow, repository)

    with pytest.raises(ValueError, match="invalid structured result"):
        service.execute(
            task.id,
            clean_alpine(),
            "https://alpine.example",
            {},
            max_attempts=2,
        )

    run = next(iter(repository.items.values()))
    assert run.status.value == "failed"
    assert run.attempts == 1


def test_execution_persists_timeout_when_workflow_exceeds_deadline():
    task = AcquisitionTask.create("Test", AcquisitionCriteria(product="power station"))
    repository = MemoryRunRepository()

    class SlowWorkflow(FlakyWorkflow):
        def run(self, task_id, lead, source_url, weights, progress=None):
            time.sleep(0.02)
            return super().run(task_id, lead, source_url, weights, progress)

    service = ResearchExecutionService(
        FakeTaskRepository(task), SlowWorkflow(failures=0), repository
    )

    with pytest.raises(TimeoutError, match="exceeded timeout_seconds"):
        service.execute(
            task.id,
            clean_alpine(),
            "https://alpine.example",
            {},
            max_attempts=1,
            timeout_seconds=0.01,
        )

    run = next(iter(repository.items.values()))
    assert run.status.value == "failed"
    assert run.error == "research run exceeded timeout_seconds"
