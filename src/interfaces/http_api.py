"""本地 HTTP API 适配器，负责把应用用例暴露给前端。"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlsplit

from src.application.acquisition_service import (
    DEFAULT_QUALIFICATION_WEIGHTS,
    AcquisitionService,
    _country_key,
)
from src.application.email_review_service import EmailReviewService
from src.application.search_health import classify_search_error
from src.domain.audit_event import AuditEvent
from src.domain.custom_research import (
    BusinessOffering,
    ResearchFieldDefinition,
    ResearchFieldType,
    ResearchFieldValue,
)
from src.domain.discovery_run import DiscoveryRun
from src.domain.email_send import EmailSendAttempt
from src.domain.follow_up_task import FollowUpTask
from src.domain.inbound_email import InboundEmail
from src.domain.lead import (
    LeadRecord,
    LeadStatus,
    canonical_source_url,
    canonical_website_domain,
    clean_company_name,
    evidence_level,
    identity_consistency,
    is_search_source,
)
from src.domain.reply_analysis import ReplyAnalysis
from src.domain.research_run import ResearchRun
from src.domain.send_safety import SendPolicy
from src.domain.sender_profile import SenderProfile
from src.domain.task import AcquisitionCriteria, TaskStatus, effective_candidate_limit
from src.infrastructure.google_search_provider import GoogleSearchProvider, SearchProviderError


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
        discovery_queue=None,
        discovery_runs=None,
        mailbox=None,
        mailbox_sync=None,
        inbound_emails=None,
        reply_analysis=None,
        send_safety=None,
        email_send=None,
        follow_up_tasks=None,
        reply_drafts=None,
        website_reader=None,
        sending_enabled=False,
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
        self._discovery_queue = discovery_queue
        self._discovery_runs_repository = discovery_runs
        self._mailbox = mailbox
        self._mailbox_sync = mailbox_sync
        self._inbound_emails = inbound_emails
        self._reply_analysis = reply_analysis
        self._send_safety = send_safety
        self._email_send = email_send
        self._follow_up_tasks = follow_up_tasks
        self._reply_drafts = reply_drafts
        self._website_reader = website_reader
        self._sending_enabled = sending_enabled
        self._reviews = EmailReviewService(drafts, audit)
        self._auto_draft_executor = ThreadPoolExecutor(max_workers=2)
        self._auto_draft_jobs = {}

    def handle(self, method: str, path: str, body=None) -> tuple[int, dict]:
        try:
            segments = [unquote(item) for item in urlsplit(path).path.split("/") if item]
            if method == "GET" and segments == ["api", "health"]:
                return 200, {"status": "ok"}
            if method == "GET" and segments == ["api", "ready"]:
                return self._ready()
            if method == "GET" and segments == ["api", "database", "overview"]:
                task_id = parse_qs(urlsplit(path).query).get("task_id", [""])[0]
                return self._database_overview(task_id)
            if method == "GET" and segments == ["api", "database", "export"]:
                task_id = parse_qs(urlsplit(path).query).get("task_id", [""])[0]
                return self._database_export(task_id)
            if method == "GET" and segments == ["api", "mailbox", "status"]:
                return self._mailbox_status()
            if method == "GET" and segments == ["api", "settings", "status"]:
                return self._settings_status()
            if method == "POST" and segments == ["api", "mailbox", "test"]:
                return self._test_mailbox()
            if (
                method == "POST"
                and len(segments) == 4
                and segments[:2] == ["api", "drafts"]
                and segments[3] == "send-check"
            ):
                return self._send_check(segments[2], self._parse_body(body))
            if (
                method == "POST"
                and len(segments) == 4
                and segments[:2] == ["api", "drafts"]
                and segments[3] == "send"
            ):
                return self._send_draft(segments[2], self._parse_body(body))
            if (
                method == "GET"
                and len(segments) == 4
                and segments[:2] == ["api", "drafts"]
                and segments[3] == "send-attempts"
            ):
                return self._send_attempts(segments[2])
            if (
                method == "POST"
                and len(segments) == 5
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "mailbox"
                and segments[4] == "sync"
            ):
                return self._sync_mailbox(segments[2])
            if (
                method == "GET"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "mail-threads"
            ):
                return self._mail_threads(segments[2])
            if (
                method == "POST"
                and len(segments) == 5
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "reply-analyses"
                and segments[4] == "run"
            ):
                return self._analyze_replies(segments[2])
            if (
                method == "POST"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "reply-drafts"
            ):
                return self._create_reply_draft(segments[2], self._parse_body(body))
            if (
                method == "GET"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "reply-analyses"
            ):
                return self._reply_analyses(segments[2])
            if (
                method == "GET"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "follow-up-tasks"
            ):
                return self._follow_up_tasks_list(segments[2])
            if (
                method == "PATCH"
                and len(segments) == 5
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "follow-up-tasks"
            ):
                return self._follow_up_task_status(segments[2], segments[4], self._parse_body(body))
            if method == "GET" and segments == ["api", "tasks"]:
                return self._task_list()
            if method == "POST" and segments == ["api", "tasks"]:
                return self._create_task(self._parse_body(body))
            if (
                method == "POST"
                and len(segments) == 5
                and segments[:2] == ["api", "tasks"]
                and segments[3:5] == ["discover", "import"]
            ):
                return self._import_discovery(segments[2], self._parse_body(body))
            if (
                method == "POST"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "discover"
            ):
                return self._discover_leads(segments[2], self._parse_body(body))
            if (
                method == "GET"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "discovery-runs"
            ):
                return self._discovery_runs(segments[2])
            if (
                method == "PATCH"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "criteria"
            ):
                return self._update_criteria(segments[2], self._parse_body(body))
            if (
                method == "PATCH"
                and len(segments) == 7
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "leads"
                and segments[5] == "research-fields"
            ):
                return self._review_research_field(
                    segments[2], segments[4], segments[6], self._parse_body(body)
                )
            if (
                method == "POST"
                and len(segments) == 7
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "leads"
                and segments[5:7] == ["contacts", "discover"]
            ):
                return self._discover_public_contacts(segments[2], segments[4])
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
                return self._create_draft(segments[2], segments[4], self._parse_body(body))
            if (
                method == "GET"
                and len(segments) == 4
                and segments[:2] == ["api", "tasks"]
                and segments[3] == "drafts"
            ):
                return self._task_drafts(segments[2])
            if (
                method == "POST"
                and len(segments) == 5
                and segments[:2] == ["api", "tasks"]
                and segments[3:5] == ["drafts", "batch-send"]
            ):
                return self._batch_send_drafts(segments[2], self._parse_body(body))
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
                return self._update_contact(segments[2], segments[4], self._parse_body(body))
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
                compact = parse_qs(urlsplit(path).query).get("view", [""])[0] == "summary"
                return self._lead_list(segments[2], compact=compact)
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
        except SearchProviderError as error:
            health = classify_search_error(str(error))
            return 503, {
                "error": str(error),
                "code": "search_provider_unavailable",
                **health,
            }
        except RuntimeError as error:
            return 503, {"error": str(error)}
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            return 400, {"error": str(error)}

    def _lead_list(self, task_id: str, compact: bool = False) -> tuple[int, dict]:
        self._require_task(task_id)
        # Route reads through the application service so legacy records receive
        # the same evidence sanitization and qualification refresh as other reads.
        assessed = self._acquisition.list_leads(task_id)
        task = self._tasks.get(task_id)
        displayable_assessed = [
            item for item in assessed if self._is_displayable_lead(item.lead)
        ]
        self._schedule_missing_research(task_id, displayable_assessed)
        items = []
        effective_assessed = []
        contacted_emails = self._contacted_emails()
        research_by_domain = (
            self._research.list_for_task(task_id)
            if self._research is not None and hasattr(self._research, "list_for_task")
            else {}
        )
        for item in displayable_assessed:
            if item.lead.domain:
                report = research_by_domain.get(item.lead.domain)
                if not research_by_domain and self._research is not None:
                    report = self._research.get(task_id, item.lead.domain)
            else:
                report = None
            effective_item = item
            if report is not None and report.country and not item.lead.country:
                effective_item = replace(
                    item,
                    lead=replace(item.lead, country=report.country),
                )
            effective_item = AcquisitionService._qualify(
                [effective_item], task.criteria
            )[0]
            effective_assessed.append(effective_item)
            payload = self._assessed(effective_item, task.criteria, include_sources=not compact)
            payload["contacted"] = bool(
                set(email.lower() for email in effective_item.lead.emails)
                & contacted_emails
            )
            if report is not None:
                if report.company_name.strip():
                    payload["lead"]["company_name"] = clean_company_name(
                        report.company_name, item.lead.domain
                    )
                payload["lead"]["customer_type"] = report.customer_type.value
                if not payload["lead"]["country"] and report.country:
                    payload["lead"]["country"] = report.country
            items.append(payload)
        self._schedule_missing_drafts(task_id, effective_assessed)
        return 200, {
            "items": items,
            "summary": self._discovery_summary(task_id, effective_assessed),
        }

    @staticmethod
    def _is_displayable_lead(lead) -> bool:
        """Hide obvious legacy directory/institution records from customer views."""
        if not lead.domain:
            return True
        if not GoogleSearchProvider._is_candidate(
            f"https://{lead.domain}/", lead.company_name
        ):
            return False
        raw_name = " ".join(str(lead.company_name or "").split()).strip()
        cleaned_name = clean_company_name(raw_name, lead.domain)
        # If cleaning can only recover the domain, the collected title was a
        # search/article headline rather than a company identity. Keep it in
        # evidence, but keep it out of the customer database view.
        if raw_name and cleaned_name.casefold() == lead.domain.casefold() and raw_name.casefold() != lead.domain.casefold():
            return False
        noise_markers = (
            "weather", "calculator", "university", "tripadvisor", "hotels.com",
            "百度知道", "知乎", "站酷", "google trends", "google traductor",
            "wikipedia", "worldometer", "population", "quiz", "whois",
            # Search/article titles are evidence candidates, not company names.
            "list of ", "top 10", "car manufacturers", "car manufacturing",
            "precision machining for the ", "automotive moulding ",
            "import your car", "private label ", "industrial equipment",
            "manufacturing directory",
        )
        return not any(marker in raw_name.casefold() for marker in noise_markers)

    def _schedule_missing_drafts(self, task_id: str, assessed) -> None:
        """后台为已核验、合格且有邮箱的客户自动生成邮件草稿。"""
        if self._email_drafts is None or self._research is None:
            return
        task = self._tasks.get(task_id)
        if task is None:
            return
        product = str(getattr(task.criteria, "product", "") or "").strip()
        profile = task.sender_profile
        if not product or not all(
            str(getattr(profile, key, "") or "").strip()
            for key in ("company_name", "contact_name", "position")
        ):
            return
        self._auto_draft_jobs = {
            key: job for key, job in self._auto_draft_jobs.items() if not job.done()
        }
        for item in assessed:
            if not item.qualified or not item.lead.domain or not item.lead.emails:
                continue
            research = self._research.get(task_id, item.lead.domain)
            if research is None or self._drafts.latest_for_lead(task_id, item.lead.domain):
                continue
            key = (task_id, item.lead.domain)
            if key in self._auto_draft_jobs:
                continue
            self._auto_draft_jobs[key] = self._auto_draft_executor.submit(
                self._generate_auto_draft, task_id, item.lead, research, product, profile,
                str(getattr(task.criteria, "language", "English") or "English")
            )

    def _generate_auto_draft(self, task_id, lead, research, product, profile, language) -> None:
        try:
            draft = self._email_drafts.generate(
                task_id,
                lead,
                research,
                "Introduce {product} to {company} based on their published product range.",
                product,
                profile,
                language,
            )
            self._drafts.save(draft)
        except Exception:
            return None

    def _contacted_emails(self) -> set[str]:
        if self._email_send is None:
            return set()
        getter = getattr(self._email_send, "sent_recipient_emails", None)
        return {str(email).lower() for email in getter()} if callable(getter) else set()

    def _schedule_missing_research(self, task_id: str, assessed) -> None:
        """Queue website research for qualified records that lack a report."""
        if self._research_queue is None or self._research is None:
            return
        for item in assessed:
            if not item.qualified or not item.lead.domain:
                continue
            if self._research.get(task_id, item.lead.domain) is not None:
                continue
            source_url = next(
                (
                    url
                    for url, _excerpt in item.lead.sources
                    if url.strip() and not is_search_source(url)
                ),
                f"https://{item.lead.domain}",
            )
            try:
                self._research_queue.submit(
                    task_id,
                    item.lead,
                    source_url,
                    DEFAULT_QUALIFICATION_WEIGHTS,
                    request_key=f"auto-list:{task_id}:{item.lead.domain}",
                )
            except Exception:
                continue

    def _mailbox_status(self) -> tuple[int, dict]:
        return 200, {
            "provider": "ali_imap",
            "configured": self._mailbox is not None,
            "mode": "read_only",
            "sending_enabled": self._sending_enabled,
        }

    def _settings_status(self) -> tuple[int, dict]:
        """Expose integration readiness without returning credentials or account values."""
        config_path = Path(__file__).resolve().parents[2] / "config" / ".env"
        values = {}
        if config_path.exists():
            for raw_line in config_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip()
        return 200, {
            "deepseek_configured": bool(values.get("DEEPSEEK_API_KEY")),
            "ali_imap_configured": bool(values.get("ALI_IMAP_USERNAME") and values.get("ALI_IMAP_PASSWORD")),
            "ali_smtp_enabled": self._sending_enabled,
            "config_path": "config/.env",
        }

    def _test_mailbox(self) -> tuple[int, dict]:
        if self._mailbox is None:
            raise RuntimeError("Ali IMAP mailbox is not configured")
        self._mailbox.test_connection()
        return 200, {"connected": True, "read_only": True, "mail_read": False}

    def _ready(self) -> tuple[int, dict]:
        checks = {
            "task_repository": self._tasks is not None,
            "lead_repository": self._leads is not None,
            "research_repository": self._research is not None,
            "draft_repository": self._drafts is not None,
        }
        ready = all(checks.values())
        return (200 if ready else 503), {
            "status": "ready" if ready else "not_ready",
            "checks": checks,
        }

    def _send_check(self, draft_id: str, body: dict) -> tuple[int, dict]:
        if self._send_safety is None:
            raise RuntimeError("send safety service is not configured")
        policy = SendPolicy(
            blocked_emails=tuple(str(item) for item in body.get("blocked_emails", [])),
            blocked_domains=tuple(str(item) for item in body.get("blocked_domains", [])),
            daily_limit=int(body.get("daily_limit", 0)),
            sent_today=int(body.get("sent_today", 0)),
            contacted_recently=bool(body.get("contacted_recently", False)),
            recent_contact_days=int(body.get("recent_contact_days", 7)),
            attachment_names=tuple(str(item) for item in body.get("attachment_names", [])),
            attachment_sizes=tuple(
                (str(item.get("name", "")), int(item.get("size_bytes", 0)))
                for item in body.get("attachments", [])
                if isinstance(item, dict)
            ),
            max_attachments=int(body.get("max_attachments", 5)),
            max_attachment_bytes=int(body.get("max_attachment_bytes", 10 * 1024 * 1024)),
            max_total_attachment_bytes=int(
                body.get("max_total_attachment_bytes", 25 * 1024 * 1024)
            ),
            allowed_attachment_extensions=tuple(
                str(item)
                for item in body.get(
                    "allowed_attachment_extensions",
                    SendPolicy().allowed_attachment_extensions,
                )
            ),
        )
        result = self._send_safety.check(draft_id, policy)
        return 200, {
            "allowed": result.allowed,
            "requires_manual_confirmation": result.requires_manual_confirmation,
            "reasons": result.reasons,
            "sending_performed": False,
        }

    def _send_draft(self, draft_id: str, body: dict) -> tuple[int, dict]:
        if not self._sending_enabled:
            raise RuntimeError(
                "SMTP sending is disabled; enable it explicitly for a controlled test"
            )
        if self._email_send is None:
            raise RuntimeError("email send service is not configured")
        policy = SendPolicy(
            blocked_emails=tuple(str(item) for item in body.get("blocked_emails", [])),
            blocked_domains=tuple(str(item) for item in body.get("blocked_domains", [])),
            daily_limit=int(body.get("daily_limit", 0)),
            sent_today=int(body.get("sent_today", 0)),
            contacted_recently=bool(body.get("contacted_recently", False)),
            recent_contact_days=int(body.get("recent_contact_days", 7)),
            attachment_names=tuple(str(item) for item in body.get("attachment_names", [])),
            attachment_sizes=tuple(
                (str(item.get("name", "")), int(item.get("size_bytes", 0)))
                for item in body.get("attachments", [])
                if isinstance(item, dict)
            ),
            max_attachments=int(body.get("max_attachments", 5)),
            max_attachment_bytes=int(body.get("max_attachment_bytes", 10 * 1024 * 1024)),
            max_total_attachment_bytes=int(
                body.get("max_total_attachment_bytes", 25 * 1024 * 1024)
            ),
            allowed_attachment_extensions=tuple(
                str(item)
                for item in body.get(
                    "allowed_attachment_extensions",
                    SendPolicy().allowed_attachment_extensions,
                )
            ),
        )
        attempt = self._email_send.send(
            draft_id,
            policy,
            bool(body.get("confirmed", False)),
            str(body.get("recipient_email", "")),
            str(body.get("subject", "")),
            str(body.get("body", "")),
            str(body.get("idempotency_key", "")).strip(),
        )
        return 200, {"attempt": self._send_attempt(attempt), "sending_performed": True}

    def _send_attempts(self, draft_id: str) -> tuple[int, dict]:
        if self._email_send is None:
            raise RuntimeError("email send service is not configured")
        if self._drafts.get(draft_id) is None:
            raise KeyError(f"Draft not found: {draft_id}")
        return 200, {
            "items": [self._send_attempt(item) for item in self._email_send.list_attempts(draft_id)]
        }

    def _sync_mailbox(self, task_id: str) -> tuple[int, dict]:
        if self._mailbox_sync is None or self._mailbox is None:
            raise RuntimeError("Ali IMAP mailbox is not configured")
        self._require_task(task_id)
        result = self._mailbox_sync.sync(task_id, self._mailbox)
        return 200, {
            "fetched": result.fetched,
            "inserted": result.inserted,
            "skipped_duplicates": result.skipped_duplicates,
            "bounce_count": result.bounce_count,
        }

    def _mail_threads(self, task_id: str) -> tuple[int, dict]:
        self._require_task(task_id)
        if self._inbound_emails is None:
            raise RuntimeError("inbound email repository is not configured")
        messages = self._inbound_emails.list_for_task(task_id)
        items = [self._inbound_email(item) for item in messages]
        grouped = {}
        for item in items:
            grouped.setdefault(item["thread_key"], []).append(item)
        threads = [
            {
                "thread_key": key,
                "message_count": len(thread_items),
                "latest_received_at": thread_items[-1]["received_at"],
                "lead_domain": thread_items[-1]["lead_domain"],
                "items": thread_items,
            }
            for key, thread_items in grouped.items()
        ]
        return 200, {"items": items, "threads": threads}

    def _analyze_replies(self, task_id: str) -> tuple[int, dict]:
        if self._reply_analysis is None:
            raise RuntimeError("reply analysis service is not configured")
        self._require_task(task_id)
        result = self._reply_analysis.analyze_task(task_id)
        return 200, {
            "analyzed": result.analyzed,
            "reused": result.reused,
            "skipped_system_notifications": result.skipped_system_notifications,
            "items": [self._reply_analysis_item(item) for item in result.items],
        }

    def _create_reply_draft(self, task_id: str, body: dict) -> tuple[int, dict]:
        if self._reply_drafts is None:
            raise RuntimeError("reply draft provider is not configured")
        self._require_task(task_id)
        message_id = str(body.get("message_id", "")).strip()
        if not message_id or self._inbound_emails is None or self._reply_analysis is None:
            raise ValueError("message_id and reply analysis are required")
        message = self._inbound_emails.get_by_message_id(message_id)
        analysis = self._reply_analysis.get_by_message_id(message_id)
        if message is None or message.task_id != task_id:
            raise KeyError("inbound message not found")
        if analysis is None:
            raise ValueError("reply analysis is required before drafting")
        assessed = next(
            (
                item
                for item in self._leads.list_assessments(task_id)
                if item.lead.domain == message.lead_domain
            ),
            None,
        )
        if assessed is None:
            raise ValueError("lead is required before drafting")
        research = self._research.get(task_id, message.lead_domain)
        if research is None:
            raise ValueError("research report is required before drafting")
        task = self._tasks.get(task_id)
        draft = self._reply_drafts.generate(
            message, analysis, assessed.lead, research, task.sender_profile
        )
        self._drafts.save(draft)
        return 201, self._draft(draft)

    def _reply_analyses(self, task_id: str) -> tuple[int, dict]:
        self._require_task(task_id)
        if self._reply_analysis is None:
            raise RuntimeError("reply analysis service is not configured")
        analyses = self._reply_analysis.list_for_task(task_id)
        return 200, {"items": [self._reply_analysis_item(item) for item in analyses]}

    def _follow_up_tasks_list(self, task_id: str) -> tuple[int, dict]:
        self._require_task(task_id)
        if self._follow_up_tasks is None:
            raise RuntimeError("follow-up task service is not configured")
        return 200, {
            "items": [
                self._follow_up_task(item) for item in self._follow_up_tasks.list_for_task(task_id)
            ]
        }

    def _follow_up_task_status(
        self, task_id: str, follow_up_id: str, body: dict
    ) -> tuple[int, dict]:
        self._require_task(task_id)
        if self._follow_up_tasks is None:
            raise RuntimeError("follow-up task service is not configured")
        status = str(body.get("status", "")).strip()
        if not status:
            raise ValueError("status is required")
        item = self._follow_up_tasks.change_status(task_id, follow_up_id, status)
        return 200, {"item": self._follow_up_task(item)}

    def _task_list(self) -> tuple[int, dict]:
        return 200, {"items": [self._task(task) for task in self._tasks.list()]}

    def _database_overview(self, task_id: str = "") -> tuple[int, dict]:
        """为本地数据库页提供只读概览；不暴露原始凭据或内部错误。"""
        # 数据库页默认展示当前工作台任务，避免把历史测试任务和不同国家
        # 的客户混在一起。未传 task_id 时保留旧的聚合行为供兼容调用方使用。
        if task_id.strip():
            selected_task = self._tasks.get(task_id.strip())
            tasks = [selected_task] if selected_task is not None else []
        else:
            tasks = self._tasks.list()
        rows = []
        contacted_emails = self._contacted_emails()
        reply_domains = self._reply_domains()
        for task in tasks:
            assessments = self._acquisition.list_leads(task.id)
            assessments = [
                item for item in assessments if self._is_displayable_lead(item.lead)
            ]
            assessments = self._apply_research_country(task.id, task, assessments)
            target_countries = {
                _country_key(country)
                for country in task.criteria.countries
                if str(country).strip()
            }
            # 客户可见数据库不展示无法确认国家或不属于本次目标市场的记录。
            # 记录仍保存在本地候选库，后续重新核验后可再次进入展示范围。
            assessments = [
                item
                for item in assessments
                if item.lead.country.strip()
                and item.lead.country.casefold() != "unknown"
                and (
                    not target_countries
                    or _country_key(item.lead.country) in target_countries
                )
            ]
            eligible = [
                item for item in assessments
                if item.qualified
                and item.lead.emails
                and not (set(email.lower() for email in item.lead.emails) & contacted_emails)
                and "email_domain_mismatch" not in item.lead.flags
                and bool(item.lead.domain)
            ]
            today_domains = {
                item.lead.domain
                for item in sorted(eligible, key=lambda item: item.score.total, reverse=True)[
                    : task.criteria.daily_limit
                ]
            }
            for item in assessments:
                is_today_send = item.lead.domain in today_domains
                is_pending_contact = item.qualified and bool(item.lead.domain) and item.lead.domain not in today_domains
                is_contacted = bool(set(email.lower() for email in item.lead.emails) & contacted_emails)
                rows.append({
                    "task_name": task.name,
                    "task_id": task.id,
                    "lead": self._lead(item.lead, task.criteria),
                    "score": self._score(item.score),
                    "qualified": bool(item.qualified),
                    "sendable": is_today_send,
                    "pending_contact": is_pending_contact,
                    "contacted": is_contacted,
                    "follow_up_ready": is_contacted and item.lead.domain in reply_domains,
                })
        rows.sort(key=lambda item: item["lead"].get("domain", ""))
        unique_domains = {item["lead"].get("domain") for item in rows if item["lead"].get("domain")}
        emails = {email.lower() for item in rows for email in item["lead"].get("emails", []) if "@" in email}
        qualified = [item for item in rows if item["qualified"]]
        sendable = [item for item in rows if item["sendable"]]
        pending_contact = [item for item in rows if item["pending_contact"]]
        contacted = [item for item in rows if item["contacted"]]
        follow_up = [item for item in rows if item["follow_up_ready"]]
        return 200, {
            "stats": {
                "task_count": len(tasks),
                "record_count": len(rows),
                "company_count": len(unique_domains),
                "qualified_count": len(qualified),
                "sendable_count": len(sendable),
                "pending_contact_count": len(pending_contact),
                "contacted_count": len(contacted),
                "follow_up_count": len(follow_up),
                "email_count": len(emails),
                "source_count": sum(item["lead"].get("source_summary", {}).get("website_count", 0) for item in rows),
            },
            "items": rows[::-1],
        }

    def _apply_research_country(self, task_id, task, assessments):
        """让数据库页使用背调补充的国家重新计算合格状态。"""
        effective = []
        for item in assessments:
            report = (
                self._research.get(task_id, item.lead.domain)
                if self._research is not None and item.lead.domain
                else None
            )
            candidate = item
            if report is not None and report.country and not item.lead.country:
                candidate = replace(
                    item,
                    lead=replace(item.lead, country=report.country),
                )
            effective.append(AcquisitionService._qualify([candidate], task.criteria)[0])
        return effective

    def _reply_domains(self) -> set[str]:
        if self._inbound_emails is None:
            return set()
        domains = set()
        for task in self._tasks.list():
            for message in self._inbound_emails.list_for_task(task.id):
                if not getattr(message, "is_bounce", False) and not getattr(message, "is_system_notification", False):
                    if message.lead_domain:
                        domains.add(message.lead_domain)
        return domains

    def _database_export(self, task_id: str = "") -> tuple[int, dict]:
        """将本机客户资料导出为真实 XLSX；只导出已保存信息，不补造字段。"""
        overview_status, overview = self._database_overview(task_id)
        if overview_status != 200:
            return overview_status, overview
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "客户资料"
        base_headers = (
            "公司名称", "官网域名", "国家/地区", "客户类型", "公开邮箱",
            "发送安排", "业务简介", "产品", "来源数量",
        )
        field_labels = {
            "company_full_name": "公司全称",
            "registered_address": "注册地址",
            "founded_date": "成立时间",
            "legal_entity_type": "公司类型",
            "social_profiles": "社媒链接",
            "public_phone": "电话",
            "main_products": "主营产品",
            "business_positioning": "业务定位",
            "industry": "所在行业",
            "product_need_evidence": "产品需求证据",
            "key_contacts": "核心岗位及联系人",
            "decision_maker_email": "决策人邮箱",
            "decision_maker_linkedin": "决策人 LinkedIn",
            "historical_sourcing_categories": "过往采购品类",
        }
        reports = {}
        field_keys = list(field_labels)
        for item in overview["items"]:
            lead = item["lead"]
            report = self._research.get(item["task_id"], lead.get("domain", "")) if lead.get("domain") else None
            reports[id(item)] = report
            for key in (report.custom_fields if report else {}):
                if key not in field_keys:
                    field_keys.append(key)
        headers = base_headers + tuple(field_labels.get(key, key) for key in field_keys) + ("字段证据来源",)
        sheet.append(headers)
        for item in overview["items"]:
            lead = item["lead"]
            report = reports[id(item)]
            research = self._research_result(report) if report else {}
            custom_fields = report.custom_fields if report else {}
            field_sources = []
            custom_values = []
            for key in field_keys:
                field = custom_fields.get(key)
                custom_values.append(field.value if field else "")
                if field:
                    field_sources.extend(field.sources)
            sheet.append((
                lead.get("company_name") or lead.get("domain", ""),
                lead.get("domain", ""),
                lead.get("country", ""),
                lead.get("customer_type", ""),
                "; ".join(lead.get("emails", [])),
                "已发送" if item.get("contacted") else "未发送",
                research.get("business_summary", ""),
                "; ".join(research.get("products", [])),
                lead.get("source_summary", {}).get("website_count", 0),
                *custom_values,
                "; ".join(dict.fromkeys(field_sources)),
            ))
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column in sheet.columns:
            width = min(max(max(len(str(cell.value or "")) for cell in column) + 2, 10), 48)
            sheet.column_dimensions[column[0].column_letter].width = width
        output = io.BytesIO()
        workbook.save(output)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return 200, {
            "filename": "客户资料库.xlsx",
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "content_base64": encoded,
            "row_count": len(overview["items"]),
        }

    def _create_task(self, body: dict) -> tuple[int, dict]:
        criteria_data = body.get("criteria", {})
        if not isinstance(criteria_data, dict):
            raise ValueError("criteria must be an object")
        criteria = AcquisitionCriteria(
            product=str(criteria_data.get("product", "")),
            countries=tuple(str(item) for item in criteria_data.get("countries", [])),
            industries=tuple(str(item) for item in criteria_data.get("industries", [])),
            customer_types=tuple(str(item) for item in criteria_data.get("customer_types", [])),
            language=str(criteria_data.get("language", "auto")),
            daily_limit=int(criteria_data.get("daily_limit", 30)),
            qualified_lead_limit=int(
                criteria_data.get("qualified_lead_limit", criteria_data.get("daily_limit", 30))
            ),
            minimum_qualification_score=int(criteria_data.get("minimum_qualification_score", 40)),
            require_public_email=bool(criteria_data.get("require_public_email", True)),
            candidate_limit=int(
                criteria_data.get(
                    "candidate_limit", max(100, int(criteria_data.get("daily_limit", 30)))
                )
            ),
            keywords=tuple(str(item) for item in criteria_data.get("keywords", [])),
            business_offerings=tuple(
                BusinessOffering(
                    name=str(item.get("name", "")),
                    key=str(item.get("key", "")),
                    description=str(item.get("description", "")),
                    keywords=tuple(str(value) for value in item.get("keywords", [])),
                )
                for item in criteria_data.get("business_offerings", [])
                if isinstance(item, dict)
            ),
            research_fields=tuple(
                ResearchFieldDefinition(
                    name=str(item.get("name", "")),
                    key=str(item.get("key", "")),
                    description=str(item.get("description", "")),
                    keywords=tuple(str(value) for value in item.get("keywords", [])),
                    field_type=ResearchFieldType(item.get("type", "text")),
                    required=bool(item.get("required", False)),
                    evidence_required=bool(item.get("evidence_required", True)),
                    human_review=bool(item.get("human_review", True)),
                    options=tuple(str(value) for value in item.get("options", [])),
                )
                for item in criteria_data.get("research_fields", [])
                if isinstance(item, dict)
            ),
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

    def _assess_leads(self, task_id: str, body: dict, enrich: bool = False) -> tuple[int, dict]:
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
        if enrich:
            records = self._acquisition.enrich_records(task_id, records)
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
        return 200, self._discovery_payload(task_id, results)

    def _discover_leads(self, task_id: str, body: dict) -> tuple[int, dict]:
        weights = body.get(
            "weights",
            {"product_match": 30, "market_match": 20, "email_quality": 15, "evidence_quality": 5},
        )
        signals = body.get("signals_by_domain", {})
        if not isinstance(weights, dict) or not isinstance(signals, dict):
            raise ValueError("weights and signals_by_domain must be objects")
        if self._discovery_queue is not None:
            run = self._discovery_queue.submit(task_id, weights, signals)
            return 202, {"run": self._discovery_run(run)}
        results = self._acquisition.discover_and_assess(task_id, weights, signals)
        return 200, self._discovery_payload(task_id, results)

    def _discovery_runs(self, task_id: str) -> tuple[int, dict]:
        self._require_task(task_id)
        if self._discovery_runs_repository is None:
            raise RuntimeError("discovery run repository is not configured")
        return 200, {
            "items": [
                self._discovery_run(run)
                for run in self._discovery_runs_repository.list_for_task(task_id)
            ]
        }

    def _discovery_payload(self, task_id: str, results) -> dict:
        return {
            "items": [self._assessed(item, self._tasks.get(task_id).criteria) for item in results],
            "summary": self._discovery_summary(task_id, results),
        }

    def _discovery_summary(self, task_id: str, results) -> dict:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        qualified_count = sum(1 for item in results if item.qualified)
        target = task.criteria.daily_limit
        rejection_counts: dict[str, int] = {}
        for item in results:
            for reason in item.rejection_reasons:
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
        funnel = {
            "website_count": sum(bool(item.lead.domain) for item in results),
            "public_email_count": sum(bool(item.lead.emails) for item in results),
            "public_email_address_count": sum(len(item.lead.emails) for item in results),
            "website_evidence_count": sum(
                any(not is_search_source(url) for url, _excerpt in item.lead.sources)
                for item in results
            ),
            "evidence_source_count": sum(
                len(
                    {
                        canonical_source_url(url)
                        for url, _excerpt in item.lead.sources
                        if not is_search_source(url)
                    }
                )
                for item in results
            ),
            "external_source_count": sum(
                self._source_summary(item.lead)["external_count"] for item in results
            ),
            "multi_source_evidence_count": sum(
                len(
                    {
                        canonical_source_url(url)
                        for url, _excerpt in item.lead.sources
                        if not is_search_source(url)
                    }
                )
                >= 2
                for item in results
            ),
            "product_evidence_count": sum(
                self._acquisition.has_product_evidence(item.lead, task.criteria)
                for item in results
            ),
        }
        candidate_count = len(results)

        def coverage(count: int) -> float | None:
            return round(count / candidate_count, 4) if candidate_count else None

        return {
            "candidate_count": candidate_count,
            "qualified_count": qualified_count,
            "target_qualified_count": target,
            "shortfall": max(0, target - qualified_count),
            "candidate_limit": effective_candidate_limit(task.criteria),
            "funnel": funnel,
            "coverage_rates": {
                "website": coverage(funnel["website_count"]),
                "public_email_company": coverage(funnel["public_email_count"]),
                "product_evidence": coverage(funnel["product_evidence_count"]),
                "multi_source_evidence": coverage(funnel["multi_source_evidence_count"]),
                "qualified": coverage(qualified_count),
            },
            "rejection_counts": rejection_counts,
        }

    def _import_discovery(self, task_id: str, body: dict) -> tuple[int, dict]:
        if str(body.get("source_mode", "")).strip() != "browser":
            raise ValueError("browser discovery import requires source_mode=browser")
        records = body.get("records", [])
        if not isinstance(records, list):
            raise ValueError("records must be an array")
        for index, record in enumerate(records):
            if not isinstance(record, dict) or not is_search_source(
                str(record.get("source_url", "")).strip()
            ):
                raise ValueError(
                    f"browser result {index + 1} must include a Google or Bing source_url"
                )
        payload = {
            "records": records,
            "weights": body.get("weights", DEFAULT_QUALIFICATION_WEIGHTS),
            "signals_by_domain": body.get("signals_by_domain", {}),
        }
        status, result = self._assess_leads(task_id, payload, enrich=True)
        domains = {
            canonical_website_domain(str(record.get("website", "")))
            or str(record.get("company_name", "")).strip().casefold()
            for record in records
            if canonical_website_domain(str(record.get("website", "")))
            or str(record.get("company_name", "")).strip()
        }
        result["summary"]["imported_record_count"] = len(records)
        result["summary"]["imported_unique_domain_count"] = len(domains)
        result["summary"]["imported_duplicate_count"] = max(0, len(records) - len(domains))
        return status, result

    def _research_lead(self, task_id: str, domain: str, body: dict) -> tuple[int, dict]:
        if self._research_execution is None:
            raise RuntimeError("research execution service is not configured")
        self._require_task(task_id)
        assessed = next(
            (item for item in self._acquisition.list_leads(task_id) if item.lead.domain == domain),
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
        timeout_seconds = int(body.get("timeout_seconds", 120))
        request_key = str(body.get("idempotency_key", "")).strip()
        if self._research_queue is not None:
            run = self._research_queue.submit(
                task_id,
                assessed.lead,
                source_url,
                normalized_weights,
                max_attempts=max_attempts,
                request_key=request_key,
                timeout_seconds=timeout_seconds,
            )
            return 202, {"run": self._research_run(run)}
        result = self._research_execution.execute(
            task_id,
            assessed.lead,
            source_url,
            normalized_weights,
            max_attempts=max_attempts,
            timeout_seconds=timeout_seconds,
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
            self._tasks.get(task_id).criteria.language,
        )
        self._drafts.save(draft)
        return 201, self._draft(draft)

    def _task_drafts(self, task_id: str) -> tuple[int, dict]:
        """列出当前任务可供批量审核的外贸邮件草稿。"""
        self._require_task(task_id)
        getter = getattr(self._drafts, "list_for_task", None)
        if not callable(getter):
            raise RuntimeError("email draft repository does not support task listing")
        return 200, {"items": [self._draft(self._normalize_draft(item, task_id)) for item in getter(task_id)]}

    def _normalize_draft(self, draft, task_id: str):
        """Remove legacy sender placeholders from drafts created before profile setup."""
        task = self._tasks.get(task_id)
        if draft is None or task is None:
            return draft
        company, name, position = task.sender_profile.prompt_values()
        replacements = {
            "[Our Company]": company,
            "[Your Company]": company,
            "[Your Name]": name,
            "[Your Position]": position,
        }
        subject = draft.subject
        body = draft.body
        for placeholder, value in replacements.items():
            subject = subject.replace(placeholder, value)
            body = body.replace(placeholder, value)
        if subject == draft.subject and body == draft.body:
            return draft
        normalized = replace(draft, subject=subject, body=body)
        self._drafts.save(normalized)
        return normalized

    def _batch_send_drafts(self, task_id: str, body: dict) -> tuple[int, dict]:
        """批量发送已人工审核的草稿；未确认时只返回预览，不执行发送。"""
        if self._email_send is None:
            raise RuntimeError("email send service is not configured")
        self._require_task(task_id)
        draft_ids = body.get("draft_ids", [])
        if not isinstance(draft_ids, list):
            raise ValueError("draft_ids must be an array")
        draft_ids = list(dict.fromkeys(str(item).strip() for item in draft_ids if str(item).strip()))
        if not draft_ids:
            raise ValueError("at least one draft is required")
        if len(draft_ids) > 30:
            raise ValueError("batch sending is limited to 30 drafts per operation")
        drafts = [self._normalize_draft(self._drafts.get(draft_id), task_id) for draft_id in draft_ids]
        if any(draft is None or draft.task_id != task_id for draft in drafts):
            raise ValueError("all drafts must belong to the current task")
        preview = [
            {
                "id": draft.id,
                "recipient_email": draft.recipient_email,
                "subject": draft.subject,
                "status": draft.status.value,
                "approved": draft.status.value == "approved",
            }
            for draft in drafts
        ]
        if not bool(body.get("confirmed", False)):
            return 200, {
                "requires_confirmation": True,
                "sending_performed": False,
                "count": len(preview),
                "items": preview,
            }
        if not all(item["approved"] for item in preview):
            raise ValueError("all selected drafts must be approved before batch sending")
        if not self._sending_enabled:
            raise RuntimeError(
                "SMTP sending is disabled; enable it explicitly for a controlled test"
            )
        task = self._tasks.get(task_id)
        sent_count = 0
        results = []
        for draft in drafts:
            policy = SendPolicy(
                daily_limit=task.criteria.daily_limit,
                sent_today=sent_count,
                recent_contact_days=7,
            )
            try:
                attempt = self._email_send.send(
                    draft.id,
                    policy,
                    True,
                    draft.recipient_email,
                    draft.subject,
                    draft.body,
                    f"batch-{task_id}-{draft.id}",
                )
                sent_count += 1
                results.append({"draft_id": draft.id, "success": True, "attempt": self._send_attempt(attempt)})
            except Exception as error:
                results.append({"draft_id": draft.id, "success": False, "error": str(error)})
        return 200, {
            "requires_confirmation": False,
            "sending_performed": bool(sent_count),
            "count": len(results),
            "sent_count": sent_count,
            "failed_count": len(results) - sent_count,
            "items": results,
        }

    def _update_contact(self, task_id: str, domain: str, body: dict) -> tuple[int, dict]:
        result = self._acquisition.update_contact(
            task_id,
            domain,
            str(body.get("email", "")),
            str(body.get("source_url", "")),
            str(body.get("source_excerpt", "")),
        )
        return 200, self._assessed(result, self._tasks.get(task_id).criteria)

    def _update_sender_profile(self, task_id: str, body: dict) -> tuple[int, dict]:
        profile = SenderProfile(
            company_name=str(body.get("company_name", "")),
            contact_name=str(body.get("contact_name", "")),
            position=str(body.get("position", "")),
        )
        return 200, self._task(self._acquisition.update_sender_profile(task_id, profile))

    def _update_criteria(self, task_id: str, body: dict) -> tuple[int, dict]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        criteria_data = body.get("criteria", body)
        if not isinstance(criteria_data, dict):
            raise ValueError("criteria must be an object")
        current = task.criteria
        merged = {
            "product": current.product,
            "countries": current.countries,
            "industries": current.industries,
            "customer_types": current.customer_types,
            "language": current.language,
            "daily_limit": current.daily_limit,
            "qualified_lead_limit": current.qualified_lead_limit,
            "minimum_qualification_score": current.minimum_qualification_score,
            "require_public_email": current.require_public_email,
            "candidate_limit": current.candidate_limit or max(100, current.daily_limit),
            "keywords": current.keywords,
            "business_offerings": current.business_offerings,
            "research_fields": current.research_fields,
        }
        merged.update(criteria_data)
        criteria = AcquisitionCriteria(
            product=str(merged.get("product", "")),
            countries=tuple(str(item) for item in merged.get("countries", [])),
            industries=tuple(str(item) for item in merged.get("industries", [])),
            customer_types=tuple(str(item) for item in merged.get("customer_types", [])),
            language=str(merged.get("language", "auto")),
            daily_limit=int(merged.get("daily_limit", 30)),
            qualified_lead_limit=int(
                merged.get("qualified_lead_limit", merged.get("daily_limit", 30))
            ),
            minimum_qualification_score=int(merged.get("minimum_qualification_score", 40)),
            require_public_email=bool(merged.get("require_public_email", True)),
            candidate_limit=int(
                merged.get("candidate_limit", max(100, int(merged.get("daily_limit", 30))))
            ),
            keywords=tuple(str(item) for item in merged.get("keywords", [])),
            business_offerings=tuple(
                BusinessOffering(
                    name=str(item.get("name", "")),
                    key=str(item.get("key", "")),
                    description=str(item.get("description", "")),
                    keywords=tuple(str(value) for value in item.get("keywords", [])),
                )
                for item in merged.get("business_offerings", [])
                if isinstance(item, dict)
            ),
            research_fields=tuple(
                ResearchFieldDefinition(
                    name=str(item.get("name", "")),
                    key=str(item.get("key", "")),
                    description=str(item.get("description", "")),
                    keywords=tuple(str(value) for value in item.get("keywords", [])),
                    field_type=ResearchFieldType(item.get("type", "text")),
                    required=bool(item.get("required", False)),
                    evidence_required=bool(item.get("evidence_required", True)),
                    human_review=bool(item.get("human_review", True)),
                    options=tuple(str(value) for value in item.get("options", [])),
                )
                for item in merged.get("research_fields", [])
                if isinstance(item, dict)
            ),
        )
        return 200, self._task(self._acquisition.update_criteria(task_id, criteria))

    def _review_research_field(
        self, task_id: str, domain: str, field_key: str, body: dict
    ) -> tuple[int, dict]:
        actor = str(body.get("actor") or "本地用户").strip()
        report = self._research.get(task_id, domain)
        if report is None:
            raise KeyError(f"Research report not found: {domain}")
        current = report.custom_fields.get(field_key)
        if current is None:
            raise KeyError(f"Research field not found: {field_key}")
        status = str(body.get("status", "")).strip()
        if status not in {"verified", "reported", "unknown", "conflicting"}:
            raise ValueError("invalid research field review status")
        if status == "verified" and not current.sources:
            raise ValueError("verified research fields require source evidence")
        reviewed = ResearchFieldValue(
            value=str(body.get("value", current.value)),
            status=status,
            confidence=1.0 if status == "verified" else current.confidence,
            sources=current.sources,
            checked_at=datetime.now(timezone.utc).isoformat(),
        )
        fields = dict(report.custom_fields)
        fields[field_key] = reviewed
        updated = replace(report, custom_fields=fields)
        if not hasattr(self._research, "save"):
            raise RuntimeError("research repository is read-only")
        lead = None
        if self._audit is not None:
            lead = next(
                (
                    item
                    for item in self._acquisition.list_leads(task_id)
                    if item.lead.domain == domain
                ),
                None,
            )
            if lead is None:
                raise KeyError(f"Lead not found: {domain}")
        self._research.save(task_id, domain, updated)
        if self._audit is not None:
            self._audit.save(
                AuditEvent.status_change(
                    entity_type="lead",
                    entity_id=f"{task_id}:{domain}",
                    action="research_field_review",
                    actor=actor,
                    from_status=lead.lead.status.value,
                    to_status=lead.lead.status.value,
                    note=f"{field_key}: {status}",
                )
            )
        return 200, self._research_result(updated)

    def _discover_public_contacts(self, task_id: str, domain: str) -> tuple[int, dict]:
        if self._website_reader is None:
            raise RuntimeError("website contact discovery is not configured")
        result = self._acquisition.discover_public_contacts(task_id, domain, self._website_reader)
        return 200, self._assessed(result, self._tasks.get(task_id).criteria)

    def _transition_lead(self, task_id: str, domain: str, body: dict) -> tuple[int, dict]:
        try:
            target = LeadStatus(str(body.get("status", "")))
        except ValueError as error:
            raise ValueError("invalid lead status") from error
        return 200, self._assessed(
            self._acquisition.transition_lead(
                task_id, domain, target, str(body.get("actor", "")), str(body.get("note", ""))
            ),
            self._tasks.get(task_id).criteria,
        )

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
        return 200, self._task(
            self._acquisition.transition_task(
                task_id,
                target,
                str(body.get("actor", "")),
                str(body.get("note", "")),
            )
        )

    def _task_audit_events(self, task_id: str) -> tuple[int, dict]:
        self._require_task(task_id)
        events = self._audit.list_for_entity("acquisition_task", task_id) if self._audit else []
        return 200, {"items": [self._audit_event(event) for event in events]}

    def _lead_detail(self, task_id: str, domain: str) -> tuple[int, dict]:
        self._require_task(task_id)
        assessed = next(
            (item for item in self._acquisition.list_leads(task_id) if item.lead.domain == domain),
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
        draft = self._normalize_draft(draft, task_id)
        send_history = []
        if self._email_send is not None:
            getter = getattr(self._email_send, "list_attempts_for_lead", None)
            if callable(getter):
                send_history = [self._send_attempt(item) for item in getter(task_id, domain)]
        return 200, {
            "lead": self._lead(assessed.lead, self._tasks.get(task_id).criteria),
            "score": self._score(assessed.score),
            "research": self._research_result(report) if report else None,
            "draft": self._draft(draft) if draft else None,
            "send_history": send_history,
        }

    def _draft_detail(self, draft_id: str) -> tuple[int, dict]:
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise KeyError(f"Draft not found: {draft_id}")
        draft = self._normalize_draft(draft, draft.task_id)
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
        reviewer = str(body.get("reviewer") or "本地用户").strip()
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
                "countries": list(task.criteria.countries),
                "industries": list(task.criteria.industries),
                "customer_types": list(task.criteria.customer_types),
                "keywords": list(task.criteria.keywords),
                "language": task.criteria.language,
                "daily_limit": task.criteria.daily_limit,
                "qualified_lead_limit": task.criteria.qualified_lead_limit,
                "minimum_qualification_score": task.criteria.minimum_qualification_score,
                "require_public_email": task.criteria.require_public_email,
                "candidate_limit": task.criteria.candidate_limit,
                "business_offerings": [item.to_dict() for item in task.criteria.business_offerings],
                "research_fields": [item.to_dict() for item in task.criteria.research_fields],
            },
            "sender_profile": {
                "company_name": task.sender_profile.company_name,
                "contact_name": task.sender_profile.contact_name,
                "position": task.sender_profile.position,
            },
        }

    @staticmethod
    def _lead(lead, criteria=None, include_sources: bool = True) -> dict:
        payload = {
            # Keep raw search titles in evidence, but expose a cleaned name in
            # customer-facing lists and the local database.
            "company_name": clean_company_name(lead.company_name, lead.domain),
            "domain": lead.domain,
            "website": f"https://{lead.domain}" if lead.domain else "",
            "emails": list(lead.emails),
            "country": lead.country,
            "quality": lead.quality,
            "status": lead.status.value,
            "flags": list(lead.flags),
            "evidence_level": evidence_level(lead),
            "identity_consistency": identity_consistency(lead),
            "source_summary": ApiApplication._source_summary(lead),
            "evidence_checks": ApiApplication._evidence_checks(lead, criteria),
        }
        if include_sources:
            payload["sources"] = [list(source) for source in lead.sources]
        return payload

    @staticmethod
    def _evidence_checks(lead, criteria=None) -> dict:
        text = " ".join(
            excerpt.lower()
            for url, excerpt in lead.sources
            if excerpt.strip() and not is_search_source(url)
        )

        def check(value: str) -> str:
            normalized = " ".join(value.lower().split())
            return "supported" if normalized and normalized in text else "not_found"

        checks = {
            "company_name": check(lead.company_name),
            "country": (
                "conflicting"
                if "conflicting_country" in lead.flags
                else check(lead.country) if lead.country else "not_configured"
            ),
            "email": (
                "conflicting"
                if "email_domain_mismatch" in lead.flags
                else "supported"
                if lead.emails and any(email.lower() in text for email in lead.emails)
                else "not_found"
            ),
            "product": "not_checked",
            "industry": "not_configured",
        }
        if criteria is not None:
            checks["product"] = (
                "supported"
                if AcquisitionService.has_product_evidence(lead, criteria)
                else "not_found"
            )
            industry_terms = tuple(
                term.strip().lower() for term in criteria.industries if term.strip()
            )
            checks["industry"] = (
                "supported"
                if any(AcquisitionService._term_in_evidence(term, text) for term in industry_terms)
                else "not_found"
                if industry_terms
                else "not_configured"
            )
        return checks

    @staticmethod
    def _source_summary(lead) -> dict:
        website_urls = {
            canonical_source_url(url)
            for url, _excerpt in lead.sources
            if url.strip() and not is_search_source(url)
        }
        lead_domain = canonical_website_domain(lead.domain)
        external_urls = {
            url
            for url in website_urls
            if canonical_website_domain(url) and canonical_website_domain(url) != lead_domain
        }
        return {
            "website_count": len(website_urls),
            "same_domain_count": len(website_urls) - len(external_urls),
            "external_count": len(external_urls),
            "external_status": "linked_requires_review" if external_urls else "none",
        }

    @staticmethod
    def _score(score) -> dict:
        return {"total": score.total, "priority": score.priority, "breakdown": score.breakdown}

    @staticmethod
    def _assessed(item, criteria=None, include_sources: bool = True) -> dict:
        return {
            "lead": ApiApplication._lead(item.lead, criteria, include_sources=include_sources),
            "score": ApiApplication._score(item.score),
            "qualified": item.qualified,
            "rejection_reasons": list(item.rejection_reasons),
        }

    @staticmethod
    def _research_result(report) -> dict:
        return {
            "company_name": report.company_name,
            "business_summary": report.business_summary,
            "customer_type": report.customer_type.value,
            "products": report.products,
            "country": report.country,
            "country_conflict": report.country_conflict,
            "confidence": report.confidence,
            "evidence_url": report.evidence_url,
            "evidence_status": report.evidence_status.value,
            "website_language": report.website_language,
            "evidence_urls": list(report.evidence_urls or (report.evidence_url,)),
            "custom_fields": {key: value.to_dict() for key, value in report.custom_fields.items()},
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
            "timeout_seconds": run.timeout_seconds,
        }

    @staticmethod
    def _discovery_run(run: DiscoveryRun) -> dict:
        health = classify_search_error(run.error) if run.error else {}
        return {
            "id": run.id,
            "task_id": run.task_id,
            "status": run.status.value,
            "step": run.step.value,
            "candidate_count": run.candidate_count,
            "website_count": run.website_count,
            "public_email_count": run.public_email_count,
            "qualified_count": run.qualified_count,
            "error": run.error,
            **health,
        }

    @staticmethod
    def _inbound_email(message: InboundEmail) -> dict:
        return {
            "uid": message.uid,
            "message_id": message.message_id,
            "in_reply_to": message.in_reply_to,
            "references": message.references,
            "from_email": message.from_email,
            "to_emails": message.to_emails,
            "subject": message.subject,
            "body": message.body,
            "received_at": message.received_at,
            "thread_key": message.thread_key,
            "lead_domain": message.lead_domain,
            "is_bounce": message.is_bounce,
            "is_system_notification": message.is_system_notification,
        }

    @staticmethod
    def _reply_analysis_item(item: ReplyAnalysis) -> dict:
        return {
            "id": item.id,
            "message_id": item.message_id,
            "task_id": item.task_id,
            "lead_domain": item.lead_domain,
            "category": item.category.value,
            "confidence": item.confidence,
            "risk_level": item.risk_level,
            "suggested_action": item.suggested_action,
            "needs_human_review": item.needs_human_review,
            "evidence": item.evidence,
        }

    @staticmethod
    def _follow_up_task(item: FollowUpTask) -> dict:
        return {
            "id": item.id,
            "task_id": item.task_id,
            "lead_domain": item.lead_domain,
            "message_id": item.message_id,
            "title": item.title,
            "description": item.description,
            "status": item.status.value,
            "created_at": item.created_at,
            "completed_at": item.completed_at,
        }

    @staticmethod
    def _send_attempt(attempt: EmailSendAttempt) -> dict:
        return {
            "id": attempt.id,
            "draft_id": attempt.draft_id,
            "recipient_email": attempt.recipient_email,
            "subject": attempt.subject,
            "status": attempt.status.value,
            "provider_message_id": attempt.provider_message_id,
            "error": attempt.error,
            "created_at": attempt.created_at,
            "request_key": attempt.request_key,
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
            "kind": draft.kind.value,
            "language": draft.language,
            "language_source": draft.language_source,
            "language_requires_review": draft.language_requires_review,
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
