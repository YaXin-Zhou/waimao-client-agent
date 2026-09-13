import time
from types import SimpleNamespace

import pytest

from src.application.discovery_queue import DiscoveryJobQueue
from src.domain.discovery_run import DiscoveryRunStep


class Runs:
    def __init__(self):
        self.items = {}

    def save(self, run):
        self.items[run.id] = run

    def get(self, run_id):
        return self.items.get(run_id)

    def list_for_task(self, task_id):
        return [item for item in self.items.values() if item.task_id == task_id]


class Tasks:
    def get(self, task_id):
        return object() if task_id == "task" else None


class Acquisition:
    def __init__(self):
        self._tasks = Tasks()

    def discover_and_assess(self, task_id, weights, signals, progress):
        progress(DiscoveryRunStep.SEARCHING, candidate_count=3)
        progress(DiscoveryRunStep.ASSESSING, candidate_count=3, qualified_count=1)
        return []


class MultiRoundAcquisition:
    def __init__(self):
        self._tasks = SimpleNamespace(
            get=lambda task_id: SimpleNamespace(
                criteria=SimpleNamespace(qualified_lead_limit=2)
            )
            if task_id == "task"
            else None
        )
        self.leads = []
        self.rounds = []

    def list_leads(self, task_id):
        return list(self.leads)

    def discover_and_assess(
        self, task_id, weights, signals, progress, search_round=0
    ):
        self.rounds.append(search_round)
        self.leads.append(
            SimpleNamespace(
                qualified=True,
                lead=SimpleNamespace(
                    domain=f"example-{search_round}.com",
                    emails=("a@example.com",),
                    sources=((f"https://example-{search_round}.com/about", "About"),),
                ),
            )
        )
        progress(
            DiscoveryRunStep.COMPLETED,
            candidate_count=len(self.leads),
            qualified_count=len(self.leads),
        )
        return self.leads


class ResearchQueue:
    def __init__(self):
        self.submissions = []

    def submit(self, task_id, lead, source_url, weights, request_key):
        self.submissions.append((task_id, lead.domain, source_url, request_key))


def wait_for_terminal(runs, run_id):
    for _ in range(50):
        run = runs.get(run_id)
        if run.status.value != "running":
            return run
        time.sleep(0.01)
    return runs.get(run_id)


def test_discovery_queue_persists_progress_and_completion():
    runs = Runs()
    queue = DiscoveryJobQueue(Acquisition(), runs, max_workers=1, max_pending=1)

    queued = queue.submit("task", {}, {})
    finished = wait_for_terminal(runs, queued.id)

    assert queued.step is DiscoveryRunStep.QUEUED
    assert finished.step is DiscoveryRunStep.COMPLETED
    assert finished.candidate_count == 3
    assert finished.qualified_count == 1
    queue.close()


def test_discovery_queue_runs_one_search_round_by_default():
    runs = Runs()
    acquisition = MultiRoundAcquisition()
    acquisition._tasks = SimpleNamespace(
        get=lambda task_id: SimpleNamespace(
            criteria=SimpleNamespace(qualified_lead_limit=10)
        )
        if task_id == "task"
        else None
    )
    queue = DiscoveryJobQueue(acquisition, runs, max_workers=1, max_pending=1)

    queued = queue.submit("task", {}, {})
    finished = wait_for_terminal(runs, queued.id)

    assert finished.step is DiscoveryRunStep.COMPLETED
    assert acquisition.rounds == [0]
    queue.close()


def test_discovery_queue_rotates_query_slice_on_later_clicks():
    runs = Runs()
    runs.save(
        SimpleNamespace(
            id="previous",
            task_id="task",
            status=SimpleNamespace(value="succeeded"),
        )
    )
    acquisition = MultiRoundAcquisition()
    queue = DiscoveryJobQueue(acquisition, runs, max_workers=1, max_pending=1)

    queued = queue.submit("task", {}, {})
    finished = wait_for_terminal(runs, queued.id)

    assert finished.step is DiscoveryRunStep.COMPLETED
    assert acquisition.rounds == [1]
    queue.close()


def test_discovery_queue_rejects_unknown_task():
    queue = DiscoveryJobQueue(Acquisition(), Runs(), max_workers=1, max_pending=1)

    with pytest.raises(KeyError, match="Task not found"):
        queue.submit("missing", {}, {})
    queue.close()


def test_discovery_queue_accumulates_rounds_until_qualified_target():
    runs = Runs()
    acquisition = MultiRoundAcquisition()
    queue = DiscoveryJobQueue(
        acquisition, runs, max_workers=1, max_pending=1, max_search_rounds=2
    )

    queued = queue.submit("task", {}, {})
    finished = wait_for_terminal(runs, queued.id)

    assert finished.step is DiscoveryRunStep.COMPLETED
    assert finished.candidate_count == 2
    assert finished.qualified_count == 2
    assert acquisition.rounds == [0, 1]
    queue.close()


def test_discovery_queue_starts_background_research_for_qualified_leads():
    runs = Runs()
    acquisition = MultiRoundAcquisition()
    research = ResearchQueue()
    queue = DiscoveryJobQueue(
        acquisition,
        runs,
        max_workers=1,
        max_pending=1,
        max_search_rounds=2,
        research_queue=research,
    )

    queued = queue.submit("task", {}, {})
    wait_for_terminal(runs, queued.id)

    assert [item[1] for item in research.submissions] == [
        "example-0.com",
        "example-1.com",
    ]
    queue.close()
