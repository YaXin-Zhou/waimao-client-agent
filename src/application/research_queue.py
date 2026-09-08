"""研究任务后台队列；队列本身可替换，运行状态由持久化记录负责。"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from src.application.research_execution import ResearchExecutionService
from src.domain.lead import CleanLead
from src.domain.research_run import ResearchRun


class ResearchJobQueue:
    def __init__(
        self, execution: ResearchExecutionService, runs, leads=None, max_workers: int = 2,
        max_pending: int = 100, timeout_seconds: int = 120,
    ):
        if max_workers <= 0:
            raise ValueError("max_workers must be positive")
        if max_pending <= 0:
            raise ValueError("max_pending must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._execution = execution
        self._runs = runs
        self._leads = leads
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._max_pending = max_pending
        self._timeout_seconds = timeout_seconds
        self._jobs: dict[str, Future] = {}

    def submit(
        self,
        task_id: str,
        lead: CleanLead,
        source_url: str,
        weights: dict[str, int],
        max_attempts: int = 2,
        request_key: str = "",
        timeout_seconds: int | None = None,
    ) -> ResearchRun:
        existing = self._runs.find_by_request_key(task_id, request_key)
        if existing is not None:
            return existing
        self._prune_finished()
        if len(self._jobs) >= self._max_pending:
            raise RuntimeError("research queue is full; retry later")
        if self._execution._tasks.get(task_id) is None:
            raise KeyError(f"Task not found: {task_id}")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        run = ResearchRun.start(
            task_id, lead.domain, request_key=request_key, source_url=source_url,
            weights=weights, max_attempts=max_attempts,
            timeout_seconds=timeout_seconds or self._timeout_seconds,
        )
        self._runs.save(run)
        self._jobs[run.id] = self._executor.submit(
            self._run,
            run,
            task_id,
            lead,
            source_url,
            weights,
            max_attempts,
            timeout_seconds or self._timeout_seconds,
        )
        return run

    def recover(self) -> int:
        """进程启动时恢复持久化的 running 任务；找不到客户的任务转为失败。"""
        if self._leads is None:
            return 0
        recovered = 0
        for run in self._runs.list_running():
            if run.id in self._jobs:
                continue
            assessed = next(
                (
                    item for item in self._leads.list_assessments(run.task_id)
                    if item.lead.domain == run.domain
                ),
                None,
            )
            if assessed is None:
                self._runs.save(run.fail("lead is no longer available for recovery"))
                continue
            self._jobs[run.id] = self._executor.submit(
                self._run, run, run.task_id, assessed.lead, run.source_url,
                dict(run.weights), run.max_attempts, run.timeout_seconds,
            )
            recovered += 1
        return recovered

    def _run(self, run, task_id, lead, source_url, weights, max_attempts, timeout_seconds):
        try:
            self._execution.execute(
                task_id,
                lead,
                source_url,
                weights,
                max_attempts=max_attempts,
                timeout_seconds=timeout_seconds,
                run=run,
            )
        except Exception:
            # The execution service has already persisted the terminal failure.
            return None

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _prune_finished(self) -> None:
        self._jobs = {
            run_id: future for run_id, future in self._jobs.items() if not future.done()
        }
