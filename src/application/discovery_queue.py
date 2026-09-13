"""真实获客发现的后台队列与持久化进度。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import time

from src.domain.discovery_run import DiscoveryRun, DiscoveryRunStep
from src.domain.lead import is_search_source
from src.application.acquisition_service import DEFAULT_QUALIFICATION_WEIGHTS


class DiscoveryJobQueue:
    def __init__(
        self,
        acquisition,
        runs,
        max_workers: int = 1,
        max_pending: int = 4,
        max_search_rounds: int = 1,
        research_queue=None,
        round_interval_seconds: float = 0.0,
        sleep=time.sleep,
    ):
        if max_workers <= 0 or max_pending <= 0:
            raise ValueError("discovery queue limits must be positive")
        if max_search_rounds <= 0:
            raise ValueError("max_search_rounds must be positive")
        if round_interval_seconds < 0:
            raise ValueError("round_interval_seconds must not be negative")
        self._acquisition = acquisition
        self._runs = runs
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._max_pending = max_pending
        self._max_search_rounds = max_search_rounds
        self._research_queue = research_queue
        self._round_interval_seconds = round_interval_seconds
        self._sleep = sleep
        self._jobs = {}
        self._lock = Lock()
        recover = getattr(self._runs, "fail_running", None)
        if callable(recover):
            recover("本地服务已重新启动，上一轮搜索已停止，请重新搜索。")

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
            start_round = self._next_search_round(task_id)
            self._jobs[run.id] = self._executor.submit(
                self._run, run, task_id, weights, signals, start_round
            )
        return run

    def _run(self, run, task_id, weights, signals, start_round=0):
        try:
            list_leads = getattr(self._acquisition, "list_leads", None)
            task = self._acquisition._tasks.get(task_id)
            multi_round = callable(list_leads) and task is not None
            rounds = self._max_search_rounds if multi_round else 1
            for round_offset in range(rounds):
                round_index = start_round + round_offset
                if multi_round:
                    daily_target = getattr(
                        task.criteria, "daily_limit", task.criteria.qualified_lead_limit
                    )
                if multi_round and self._qualified_count(task_id) >= daily_target:
                    break
                discovery_kwargs = {
                    "progress": lambda step, **counts: self._save_progress(
                        run, step, **counts
                    )
                }
                if multi_round:
                    discovery_kwargs["search_round"] = round_index
                self._acquisition.discover_and_assess(
                    task_id, weights, signals, **discovery_kwargs
                )
                if multi_round:
                    counts = self._cumulative_counts(task_id)
                    self._save_progress(run, "completed", **counts)
                    if round_index + 1 < rounds and self._qualified_count(task_id) < daily_target:
                        self._sleep(self._round_interval_seconds)
            counts = self._cumulative_counts(task_id) if multi_round else {}
            latest = self._runs.get(run.id) or run
            self._enqueue_research(task_id, run.id, weights)
            self._runs.save(latest.succeed(**counts))
        except Exception as error:
            self._runs.save((self._runs.get(run.id) or run).fail(str(error)))

    def _next_search_round(self, task_id: str) -> int:
        """Rotate later clicks through remaining query slices."""
        list_for_task = getattr(self._runs, "list_for_task", None)
        if not callable(list_for_task):
            return 0
        return sum(
            1
            for item in list_for_task(task_id)
            if getattr(getattr(item, "status", None), "value", getattr(item, "status", ""))
            == "succeeded"
        )

    def _qualified_count(self, task_id: str) -> int:
        return sum(bool(item.qualified) for item in self._acquisition.list_leads(task_id))

    def _cumulative_counts(self, task_id: str) -> dict[str, int]:
        items = self._acquisition.list_leads(task_id)
        return {
            "candidate_count": len(items),
            "website_count": sum(bool(item.lead.domain) for item in items),
            "public_email_count": sum(bool(item.lead.emails) for item in items),
            "qualified_count": sum(bool(item.qualified) for item in items),
        }

    def _save_progress(self, run, step: DiscoveryRunStep | str, **counts: int):
        self._runs.save(
            (self._runs.get(run.id) or run).progress(DiscoveryRunStep(step), **counts)
        )

    def _enqueue_research(self, task_id: str, run_id: str, weights: dict) -> None:
        if self._research_queue is None:
            return
        for item in self._acquisition.list_leads(task_id):
            if not item.qualified or not item.lead.domain or not item.lead.sources:
                continue
            source_url = next(
                (
                    url
                    for url, _excerpt in item.lead.sources
                    if url.strip() and not is_search_source(url)
                ),
                f"https://{item.lead.domain}",
            )
            try:
                self._research_queue.submit(
                    task_id,
                    item.lead,
                    source_url,
                    weights or DEFAULT_QUALIFICATION_WEIGHTS,
                    request_key=f"auto-discovery:{task_id}:{item.lead.domain}",
                )
            except Exception:
                # Discovery delivery must not be marked failed because one
                # optional background research job could not be queued.
                continue

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _prune_finished(self) -> None:
        self._jobs = {
            run_id: future for run_id, future in self._jobs.items() if not future.done()
        }
