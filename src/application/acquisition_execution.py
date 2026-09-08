"""获客任务执行器：编排状态、搜索、评估和失败恢复。"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.acquisition_service import AcquisitionService, AssessedLead
from src.domain.task import AcquisitionTask, TaskStatus


@dataclass(frozen=True)
class AcquisitionExecutionResult:
    task: AcquisitionTask
    leads: tuple[AssessedLead, ...]


class AcquisitionExecutionService:
    """执行一次可恢复的获客任务，不把具体搜索实现耦合到任务编排。"""

    def __init__(self, tasks, acquisition: AcquisitionService):
        self._tasks = tasks
        self._acquisition = acquisition

    def execute(
        self,
        task_id: str,
        weights: dict[str, int],
        signals_by_domain: dict[str, dict[str, int]],
    ) -> AcquisitionExecutionResult:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if task.status is TaskStatus.COMPLETED:
            raise ValueError("Completed task cannot be executed again")

        running = self._move_to_running(task)
        try:
            leads = self._acquisition.discover_and_assess(
                task_id, weights, signals_by_domain
            )
            completed = running.transition_to(TaskStatus.COMPLETED)
            self._tasks.save(completed)
            return AcquisitionExecutionResult(completed, tuple(leads))
        except Exception as error:
            failed = running.transition_to(TaskStatus.FAILED)
            self._tasks.save(failed)
            raise error

    def _move_to_running(self, task: AcquisitionTask) -> AcquisitionTask:
        current = task
        if current.status in {TaskStatus.DRAFT, TaskStatus.FAILED, TaskStatus.PAUSED}:
            current = current.transition_to(TaskStatus.READY)
            self._tasks.save(current)
        if current.status is TaskStatus.READY:
            current = current.transition_to(TaskStatus.RUNNING)
            self._tasks.save(current)
        if current.status is not TaskStatus.RUNNING:
            raise ValueError(f"Task is not executable: {current.status}")
        return current
