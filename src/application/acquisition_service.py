"""获客任务用例：创建任务、清洗潜客并生成评分结果。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from urllib.parse import urlparse

from src.application.ports import (
    AuditEventRepository,
    LeadRepository,
    SearchProvider,
    TaskRepository,
)
from src.domain.audit_event import AuditEvent
from src.domain.lead import CleanLead, LeadRecord, LeadScore, LeadStatus, clean_leads, score_lead
from src.domain.sender_profile import SenderProfile
from src.domain.task import AcquisitionCriteria, AcquisitionTask, TaskStatus


@dataclass(frozen=True)
class AssessedLead:
    lead: CleanLead
    score: LeadScore
    qualified: bool = False
    rejection_reasons: tuple[str, ...] = ()


class AcquisitionService:
    def __init__(
        self,
        task_repository: TaskRepository,
        lead_repository: LeadRepository,
        search_provider: SearchProvider | None = None,
        audit_repository: AuditEventRepository | None = None,
        website_reader=None,
    ):
        self._tasks = task_repository
        self._leads = lead_repository
        self._search = search_provider
        self._audit = audit_repository
        self._website_reader = website_reader
        self._website_page_limit = 5
        self._external_source_limit = 3

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
                score=score_lead(
                    lead,
                    weights,
                    signals_by_domain.get(lead.domain)
                    or self._derive_signals(lead, task_id, weights),
                ),
            )
            for lead in cleaned
        ]
        task = self._tasks.get(task_id)
        assert task is not None
        qualified = self._qualify(results, task.criteria)
        self._leads.save_assessments(task_id, qualified)
        return qualified

    def _derive_signals(
        self, lead: CleanLead, task_id: str, weights: dict[str, int]
    ) -> dict[str, int]:
        """没有外部评分时，按当前任务配置生成可解释的基础信号。"""
        task = self._tasks.get(task_id)
        if task is None:
            return {}
        criteria = task.criteria
        searchable = " ".join(
            (
                lead.company_name,
                lead.domain,
                *(source[1] for source in lead.sources),
                criteria.product,
                *criteria.keywords,
            )
        ).lower()
        configured_terms = tuple(
            term.strip().lower()
            for term in (criteria.product, *criteria.keywords)
            if term.strip()
        )
        signals: dict[str, int] = {}
        if "product_match" in weights and any(term in searchable for term in configured_terms):
            signals["product_match"] = weights["product_match"]
        if "email_quality" in weights and lead.emails:
            signals["email_quality"] = weights["email_quality"]
        if "evidence_quality" in weights and lead.sources:
            signals["evidence_quality"] = weights["evidence_quality"]
        if "market_match" in weights and lead.country:
            markets = {value.strip().lower() for value in criteria.countries if value.strip()}
            if not markets or lead.country.lower() in markets:
                signals["market_match"] = weights["market_match"]
        return signals

    @staticmethod
    def _qualify(
        results: list[AssessedLead], criteria: AcquisitionCriteria
    ) -> list[AssessedLead]:
        """按任务配置筛选可交付客户，同时保留所有候选及淘汰原因。"""
        evaluated: list[AssessedLead] = []
        for item in results:
            reasons: list[str] = []
            if not item.lead.domain:
                reasons.append("missing_website")
            if criteria.require_public_email and not item.lead.emails:
                reasons.append("missing_public_email")
            if item.score.total < criteria.minimum_qualification_score:
                reasons.append("score_below_threshold")
            if "conflicting_country" in item.lead.flags:
                reasons.append("conflicting_country")
            evaluated.append(
                replace(
                    item,
                    qualified=not reasons,
                    rejection_reasons=tuple(dict.fromkeys(reasons)),
                )
            )

        ranked = sorted(
            (item for item in evaluated if item.qualified),
            key=lambda item: item.score.total,
            reverse=True,
        )
        selected_domains = {item.lead.domain for item in ranked[: criteria.qualified_lead_limit]}
        return [
            replace(
                item,
                qualified=item.lead.domain in selected_domains,
                rejection_reasons=(
                    item.rejection_reasons
                    if item.lead.domain in selected_domains
                    else tuple(
                        dict.fromkeys(
                            item.rejection_reasons + ("qualified_quota_exceeded",)
                        )
                    )
                ),
            )
            for item in evaluated
        ]

    def list_leads(self, task_id: str) -> list[AssessedLead]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        current = self._leads.list_assessments(task_id)
        # 兼容升级前写入的记录：旧记录没有资格判断字段，需要按当前任务规则重评估。
        refreshed = self._qualify(current, task.criteria)
        if refreshed != current:
            self._leads.save_assessments(task_id, refreshed)
        return refreshed

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
        updated = clean_leads(
            [
                LeadRecord(
                    record.company_name,
                    record.website,
                    assessed.lead.emails[0] if assessed.lead.emails else "",
                    record.country,
                    assessed.lead.sources[0][0] if assessed.lead.sources else "",
                    assessed.lead.sources[0][1] if assessed.lead.sources else "",
                ),
                record,
            ]
        )[0]
        result = self._qualify(
            [AssessedLead(replace(updated, status=assessed.lead.status), assessed.score)],
            self._tasks.get(task_id).criteria,  # type: ignore[union-attr]
        )[0]
        self._leads.save_assessments(
            task_id,
            [item if item.lead.domain != domain else result for item in self.list_leads(task_id)],
        )
        return result

    def discover_public_contacts(self, task_id: str, domain: str, website_reader) -> AssessedLead:
        """Extract only emails published by the lead's website and keep evidence."""
        assessed = next(
            (item for item in self.list_leads(task_id) if item.lead.domain == domain), None
        )
        if assessed is None:
            raise KeyError(f"Lead not found: {domain}")
        website = f"https://{domain}"
        document = website_reader.fetch(website)
        public_emails = getattr(document, "public_emails", ())
        if not public_emails:
            return assessed
        first_source = assessed.lead.sources[0] if assessed.lead.sources else ("", "")
        records = [
            LeadRecord(
                assessed.lead.company_name,
                website,
                email,
                assessed.lead.country,
                first_source[0],
                first_source[1],
            )
            for email in assessed.lead.emails or ("",)
        ]
        records.extend(
            LeadRecord(assessed.lead.company_name, website, "", assessed.lead.country, url, excerpt)
            for url, excerpt in assessed.lead.sources[1:]
        )
        records.extend(
            LeadRecord(
                assessed.lead.company_name,
                website,
                item.address,
                assessed.lead.country,
                item.source_url,
                item.excerpt,
            )
            for item in public_emails
        )
        updated_lead = replace(clean_leads(records)[0], status=assessed.lead.status)
        result = self._qualify(
            [AssessedLead(updated_lead, assessed.score)],
            self._tasks.get(task_id).criteria,  # type: ignore[union-attr]
        )[0]
        self._leads.save_assessments(
            task_id,
            [item if item.lead.domain != domain else result for item in self.list_leads(task_id)],
        )
        return result

    def transition_lead(
        self, task_id: str, domain: str, target: LeadStatus, actor: str, note: str = ""
    ) -> AssessedLead:
        assessed = next(
            (item for item in self.list_leads(task_id) if item.lead.domain == domain), None
        )
        if assessed is None:
            raise KeyError(f"Lead not found: {domain}")
        updated_lead = assessed.lead.transition_to(target)
        updated = AssessedLead(updated_lead, assessed.score)
        self._leads.save_assessments(
            task_id,
            [item if item.lead.domain != domain else updated for item in self.list_leads(task_id)],
        )
        if self._audit is not None:
            self._audit.save(
                AuditEvent.status_change(
                    entity_type="lead",
                    entity_id=f"{task_id}:{domain}",
                    action="transition",
                    actor=actor,
                    from_status=assessed.lead.status.value,
                    to_status=target.value,
                    note=note,
                )
            )
        return updated

    def update_sender_profile(self, task_id: str, sender_profile: SenderProfile) -> AcquisitionTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        updated = replace(task, sender_profile=sender_profile)
        self._tasks.save(updated)
        return updated

    def update_criteria(self, task_id: str, criteria: AcquisitionCriteria) -> AcquisitionTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        updated = replace(task, criteria=criteria)
        self._tasks.save(updated)
        return updated

    def transition_task(
        self, task_id: str, target: TaskStatus, actor: str, note: str = ""
    ) -> AcquisitionTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        updated = task.transition_to(target)
        if self._audit is not None:
            self._audit.save(
                AuditEvent.status_change(
                    entity_type="acquisition_task",
                    entity_id=task.id,
                    action="transition",
                    actor=actor,
                    from_status=task.status.value,
                    to_status=updated.status.value,
                    note=note,
                )
            )
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
        records = self._enrich_search_records(records)
        return self.assess_leads(task_id, records, weights, signals_by_domain)

    def _enrich_search_records(self, records: list[LeadRecord]) -> list[LeadRecord]:
        """从候选官网提取公开邮箱；失败时保留原始候选，不猜测联系方式。"""
        if self._website_reader is None:
            return records
        enriched: list[LeadRecord] = []
        fetched: set[str] = set()
        for record in records:
            enriched.append(record)
            parsed = urlparse(record.website.strip())
            domain = (parsed.hostname or "").lower().removeprefix("www.")
            if not domain or domain in fetched:
                continue
            fetched.add(domain)
            try:
                fetch_pages = getattr(self._website_reader, "fetch_contact_pages", None)
                documents = (
                    fetch_pages(
                        record.website.strip(),
                        max_pages=self._website_page_limit,
                        allow_external_sources=True,
                        max_external_pages=self._external_source_limit,
                    )
                    if fetch_pages is not None
                    else (self._website_reader.fetch(record.website.strip()),)
                )
            except Exception:
                continue
            for document in documents:
                for public_email in getattr(document, "public_emails", ()):
                    enriched.append(
                        LeadRecord(
                            company_name=record.company_name,
                            website=record.website,
                            email=public_email.address,
                            country=record.country,
                            source_url=public_email.source_url,
                            source_excerpt=public_email.excerpt,
                        )
                    )
        return enriched
