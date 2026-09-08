"""本地 HTTP API 适配器，负责把应用用例暴露给前端。"""

from __future__ import annotations

import json
from urllib.parse import unquote, urlsplit

from src.application.acquisition_service import AcquisitionService
from src.application.email_review_service import EmailReviewService
from src.domain.lead import LeadRecord


class ApiApplication:
    def __init__(self, tasks, leads, research, drafts, acquisition=None):
        self._tasks = tasks
        self._leads = leads
        self._research = research
        self._drafts = drafts
        self._acquisition = acquisition or AcquisitionService(tasks, leads)
        self._reviews = EmailReviewService(drafts)

    def handle(self, method: str, path: str, body=None) -> tuple[int, dict]:
        try:
            segments = [unquote(item) for item in urlsplit(path).path.split("/") if item]
            if method == "GET" and segments == ["api", "health"]:
                return 200, {"status": "ok"}
            if method == "GET" and segments == ["api", "tasks"]:
                return self._task_list()
            if (
                method == "POST"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "assess"
            ):
                return self._assess_leads(segments[2], self._parse_body(body))
            if (
                method == "GET"
                and len(segments) == 5
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "leads"
            ):
                return self._lead_detail(segments[2], segments[4])
            if (
                method == "GET"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "leads"
            ):
                return self._lead_list(segments[2])
            if method == "GET" and len(segments) == 3 and segments[:2] == ["api", "drafts"]:
                return self._draft_detail(segments[2])
            if method == "POST" and len(segments) == 4 and segments[:2] == ["api", "drafts"]:
                return self._review(segments[2], segments[3], self._parse_body(body))
            return 404, {"error": "Route not found"}
        except KeyError as error:
            return 404, {"error": str(error).strip("'")}
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            return 400, {"error": str(error)}

    def _lead_list(self, task_id: str) -> tuple[int, dict]:
        self._require_task(task_id)
        items = [self._assessed(item) for item in self._leads.list_assessments(task_id)]
        return 200, {"items": items}

    def _task_list(self) -> tuple[int, dict]:
        return 200, {
            "items": [
                {"id": task.id, "name": task.name, "status": task.status.value}
                for task in self._tasks.list()
            ]
        }

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

    def _lead_detail(self, task_id: str, domain: str) -> tuple[int, dict]:
        self._require_task(task_id)
        assessed = next(
            (item for item in self._leads.list_assessments(task_id) if item.lead.domain == domain),
            None,
        )
        if assessed is None:
            raise KeyError(f"Lead not found: {domain}")
        report = self._research.get(task_id, domain)
        return 200, {
            "lead": self._lead(assessed.lead),
            "score": self._score(assessed.score),
            "research": self._research_result(report) if report else None,
        }

    def _draft_detail(self, draft_id: str) -> tuple[int, dict]:
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise KeyError(f"Draft not found: {draft_id}")
        return 200, self._draft(draft)

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
    def _lead(lead) -> dict:
        return {
            "company_name": lead.company_name,
            "domain": lead.domain,
            "website": f"https://{lead.domain}" if lead.domain else "",
            "emails": lead.emails,
            "country": lead.country,
            "quality": lead.quality,
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
