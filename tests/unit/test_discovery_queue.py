import time

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


def test_discovery_queue_rejects_unknown_task():
    queue = DiscoveryJobQueue(Acquisition(), Runs(), max_workers=1, max_pending=1)

    with pytest.raises(KeyError, match="Task not found"):
        queue.submit("missing", {}, {})
    queue.close()
