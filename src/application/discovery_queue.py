"""真实获客发现的后台队列与持久化进度。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from src.domain.discovery_run import DiscoveryRun, DiscoveryRunStep


class DiscoveryJobQueue:
    def __init__(self, acquisition, runs, max_workers: int = 1, max_pending: int = 4):
        if max_workers <= 0 or max_pending <= 0:
            raise ValueError("discovery queue limits must be positive")
        self._acquisition = acquisition
        self._runs = runs
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._max_pending = max_pending
        self._jobs = {}
        self._lock = Lock()

    def submit(
        self, task_id: str, weights: dict[str, int], signals: dict[str, dict[str, int]]
    ) -> DiscoveryRun:
        with self._lock:
            self._prune_finished()
            if len(self._jobs) >= self._max_pending:
                raise RuntimeError("discovery queue is full; retry later")
            if self._acquisition._tasks.get(task_id) is None:
                raise KeyError(f"Task not found: {task_id}")
            run = DiscoveryRun.start(task_id)
            self._runs.save(run)
            self._jobs[run.id] = self._executor.submit(
                self._run, run, task_id, weights, signals
            )
        return run

    def _run(self, run, task_id, weights, signals):
        try:
            self._acquisition.discover_and_assess(
                task_id,
                weights,
                signals,
                progress=lambda step, **counts: self._save_progress(run, step, **counts),
            )
            latest = self._runs.get(run.id) or run
            self._runs.save(latest.succeed())
        except Exception as error:
            self._runs.save((self._runs.get(run.id) or run).fail(str(error)))

    def _save_progress(self, run, step: DiscoveryRunStep | str, **counts: int):
        self._runs.save(
            (self._runs.get(run.id) or run).progress(DiscoveryRunStep(step), **counts)
        )

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _prune_finished(self) -> None:
        self._jobs = {
            run_id: future for run_id, future in self._jobs.items() if not future.done()
        }
