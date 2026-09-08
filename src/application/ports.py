"""应用层需要的持久化抽象。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from src.domain.audit_event import AuditEvent
from src.domain.email_draft import EmailDraft
from src.domain.lead import LeadRecord
from src.domain.research_run import ResearchRun
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


class ResearchRunRepository(Protocol):
    def save(self, run: ResearchRun) -> None: ...

    def get(self, run_id: str) -> ResearchRun | None: ...


class EmailDraftRepository(Protocol):
    def save(self, draft: EmailDraft) -> None: ...

    def get(self, draft_id: str) -> EmailDraft | None: ...


class AuditEventRepository(Protocol):
    def save(self, event: AuditEvent) -> None: ...

    def list_for_entity(self, entity_type: str, entity_id: str) -> list[AuditEvent]: ...
