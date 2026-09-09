"""用于开发和测试的内存仓储；生产环境可替换为数据库实现。"""

from __future__ import annotations

from dataclasses import replace

from src.application.acquisition_service import AssessedLead
from src.domain.lead import LeadScore
from src.domain.task import AcquisitionTask


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._items: dict[str, AcquisitionTask] = {}

    def save(self, task: AcquisitionTask) -> None:
        self._items[task.id] = task

    def get(self, task_id: str) -> AcquisitionTask | None:
        return self._items.get(task_id)


class InMemoryLeadRepository:
    def __init__(self) -> None:
        self._items: dict[str, list[AssessedLead]] = {}

    def save_assessments(self, task_id: str, results: list[AssessedLead]) -> None:
        self._items[task_id] = list(results)

    def list_assessments(self, task_id: str) -> list[AssessedLead]:
        return list(self._items.get(task_id, []))

    def update_score(self, task_id: str, domain: str, score: LeadScore) -> None:
        items = self._items.get(task_id, [])
        self._items[task_id] = [
            replace(item, score=score) if item.lead.domain == domain else item
            for item in items
        ]
