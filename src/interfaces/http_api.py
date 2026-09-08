"""本地 HTTP API 适配器，负责把应用用例暴露给前端。"""

from __future__ import annotations

import json
from urllib.parse import unquote, urlsplit

from src.application.acquisition_service import AcquisitionService
from src.application.email_review_service import EmailReviewService
from src.domain.audit_event import AuditEvent
from src.domain.lead import LeadRecord, LeadStatus
from src.domain.research_run import ResearchRun
from src.domain.sender_profile import SenderProfile
from src.domain.task import AcquisitionCriteria, TaskStatus


class ApiApplication:
    def __init__(
        self,
        tasks,
        leads,
        research,
        drafts,
        acquisition=None,
        email_drafts=None,
        translation=None,
        audit=None,
        research_execution=None,
        research_runs=None,
        research_queue=None,
    ):
        self._tasks = tasks
        self._leads = leads
        self._research = research
        self._drafts = drafts
        self._acquisition = acquisition or AcquisitionService(tasks, leads, audit_repository=audit)
        self._email_drafts = email_drafts
        self._translation = translation
        self._audit = audit
        self._research_execution = research_execution
        self._research_runs_repository = research_runs
        self._research_queue = research_queue
        self._reviews = EmailReviewService(drafts, audit)

    def handle(self, method: str, path: str, body=None) -> tuple[int, dict]:
        try:
            segments = [unquote(item) for item in urlsplit(path).path.split("/") if item]
            if method == "GET" and segments == ["api", "health"]:
                return 200, {"status": "ok"}
            if method == "GET" and segments == ["api", "tasks"]:
                return self._task_list()
            if method == "POST" and segments == ["api", "tasks"]:
                return self._create_task(self._parse_body(body))
            if (
                method == "POST"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "transition"
            ):
                return self._transition_task(segments[2], self._parse_body(body))
            if (
                method == "POST"
                and len(segments) == 6
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "leads"
                and segments[5] == "draft"
            ):
                return self._create_draft(
                    segments[2], segments[4], self._parse_body(body)
                )
            if (
                method == "POST"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "sender-profile"
            ):
                return self._update_sender_profile(segments[2], self._parse_body(body))
            if (
                method == "POST"
                and len(segments) == 6
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "leads"
                and segments[5] == "contact"
            ):
                return self._update_contact(
                    segments[2], segments[4], self._parse_body(body)
                )
            if (
                method == "POST"
                and len(segments) == 6
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "leads"
                and segments[5] == "transition"
            ):
                return self._transition_lead(segments[2], segments[4], self._parse_body(body))
            if (
                method == "POST"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "assess"
            ):
                return self._assess_leads(segments[2], self._parse_body(body))
            if (
                method == "POST"
                and len(segments) == 6
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "leads"
                and segments[5] == "research"
            ):
                return self._research_lead(segments[2], segments[4], self._parse_body(body))
            if (
                method == "GET"
                and len(segments) == 5
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "leads"
            ):
                return self._lead_detail(segments[2], segments[4])
            if (
                method == "GET"
                and len(segments) == 6
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "leads"
                and segments[5] == "audit-events"
            ):
                return self._lead_audit_events(segments[2], segments[4])
            if (
                method == "GET"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "leads"
            ):
                return self._lead_list(segments[2])
            if method == "GET" and len(segments) == 3 and segments[:2] == ["api", "drafts"]:
                return self._draft_detail(segments[2])
            if (
                method == "GET"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "audit-events"
            ):
                return self._task_audit_events(segments[2])
            if (
                method == "GET"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "research-runs"
            ):
                return self._research_runs(segments[2])
            if (
                method == "GET"
                and len(segments) == 4
                and segments[:2] == ["api", "drafts"]
                and segments[3] == "audit-events"
            ):
                return self._draft_audit_events(segments[2])
            if (
                method == "POST"
                and len(segments) == 4
                and segments[:2] == ["api", "drafts"]
                and segments[3] == "translate"
            ):
                return self._translate_draft(segments[2], self._parse_body(body))
            if method == "POST" and len(segments) == 4 and segments[:2] == ["api", "drafts"]:
                return self._review(segments[2], segments[3], self._parse_body(body))
            return 404, {"error": "Route not found"}
        except KeyError as error:
            return 404, {"error": str(error).strip("'")}
        except RuntimeError as error:
            return 503, {"error": str(error)}
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            return 400, {"error": str(error)}

    def _lead_list(self, task_id: str) -> tuple[int, dict]:
        self._require_task(task_id)
        items = [self._assessed(item) for item in self._leads.list_assessments(task_id)]
        return 200, {"items": items}

    def _task_list(self) -> tuple[int, dict]:
        return 200, {"items": [self._task(task) for task in self._tasks.list()]}

    def _create_task(self, body: dict) -> tuple[int, dict]:
        criteria_data = body.get("criteria", {})
        if not isinstance(criteria_data, dict):
            raise ValueError("criteria must be an object")
        criteria = AcquisitionCriteria(
            product=str(criteria_data.get("product", "")),
            countries=tuple(str(item) for item in criteria_data.get("countries", [])),
            industries=tuple(str(item) for item in criteria_data.get("industries", [])),
            customer_types=tuple(
                str(item) for item in criteria_data.get("customer_types", [])
            ),
            language=str(criteria_data.get("language", "English")),
            daily_limit=int(criteria_data.get("daily_limit", 10)),
            keywords=tuple(str(item) for item in criteria_data.get("keywords", [])),
        )
        sender_data = body.get("sender_profile", {})
        if not isinstance(sender_data, dict):
            raise ValueError("sender_profile must be an object")
        sender_profile = SenderProfile(
            company_name=str(sender_data.get("company_name", "")),
            contact_name=str(sender_data.get("contact_name", "")),
            position=str(sender_data.get("position", "")),
        )
        task = self._acquisition.create_task(str(body.get("name", "")), criteria, sender_profile)
        return 201, self._task(task)

    def _assess_leads(self, task_id: str, body: dict) -> tuple[int, dict]:
        """接收外部搜索适配器的原始记录，统一清洗、评分并持久化。"""
        records = [
            LeadRecord(
                company_name=item.get("company_name", ""),
                website=item.get("website", ""),
                email=item.get("email", ""),
                country=item.get("country", ""),
                source_url=item.get("source_url", ""),
                source_excerpt=item.get("source_excerpt", ""),
            )
            for item in body.get("records", [])
            if isinstance(item, dict)
        ]
        weights = body.get("weights", {})
        signals_by_domain = body.get("signals_by_domain", {})
        if not isinstance(weights, dict) or not isinstance(signals_by_domain, dict):
            raise ValueError("weights and signals_by_domain must be objects")
        results = self._acquisition.assess_leads(
            task_id,
            records,
            {str(key): int(value) for key, value in weights.items()},
            {
                str(domain): {str(key): int(value) for key, value in signals.items()}
                for domain, signals in signals_by_domain.items()
                if isinstance(signals, dict)
            },
        )
        return 200, {"items": [self._assessed(item) for item in results]}

    def _research_lead(self, task_id: str, domain: str, body: dict) -> tuple[int, dict]:
        if self._research_execution is None:
            raise RuntimeError("research execution service is not configured")
        self._require_task(task_id)
        assessed = next(
            (item for item in self._leads.list_assessments(task_id) if item.lead.domain == domain),
            None,
        )
        if assessed is None:
            raise KeyError(f"Lead not found: {domain}")
        source_url = str(body.get("source_url", "")).strip()
        if not source_url:
            raise ValueError("source_url is required")
        weights = body.get("weights", {})
        if not isinstance(weights, dict):
            raise ValueError("weights must be an object")
        normalized_weights = {str(key): int(value) for key, value in weights.items()}
        max_attempts = int(body.get("max_attempts", 2))
        request_key = str(body.get("idempotency_key", "")).strip()
        if self._research_queue is not None:
            run = self._research_queue.submit(
                task_id,
                assessed.lead,
                source_url,
                normalized_weights,
                max_attempts=max_attempts,
                request_key=request_key,
            )
            return 202, {"run": self._research_run(run)}
        result = self._research_execution.execute(
            task_id, assessed.lead, source_url, normalized_weights, max_attempts=max_attempts
        )
        return 200, {
            "run": self._research_run(result.run),
            "research": self._research_result(result.assessment.research),
            "score": self._score(result.assessment.score),
        }

    def _research_runs(self, task_id: str) -> tuple[int, dict]:
        self._require_task(task_id)
        if self._research_runs_repository is None:
            raise RuntimeError("research run repository is not configured")
        return 200, {
            "items": [
                self._research_run(run)
                for run in self._research_runs_repository.list_for_task(task_id)
            ]
        }

    def _create_draft(self, task_id: str, domain: str, body: dict) -> tuple[int, dict]:
        if self._email_drafts is None:
            raise RuntimeError("email draft provider is not configured")
        self._require_task(task_id)
        assessed = next(
            (item for item in self._leads.list_assessments(task_id) if item.lead.domain == domain),
            None,
        )
        if assessed is None:
            raise KeyError(f"Lead not found: {domain}")
        research = self._research.get(task_id, domain)
        if research is None:
            raise ValueError("research report is required before drafting")
        template = str(body.get("template", ""))
        product = str(body.get("product", ""))
        draft = self._email_drafts.generate(
            task_id,
            assessed.lead,
            research,
            template,
            product,
            self._tasks.get(task_id).sender_profile,
        )
        self._drafts.save(draft)
        return 201, self._draft(draft)

    def _update_contact(self, task_id: str, domain: str, body: dict) -> tuple[int, dict]:
        result = self._acquisition.update_contact(
            task_id,
            domain,
            str(body.get("email", "")),
            str(body.get("source_url", "")),
            str(body.get("source_excerpt", "")),
        )
        return 200, self._assessed(result)

    def _update_sender_profile(self, task_id: str, body: dict) -> tuple[int, dict]:
        profile = SenderProfile(
            company_name=str(body.get("company_name", "")),
            contact_name=str(body.get("contact_name", "")),
            position=str(body.get("position", "")),
        )
        return 200, self._task(self._acquisition.update_sender_profile(task_id, profile))

    def _transition_lead(self, task_id: str, domain: str, body: dict) -> tuple[int, dict]:
        try:
            target = LeadStatus(str(body.get("status", "")))
        except ValueError as error:
            raise ValueError("invalid lead status") from error
        return 200, self._assessed(self._acquisition.transition_lead(
            task_id, domain, target, str(body.get("actor", "")), str(body.get("note", ""))
        ))

    def _lead_audit_events(self, task_id: str, domain: str) -> tuple[int, dict]:
        self._require_task(task_id)
        self._lead_detail(task_id, domain)
        entity_id = f"{task_id}:{domain}"
        events = self._audit.list_for_entity("lead", entity_id) if self._audit else []
        return 200, {"items": [self._audit_event(event) for event in events]}

    def _transition_task(self, task_id: str, body: dict) -> tuple[int, dict]:
        try:
            target = TaskStatus(str(body.get("status", "")))
        except ValueError as error:
            raise ValueError("invalid task status") from error
        return 200, self._task(self._acquisition.transition_task(
            task_id,
            target,
            str(body.get("actor", "")),
            str(body.get("note", "")),
        ))

    def _task_audit_events(self, task_id: str) -> tuple[int, dict]:
        self._require_task(task_id)
        events = self._audit.list_for_entity("acquisition_task", task_id) if self._audit else []
        return 200, {"items": [self._audit_event(event) for event in events]}

    def _lead_detail(self, task_id: str, domain: str) -> tuple[int, dict]:
        self._require_task(task_id)
        assessed = next(
            (item for item in self._leads.list_assessments(task_id) if item.lead.domain == domain),
            None,
        )
        if assessed is None:
            raise KeyError(f"Lead not found: {domain}")
        report = self._research.get(task_id, domain)
        draft = (
            self._drafts.latest_for_lead(task_id, domain)
            if hasattr(self._drafts, "latest_for_lead")
            else None
        )
        return 200, {
            "lead": self._lead(assessed.lead),
            "score": self._score(assessed.score),
            "research": self._research_result(report) if report else None,
            "draft": self._draft(draft) if draft else None,
        }

    def _draft_detail(self, draft_id: str) -> tuple[int, dict]:
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise KeyError(f"Draft not found: {draft_id}")
        return 200, self._draft(draft)

    def _draft_audit_events(self, draft_id: str) -> tuple[int, dict]:
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise KeyError(f"Draft not found: {draft_id}")
        events = self._audit.list_for_entity("email_draft", draft_id) if self._audit else []
        return 200, {"items": [self._audit_event(event) for event in events]}

    def _translate_draft(self, draft_id: str, body: dict) -> tuple[int, dict]:
        if self._translation is None:
            raise RuntimeError("translation provider is not configured")
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise KeyError(f"Draft not found: {draft_id}")
        return 200, self._translation.preview(draft, str(body.get("target_language", "zh-CN")))

    def _review(self, draft_id: str, action: str, body: dict) -> tuple[int, dict]:
        reviewer = body.get("reviewer", "")
        if action == "approve":
            draft = self._reviews.approve(draft_id, reviewer)
        elif action == "request-revision":
            draft = self._reviews.request_revision(draft_id, reviewer, body.get("note", ""))
        elif action == "reject":
            draft = self._reviews.reject(draft_id, reviewer, body.get("note", ""))
        else:
            return 404, {"error": "Review action not found"}
        return 200, self._draft(draft)

    def _require_task(self, task_id: str) -> None:
        if self._tasks.get(task_id) is None:
            raise KeyError(f"Task not found: {task_id}")

    @staticmethod
    def _parse_body(body) -> dict:
        if body is None:
            return {}
        data = json.loads(body) if isinstance(body, str) else body
        if not isinstance(data, dict):
            raise ValueError("request body must be an object")
        return data

    @staticmethod
    def _task(task) -> dict:
        return {
            "id": task.id,
            "name": task.name,
            "status": task.status.value,
            "criteria": {
                "product": task.criteria.product,
                "language": task.criteria.language,
            },
            "sender_profile": {
                "company_name": task.sender_profile.company_name,
                "contact_name": task.sender_profile.contact_name,
                "position": task.sender_profile.position,
            },
        }

    @staticmethod
    def _lead(lead) -> dict:
        return {
            "company_name": lead.company_name,
            "domain": lead.domain,
            "website": f"https://{lead.domain}" if lead.domain else "",
            "emails": lead.emails,
            "country": lead.country,
            "quality": lead.quality,
            "status": lead.status.value,
            "flags": lead.flags,
            "sources": lead.sources,
        }

    @staticmethod
    def _score(score) -> dict:
        return {"total": score.total, "priority": score.priority, "breakdown": score.breakdown}

    @staticmethod
    def _assessed(item) -> dict:
        return {"lead": ApiApplication._lead(item.lead), "score": ApiApplication._score(item.score)}

    @staticmethod
    def _research_result(report) -> dict:
        return {
            "company_name": report.company_name,
            "business_summary": report.business_summary,
            "customer_type": report.customer_type.value,
            "products": report.products,
            "country": report.country,
            "confidence": report.confidence,
            "evidence_url": report.evidence_url,
            "evidence_status": report.evidence_status.value,
        }

    @staticmethod
    def _research_run(run: ResearchRun) -> dict:
        return {
            "id": run.id,
            "task_id": run.task_id,
            "domain": run.domain,
            "status": run.status.value,
            "step": run.step.value,
            "attempts": run.attempts,
            "error": run.error,
        }

    @staticmethod
    def _draft(draft) -> dict:
        return {
            "id": draft.id,
            "task_id": draft.task_id,
            "lead_domain": draft.lead_domain,
            "recipient_email": draft.recipient_email,
            "subject": draft.subject,
            "body": draft.body,
            "evidence_urls": draft.evidence_urls,
            "status": draft.status.value,
            "reviewed_by": draft.reviewed_by,
            "review_note": draft.review_note,
        }

    @staticmethod
    def _audit_event(event: AuditEvent) -> dict:
        return {
            "id": event.id,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "action": event.action,
            "actor": event.actor,
            "from_status": event.from_status,
            "to_status": event.to_status,
            "note": event.note,
            "occurred_at": event.occurred_at,
        }
