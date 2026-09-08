import time

from src.application.research_execution import ResearchExecutionService
from src.application.research_queue import ResearchJobQueue
from src.application.research_workflow import ResearchAssessment
from src.domain.lead import CleanLead, LeadScore
from src.domain.research import CustomerType, EvidenceStatus, ResearchResult
from src.domain.task import AcquisitionCriteria, AcquisitionTask


class Tasks:
    def __init__(self, task):
        self.task = task

    def get(self, task_id):
        return self.task if task_id == self.task.id else None


class Runs:
    def __init__(self):
        self.items = {}

    def save(self, run):
        self.items[run.id] = run

    def find_by_request_key(self, task_id, request_key):
        return next(
            (
                run
                for run in self.items.values()
                if run.task_id == task_id and run.request_key == request_key and request_key
            ),
            None,
        )


class Workflow:
    def run(self, task_id, lead, source_url, weights):
        return ResearchAssessment(
            ResearchResult(
                lead.company_name,
                "Distributor",
                CustomerType.DISTRIBUTOR,
                ("solar generator",),
                "Germany",
                0.9,
                source_url,
                EvidenceStatus.SUFFICIENT,
            ),
            LeadScore(80, "A", {"product": 40}),
        )


def test_queue_runs_in_background_and_is_idempotent():
    task = AcquisitionTask.create("Test", AcquisitionCriteria(product="solar generator"))
    runs = Runs()
    execution = ResearchExecutionService(Tasks(task), Workflow(), runs)
    queue = ResearchJobQueue(execution, runs, max_workers=1)
    lead = CleanLead("Alpine", "alpine.example", ("sales@alpine.example",), "Germany", "complete")

    first = queue.submit(
        task.id,
        lead,
        "https://alpine.example",
        {"product": 40},
        request_key="research-1",
    )
    second = queue.submit(
        task.id,
        lead,
        "https://alpine.example",
        {"product": 40},
        request_key="research-1",
    )

    assert second.id == first.id
    deadline = time.monotonic() + 2
    while (
        time.monotonic() < deadline
        and (first.id not in runs.items or runs.items[first.id].status.value == "running")
    ):
        time.sleep(0.01)
    assert runs.items[first.id].status.value == "succeeded"
    assert len(runs.items) == 1
    queue.close()
