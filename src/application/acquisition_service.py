"""获客任务用例：创建任务、清洗潜客并生成评分结果。"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from urllib.parse import urlparse

from src.application.ports import (
    AuditEventRepository,
    LeadRepository,
    SearchProvider,
    TaskRepository,
)
from src.application.search_queries import search_term_variants
from src.domain.audit_event import AuditEvent
from src.domain.lead import (
    CleanLead,
    LeadRecord,
    LeadScore,
    LeadStatus,
    canonical_website_domain,
    clean_company_name,
    clean_leads,
    identity_consistency,
    is_plausible_email,
    is_credible_source_excerpt,
    is_search_source,
    score_lead,
)
from src.domain.sender_profile import SenderProfile
from src.domain.task import (
    AcquisitionCriteria,
    AcquisitionTask,
    TaskStatus,
    configured_research_terms,
    configured_product_evidence_terms,
)


@dataclass(frozen=True)
class AssessedLead:
    lead: CleanLead
    score: LeadScore
    qualified: bool = False
    rejection_reasons: tuple[str, ...] = ()


DEFAULT_QUALIFICATION_WEIGHTS = {
    "product_match": 30,
    "market_match": 20,
    "email_quality": 15,
    "evidence_quality": 5,
}


_COUNTRY_ALIASES = {
    "中国": "china",
    "cn": "china",
    "china": "china",
    "德国": "germany",
    "de": "germany",
    "germany": "germany",
    "美国": "united states",
    "us": "united states",
    "usa": "united states",
    "united states": "united states",
    "英国": "united kingdom",
    "gb": "united kingdom",
    "uk": "united kingdom",
    "united kingdom": "united kingdom",
    "法国": "france",
    "fr": "france",
    "france": "france",
    "意大利": "italy",
    "it": "italy",
    "italy": "italy",
}


def _country_key(value: str) -> str:
    normalized = " ".join(str(value or "").strip().lower().split())
    return _COUNTRY_ALIASES.get(normalized, normalized)


class AcquisitionService:
    def __init__(
        self,
        task_repository: TaskRepository,
        lead_repository: LeadRepository,
        search_provider: SearchProvider | None = None,
        audit_repository: AuditEventRepository | None = None,
        website_reader=None,
        website_workers: int = 8,
        website_page_limit: int = 3,
        external_source_limit: int = 1,
    ):
        self._tasks = task_repository
        self._leads = lead_repository
        self._search = search_provider
        self._audit = audit_repository
        self._website_reader = website_reader
        if website_page_limit <= 0 or external_source_limit < 0:
            raise ValueError("website page limits must be valid")
        self._website_page_limit = website_page_limit
        self._external_source_limit = external_source_limit
        if website_workers <= 0:
            raise ValueError("website_workers must be positive")
        self._website_workers = website_workers
        # Search rounds often return the same domains. Cache only successful
        # public-page extraction so changing criteria reuses evidence without
        # hiding a transient fetch failure.
        self._website_enrichment_cache: dict[str, tuple[LeadRecord, ...]] = {}

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
        website_sources = self._same_domain_sources(lead)
        signals: dict[str, int] = {}
        if "product_match" in weights:
            terms = tuple(
                term.strip().lower()
                for term in configured_research_terms(criteria)
                if term.strip()
            )
            searchable = " ".join(source[1] for source in website_sources).lower()
            matched_terms = sum(
                self._term_in_evidence(term, searchable) for term in terms
            )
            if matched_terms:
                signals["product_match"] = max(
                    1,
                    round(weights["product_match"] * matched_terms / len(terms)),
                )
        if "email_quality" in weights and lead.emails:
            signals["email_quality"] = weights["email_quality"]
        if "evidence_quality" in weights and website_sources:
            signals["evidence_quality"] = weights["evidence_quality"]
        if "market_match" in weights and lead.country:
            markets = {value.strip().lower() for value in criteria.countries if value.strip()}
            if not markets or lead.country.lower() in markets:
                signals["market_match"] = weights["market_match"]
        return signals

    @staticmethod
    def _website_sources(lead: CleanLead) -> tuple[tuple[str, str], ...]:
        return tuple(source for source in lead.sources if not is_search_source(source[0]))

    @classmethod
    def _same_domain_sources(cls, lead: CleanLead) -> tuple[tuple[str, str], ...]:
        domain = canonical_website_domain(lead.domain)
        return tuple(
            source
            for source in cls._website_sources(lead)
            if canonical_website_domain(source[0]) == domain
        )

    @classmethod
    def has_product_evidence(cls, lead: CleanLead, criteria: AcquisitionCriteria) -> bool:
        """Accept direct product evidence or a credible industry-use signal."""
        terms = tuple(
            variant.strip().lower()
            for term in configured_product_evidence_terms(criteria)
            for variant in search_term_variants(term)
            if variant.strip()
        )
        searchable = " ".join(
            source[1] for source in cls._same_domain_sources(lead)
        ).lower()
        if not searchable or not terms:
            return False
        if any(
            cls._term_in_evidence(term, searchable) for term in terms
        ):
            return True
        # A company can be a plausible buyer even when its site does not name
        # the exact purchased part. Require both a configured target industry
        # and a manufacturing/use-context signal before accepting that case.
        industries = tuple(
            variant.strip().lower()
            for industry in criteria.industries
            for variant in search_term_variants(industry)
            if variant.strip()
        )
        context_terms = (
            "manufacturer", "manufacturing", "production", "components",
            "oem", "engineering", "factory", "automotive", "electronics",
            "medical", "appliance", "industrial",
        )
        return bool(industries) and any(
            cls._term_in_evidence(term, searchable) for term in industries
        ) and any(
            cls._term_in_evidence(term, searchable) for term in context_terms
        )

    @staticmethod
    def _term_in_evidence(term: str, text: str) -> bool:
        """Match configurable terms without accepting English substring false positives."""
        normalized_term = " ".join(term.lower().split())
        normalized_text = " ".join(text.lower().split())
        if not normalized_term or not normalized_text:
            return False
        if re.search(r"[a-z0-9]", normalized_term):
            variants = {normalized_term}
            if normalized_term.endswith("s"):
                variants.add(normalized_term[:-1])
            for variant in variants:
                tokens = variant.split()
                pattern_body = r"\s+".join(re.escape(token) for token in tokens)
                pattern = rf"(?<![a-z0-9]){pattern_body}s?(?![a-z0-9])"
                if re.search(pattern, normalized_text) is not None:
                    return True
            return False
        return normalized_term in normalized_text

    @staticmethod
    def _qualify(
        results: list[AssessedLead], criteria: AcquisitionCriteria
    ) -> list[AssessedLead]:
        """按任务配置筛选可交付客户，同时保留所有候选及淘汰原因。"""
        evaluated: list[AssessedLead] = []
        target_countries = {
            _country_key(value)
            for value in criteria.countries
            if _country_key(value)
        }
        for item in results:
            reasons: list[str] = []
            if criteria.require_public_email and not item.lead.emails:
                reasons.append("missing_public_email")
            # Target market is a hard business boundary: public-email records
            # without confirmed country evidence stay in the candidate archive,
            # but must never enter the sendable customer pool.
            if target_countries:
                lead_country = _country_key(item.lead.country)
                if not lead_country:
                    reasons.append("missing_target_country")
                elif lead_country not in target_countries:
                    reasons.append("country_not_target")
            evaluated.append(
                replace(
                    item,
                    qualified=not reasons,
                    rejection_reasons=tuple(dict.fromkeys(reasons)),
                )
            )

        # 合格判断只负责判断“是否符合客户条件”，不再截断为发送数量。
        # 每日发送上限属于发送环节；其余合格客户必须保留在本地数据库，
        # 作为后续待联系客户，避免一次搜索结果被无声丢弃。
        return evaluated

    def list_leads(self, task_id: str) -> list[AssessedLead]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        current = self._leads.list_assessments(task_id)
        sanitized = [
            replace(
                item,
                lead=replace(
                    item.lead,
                    company_name=clean_company_name(
                        item.lead.company_name, item.lead.domain
                    ),
                    emails=tuple(
                        email for email in item.lead.emails if is_plausible_email(email)
                    ),
                    sources=tuple(
                        source
                        for source in item.lead.sources
                        if source[0].strip() and is_credible_source_excerpt(source[1])
                    ),
                ),
            )
            for item in current
        ]
        if sanitized != current:
            self._leads.save_assessments(task_id, sanitized)
            current = sanitized
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
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        website = f"https://{domain}"
        fetch_pages = getattr(website_reader, "fetch_contact_pages", None)
        documents = (
            self._fetch_contact_pages(
                fetch_pages,
                website,
                task.criteria,
                allow_external_sources=True,
            )
            if fetch_pages is not None
            else (website_reader.fetch(website),)
        )
        public_emails = tuple(
            email
            for document in documents
            for email in getattr(document, "public_emails", ())
        )
        records = [
            LeadRecord(
                assessed.lead.company_name,
                website,
                "",
                assessed.lead.country,
                source_url,
                source_excerpt,
            )
            for source_url, source_excerpt in assessed.lead.sources
            if is_search_source(source_url)
        ]
        if not records:
            records.append(
                LeadRecord(
                    assessed.lead.company_name,
                    website,
                    "",
                    assessed.lead.country,
                )
            )
        records.extend(
            LeadRecord(
                assessed.lead.company_name,
                website,
                "",
                assessed.lead.country,
                document.url,
                self._document_excerpt(document),
            )
            for document in documents
            if self._document_excerpt(document)
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
        score = assessed.score
        if score.total == 0:
            score = score_lead(
                updated_lead,
                DEFAULT_QUALIFICATION_WEIGHTS,
                self._derive_signals(updated_lead, task_id, DEFAULT_QUALIFICATION_WEIGHTS),
            )
        result = self._qualify(
            [AssessedLead(updated_lead, score)],
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
        if self._audit is not None and not actor.strip():
            raise ValueError("audit actor is required")
        assessed = next(
            (item for item in self.list_leads(task_id) if item.lead.domain == domain), None
        )
        if assessed is None:
            raise KeyError(f"Lead not found: {domain}")
        updated_lead = assessed.lead.transition_to(target)
        updated = AssessedLead(updated_lead, assessed.score)
        audit_event = (
            AuditEvent.status_change(
                entity_type="lead",
                entity_id=f"{task_id}:{domain}",
                action="transition",
                actor=actor,
                from_status=assessed.lead.status.value,
                to_status=target.value,
                note=note,
            )
            if self._audit is not None
            else None
        )
        self._leads.save_assessments(
            task_id,
            [item if item.lead.domain != domain else updated for item in self.list_leads(task_id)],
        )
        if audit_event is not None:
            self._audit.save(audit_event)
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
        progress=None,
        search_round: int = 0,
    ) -> list[AssessedLead]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if self._search is None:
            raise RuntimeError("Search provider is not configured")
        # Keep repeated rounds productive: the search provider exposes bounded
        # query slices, while the local database owns durable deduplication.
        # Synchronize known domains before each round so later searches move
        # past already-seen companies instead of overwriting them again.
        remember_domains = getattr(self._search, "remember_domains", None)
        if callable(remember_domains):
            remember_domains(
                {
                    item.lead.domain
                    for item in self._leads.list_assessments(task_id)
                    if item.lead.domain
                }
            )
        if progress:
            progress("searching")
        search_pass = getattr(self._search, "search_round", None)
        records = (
            search_pass(task.criteria, search_round)
            if callable(search_pass)
            else self._search.search(task.criteria)
        )
        if progress:
            progress(
                "enriching",
                candidate_count=len(records),
                website_count=sum(bool(record.website) for record in records),
            )
        records = self._enrich_search_records(task_id, records)
        if progress:
            progress(
                "assessing",
                candidate_count=len(records),
                website_count=len({record.website for record in records if record.website}),
                public_email_count=sum(bool(record.email) for record in records),
            )
        results = self.assess_leads(task_id, records, weights, signals_by_domain)
        if progress:
            progress(
                "completed",
                candidate_count=len(results),
                website_count=sum(bool(item.lead.domain) for item in results),
                public_email_count=sum(bool(item.lead.emails) for item in results),
                qualified_count=sum(item.qualified for item in results),
            )
        return results

    def enrich_records(self, task_id: str, records: list[LeadRecord]) -> list[LeadRecord]:
        """核验外部导入的官网并补充真实页面、公开邮箱证据。"""
        return self._enrich_search_records(task_id, records)

    def _enrich_search_records(self, task_id: str, records: list[LeadRecord]) -> list[LeadRecord]:
        """从候选官网提取公开邮箱；失败时保留原始候选，不猜测联系方式。"""
        if self._website_reader is None:
            return records
        enriched = list(records)
        unique_records: list[LeadRecord] = []
        fetched: set[str] = set()
        for record in records:
            parsed = urlparse(record.website.strip())
            domain = (parsed.hostname or "").lower().removeprefix("www.")
            if domain and domain not in fetched:
                fetched.add(domain)
                cached = self._website_enrichment_cache.get(domain)
                if cached is not None:
                    enriched.extend(cached)
                else:
                    unique_records.append(record)
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        with ThreadPoolExecutor(max_workers=self._website_workers) as executor:
            for record, additions in zip(unique_records, executor.map(
                lambda record: self._enrich_one_search_record(record, task.criteria),
                unique_records,
            )):
                enriched.extend(additions)
                domain = (urlparse(record.website.strip()).hostname or "").lower().removeprefix("www.")
                if domain and additions:
                    self._website_enrichment_cache[domain] = tuple(additions)
        return enriched

    def _enrich_one_search_record(
        self, record: LeadRecord, criteria: AcquisitionCriteria
    ) -> list[LeadRecord]:
        try:
            fetch_pages = getattr(self._website_reader, "fetch_contact_pages", None)
            documents = (
                self._fetch_contact_pages(
                    fetch_pages,
                    record.website.strip(),
                    criteria,
                    allow_external_sources=True,
                )
                if fetch_pages is not None
                else (self._website_reader.fetch(record.website.strip()),)
            )
        except Exception:
            return []
        additions: list[LeadRecord] = []
        for document in documents:
            excerpt = self._document_excerpt(document)
            if excerpt:
                additions.append(
                    LeadRecord(
                        company_name=record.company_name,
                        website=record.website,
                        country=record.country,
                        source_url=document.url,
                        source_excerpt=excerpt,
                    )
                )
        for document in documents:
            for public_email in getattr(document, "public_emails", ()):
                additions.append(
                    LeadRecord(
                        company_name=record.company_name,
                        website=record.website,
                        email=public_email.address,
                        country=record.country,
                        source_url=public_email.source_url,
                        source_excerpt=public_email.excerpt,
                    )
                )
        return additions

    def _fetch_contact_pages(self, fetch_pages, website, criteria, allow_external_sources):
        kwargs = {
            "max_pages": self._website_page_limit,
            "allow_external_sources": allow_external_sources,
            "max_external_pages": self._external_source_limit,
            "priority_terms": configured_research_terms(criteria),
        }
        try:
            return fetch_pages(website, **kwargs)
        except TypeError:
            kwargs.pop("priority_terms")
            return fetch_pages(website, **kwargs)

    @staticmethod
    def _document_excerpt(document) -> str:
        """Persist a bounded, human-readable excerpt from a fetched public page."""
        title = " ".join(str(getattr(document, "title", "")).split())
        text = " ".join(str(getattr(document, "text", "")).split())
        if not title and not text:
            return ""
        if len(text) > 600:
            text = text[:600].rstrip() + "…"
        return " - ".join(value for value in (title, text) if value)
