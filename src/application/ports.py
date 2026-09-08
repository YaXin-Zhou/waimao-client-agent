"""应用层需要的持久化抽象。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from src.domain.lead import LeadRecord
from src.domain.task import AcquisitionTask

if TYPE_CHECKING:
    from src.application.acquisition_service import AssessedLead


class TaskRepository(Protocol):
    def save(self, task: AcquisitionTask) -> None: ...

    def get(self, task_id: str) -> AcquisitionTask | None: ...


class LeadRepository(Protocol):
    def save_assessments(self, task_id: str, results: list[AssessedLead]) -> None: ...

    def list_assessments(self, task_id: str) -> list[AssessedLead]: ...


class SearchProvider(Protocol):
    def search(self, criteria: object) -> list[LeadRecord]: ...
