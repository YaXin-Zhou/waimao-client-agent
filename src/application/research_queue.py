"""研究任务后台队列；队列本身可替换，运行状态由持久化记录负责。"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from src.application.research_execution import ResearchExecutionService
from src.domain.lead import CleanLead
from src.domain.research_run import ResearchRun


class ResearchJobQueue:
    def __init__(self, execution: ResearchExecutionService, runs, max_workers: int = 2):
        if max_workers <= 0:
            raise ValueError("max_workers must be positive")
        self._execution = execution
        self._runs = runs
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, Future] = {}

    def submit(
        self,
        task_id: str,
        lead: CleanLead,
        source_url: str,
        weights: dict[str, int],
        max_attempts: int = 2,
        request_key: str = "",
    ) -> ResearchRun:
        existing = self._runs.find_by_request_key(task_id, request_key)
        if existing is not None:
            return existing
        if self._execution._tasks.get(task_id) is None:
            raise KeyError(f"Task not found: {task_id}")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        run = ResearchRun.start(task_id, lead.domain, request_key=request_key)
        self._runs.save(run)
        self._jobs[run.id] = self._executor.submit(
            self._run,
            run,
            task_id,
            lead,
            source_url,
            weights,
            max_attempts,
        )
        return run

    def _run(self, run, task_id, lead, source_url, weights, max_attempts):
        try:
            self._execution.execute(
                task_id,
                lead,
                source_url,
                weights,
                max_attempts=max_attempts,
                run=run,
            )
        except Exception:
            # The execution service has already persisted the terminal failure.
            return None

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)
