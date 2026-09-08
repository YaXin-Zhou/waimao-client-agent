"""获客任务用例：创建任务、清洗潜客并生成评分结果。"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.ports import LeadRepository, SearchProvider, TaskRepository
from src.domain.lead import CleanLead, LeadRecord, LeadScore, clean_leads, score_lead
from src.domain.task import AcquisitionCriteria, AcquisitionTask


@dataclass(frozen=True)
class AssessedLead:
    lead: CleanLead
    score: LeadScore


class AcquisitionService:
    def __init__(
        self,
        task_repository: TaskRepository,
        lead_repository: LeadRepository,
        search_provider: SearchProvider | None = None,
    ):
        self._tasks = task_repository
        self._leads = lead_repository
        self._search = search_provider

    def create_task(self, name: str, criteria: AcquisitionCriteria) -> AcquisitionTask:
        task = AcquisitionTask.create(name, criteria)
        self._tasks.save(task)
        return task

    def assess_leads(
        self,
        task_id: str,
        records: list[LeadRecord],
        weights: dict[str, int],
        signals_by_domain: dict[str, dict[str, int]],
    ) -> list[AssessedLead]:
        if self._tasks.get(task_id) is None:
            raise KeyError(f"Task not found: {task_id}")
        cleaned = clean_leads(records)
        results = [
            AssessedLead(
                lead=lead,
                score=score_lead(lead, weights, signals_by_domain.get(lead.domain, {})),
            )
            for lead in cleaned
        ]
        self._leads.save_assessments(task_id, results)
        return results

    def list_leads(self, task_id: str) -> list[AssessedLead]:
        if self._tasks.get(task_id) is None:
            raise KeyError(f"Task not found: {task_id}")
        return self._leads.list_assessments(task_id)

    def discover_and_assess(
        self,
        task_id: str,
        weights: dict[str, int],
        signals_by_domain: dict[str, dict[str, int]],
    ) -> list[AssessedLead]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if self._search is None:
            raise RuntimeError("Search provider is not configured")
        records = self._search.search(task.criteria)
        return self.assess_leads(task_id, records, weights, signals_by_domain)
