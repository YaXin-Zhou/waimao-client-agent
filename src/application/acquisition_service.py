"""获客任务用例：创建任务、清洗潜客并生成评分结果。"""

from __future__ import annotations

from dataclasses import dataclass, replace

from src.application.ports import LeadRepository, SearchProvider, TaskRepository
from src.domain.lead import CleanLead, LeadRecord, LeadScore, clean_leads, score_lead
from src.domain.sender_profile import SenderProfile
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

    def create_task(
        self,
        name: str,
        criteria: AcquisitionCriteria,
        sender_profile: SenderProfile | None = None,
    ) -> AcquisitionTask:
        task = AcquisitionTask.create(name, criteria, sender_profile)
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

    def update_contact(
        self,
        task_id: str,
        domain: str,
        email: str,
        source_url: str,
        source_excerpt: str,
    ) -> AssessedLead:
        """补充有来源的公开邮箱，并保留原有评分。"""
        assessed = next(
            (item for item in self.list_leads(task_id) if item.lead.domain == domain), None
        )
        if assessed is None:
            raise KeyError(f"Lead not found: {domain}")
        if not source_url.strip() or not source_excerpt.strip():
            raise ValueError("contact source url and excerpt are required")
        record = LeadRecord(
            company_name=assessed.lead.company_name,
            website=f"https://{assessed.lead.domain}",
            email=email,
            country=assessed.lead.country,
            source_url=source_url,
            source_excerpt=source_excerpt,
        )
        updated = clean_leads([
            LeadRecord(
                record.company_name,
                record.website,
                assessed.lead.emails[0] if assessed.lead.emails else "",
                record.country,
                assessed.lead.sources[0][0] if assessed.lead.sources else "",
                assessed.lead.sources[0][1] if assessed.lead.sources else "",
            ),
            record,
        ])[0]
        result = AssessedLead(updated, assessed.score)
        self._leads.save_assessments(
            task_id,
            [item if item.lead.domain != domain else result for item in self.list_leads(task_id)],
        )
        return result

    def update_sender_profile(
        self, task_id: str, sender_profile: SenderProfile
    ) -> AcquisitionTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        updated = replace(task, sender_profile=sender_profile)
        self._tasks.save(updated)
        return updated

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
