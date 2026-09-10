"""SQLite 持久化适配器。"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

from src.application.acquisition_service import AssessedLead
from src.domain.audit_event import AuditEvent
from src.domain.custom_research import (
    BusinessOffering,
    ResearchFieldDefinition,
    ResearchFieldType,
    ResearchFieldValue,
)
from src.domain.discovery_run import DiscoveryRun, DiscoveryRunStatus, DiscoveryRunStep
from src.domain.email_draft import EmailDraft, EmailDraftKind, EmailDraftStatus
from src.domain.email_send import EmailSendAttempt, EmailSendStatus
from src.domain.follow_up_task import FollowUpStatus, FollowUpTask
from src.domain.inbound_email import InboundEmail
from src.domain.lead import CleanLead, LeadScore, LeadStatus
from src.domain.reply_analysis import ReplyAnalysis, ReplyCategory
from src.domain.research import CustomerType, EvidenceStatus, ResearchResult
from src.domain.research_run import ResearchRun, ResearchRunStatus, ResearchRunStep
from src.domain.sender_profile import SenderProfile
from src.domain.task import AcquisitionCriteria, AcquisitionTask, TaskStatus


def _connect(database: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS acquisition_tasks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            criteria_json TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_assessments (
            task_id TEXT NOT NULL,
            domain TEXT NOT NULL,
            lead_json TEXT NOT NULL,
            score_json TEXT NOT NULL,
            PRIMARY KEY (task_id, domain),
            FOREIGN KEY (task_id) REFERENCES acquisition_tasks(id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS research_reports (
            task_id TEXT NOT NULL,
            domain TEXT NOT NULL,
            report_json TEXT NOT NULL,
            PRIMARY KEY (task_id, domain)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS research_runs (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            domain TEXT NOT NULL,
            status TEXT NOT NULL,
            step TEXT NOT NULL DEFAULT 'queued',
            attempts INTEGER NOT NULL,
            error TEXT NOT NULL,
            request_key TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            weights_json TEXT NOT NULL DEFAULT '{}',
            max_attempts INTEGER NOT NULL DEFAULT 2,
            timeout_seconds INTEGER NOT NULL DEFAULT 120
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_runs (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL,
            step TEXT NOT NULL,
            candidate_count INTEGER NOT NULL DEFAULT 0,
            website_count INTEGER NOT NULL DEFAULT 0,
            public_email_count INTEGER NOT NULL DEFAULT 0,
            qualified_count INTEGER NOT NULL DEFAULT 0,
            error TEXT NOT NULL DEFAULT ''
        )
        """
    )
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(research_runs)").fetchall()
    }
    if "step" not in columns:
        connection.execute(
            "ALTER TABLE research_runs ADD COLUMN step TEXT NOT NULL DEFAULT 'queued'"
        )
    if "request_key" not in columns:
        connection.execute(
            "ALTER TABLE research_runs ADD COLUMN request_key TEXT NOT NULL DEFAULT ''"
        )
    if "source_url" not in columns:
        connection.execute(
            "ALTER TABLE research_runs ADD COLUMN source_url TEXT NOT NULL DEFAULT ''"
        )
    if "weights_json" not in columns:
        connection.execute(
            "ALTER TABLE research_runs ADD COLUMN weights_json TEXT NOT NULL DEFAULT '{}'"
        )
    if "max_attempts" not in columns:
        connection.execute(
            "ALTER TABLE research_runs ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 2"
        )
    if "timeout_seconds" not in columns:
        connection.execute(
            "ALTER TABLE research_runs ADD COLUMN timeout_seconds INTEGER NOT NULL DEFAULT 120"
        )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS research_runs_request_key "
        "ON research_runs(task_id, request_key) WHERE request_key <> ''"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS email_drafts (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            lead_domain TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            evidence_urls_json TEXT NOT NULL,
            status TEXT NOT NULL,
            reviewed_by TEXT NOT NULL,
            review_note TEXT NOT NULL
            ,kind TEXT NOT NULL DEFAULT 'outreach'
            ,language TEXT NOT NULL DEFAULT 'English'
            ,language_source TEXT NOT NULL DEFAULT 'fallback'
            ,language_requires_review INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    draft_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(email_drafts)").fetchall()
    }
    if "kind" not in draft_columns:
        connection.execute(
            "ALTER TABLE email_drafts ADD COLUMN kind TEXT NOT NULL DEFAULT 'outreach'"
        )
    if "language" not in draft_columns:
        connection.execute(
            "ALTER TABLE email_drafts ADD COLUMN language TEXT NOT NULL DEFAULT 'English'"
        )
    if "language_source" not in draft_columns:
        connection.execute(
            "ALTER TABLE email_drafts ADD COLUMN language_source TEXT NOT NULL DEFAULT 'fallback'"
        )
    if "language_requires_review" not in draft_columns:
        connection.execute(
            "ALTER TABLE email_drafts ADD COLUMN "
            "language_requires_review INTEGER NOT NULL DEFAULT 1"
        )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            from_status TEXT NOT NULL,
            to_status TEXT NOT NULL,
            note TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS inbound_emails (
            message_id TEXT PRIMARY KEY,
            uid TEXT NOT NULL,
            in_reply_to TEXT NOT NULL,
            references_json TEXT NOT NULL,
            from_email TEXT NOT NULL,
            to_emails_json TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            received_at TEXT NOT NULL,
            thread_key TEXT NOT NULL,
            task_id TEXT NOT NULL,
            lead_domain TEXT NOT NULL,
            is_bounce INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS follow_up_tasks (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            lead_domain TEXT NOT NULL,
            message_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS reply_analyses (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL UNIQUE,
            task_id TEXT NOT NULL,
            lead_domain TEXT NOT NULL,
            category TEXT NOT NULL,
            confidence REAL NOT NULL,
            risk_level TEXT NOT NULL,
            suggested_action TEXT NOT NULL,
            needs_human_review INTEGER NOT NULL,
            evidence_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS email_send_attempts (
            id TEXT PRIMARY KEY,
            draft_id TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            status TEXT NOT NULL,
            provider_message_id TEXT NOT NULL,
            error TEXT NOT NULL,
            created_at TEXT NOT NULL,
            request_key TEXT NOT NULL DEFAULT '',
            body_hash TEXT NOT NULL DEFAULT ''
        )
        """
    )
    send_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(email_send_attempts)").fetchall()
    }
    if "request_key" not in send_columns:
        connection.execute(
            "ALTER TABLE email_send_attempts ADD COLUMN request_key TEXT NOT NULL DEFAULT ''"
        )
    if "body_hash" not in send_columns:
        connection.execute(
            "ALTER TABLE email_send_attempts ADD COLUMN body_hash TEXT NOT NULL DEFAULT ''"
        )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS email_send_attempts_request_key "
        "ON email_send_attempts(draft_id, request_key) WHERE request_key <> ''"
    )
    connection.commit()
    return connection


class SQLiteTaskRepository:
    def __init__(self, database: str | Path):
        self._database = database

    def save(self, task: AcquisitionTask) -> None:
        criteria = {
            "product": task.criteria.product,
            "countries": task.criteria.countries,
            "industries": task.criteria.industries,
            "customer_types": task.criteria.customer_types,
            "language": task.criteria.language,
            "daily_limit": task.criteria.daily_limit,
            "qualified_lead_limit": task.criteria.qualified_lead_limit,
            "minimum_qualification_score": task.criteria.minimum_qualification_score,
            "require_public_email": task.criteria.require_public_email,
            "candidate_limit": task.criteria.candidate_limit,
            "keywords": task.criteria.keywords,
            "business_offerings": [item.to_dict() for item in task.criteria.business_offerings],
            "research_fields": [item.to_dict() for item in task.criteria.research_fields],
            "sender_profile": {
                "company_name": task.sender_profile.company_name,
                "contact_name": task.sender_profile.contact_name,
                "position": task.sender_profile.position,
            },
        }
        with _connect(self._database) as connection:
            connection.execute(
                """
                INSERT INTO acquisition_tasks (id, name, criteria_json, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    criteria_json=excluded.criteria_json,
                    status=excluded.status
                """,
                (task.id, task.name, json.dumps(criteria), task.status.value),
            )

    def get(self, task_id: str) -> AcquisitionTask | None:
        with _connect(self._database) as connection:
            row = connection.execute(
                "SELECT id, name, criteria_json, status FROM acquisition_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        criteria_data = json.loads(row["criteria_json"])
        criteria = AcquisitionCriteria(
            product=criteria_data["product"],
            countries=tuple(criteria_data["countries"]),
            industries=tuple(criteria_data["industries"]),
            customer_types=tuple(criteria_data["customer_types"]),
            language=criteria_data["language"],
            daily_limit=criteria_data["daily_limit"],
            qualified_lead_limit=criteria_data.get(
                "qualified_lead_limit", criteria_data["daily_limit"]
            ),
            minimum_qualification_score=criteria_data.get("minimum_qualification_score", 0),
            require_public_email=bool(criteria_data.get("require_public_email", False)),
            candidate_limit=criteria_data.get("candidate_limit", criteria_data["daily_limit"]),
            keywords=tuple(criteria_data.get("keywords", [])),
            business_offerings=tuple(
                BusinessOffering(
                    name=item["name"],
                    key=item["key"],
                    description=item.get("description", ""),
                    keywords=tuple(item.get("keywords", [])),
                )
                for item in criteria_data.get("business_offerings", [])
            ),
            research_fields=tuple(
                ResearchFieldDefinition(
                    name=item["name"],
                    key=item["key"],
                    description=item.get("description", ""),
                    keywords=tuple(item.get("keywords", [])),
                    field_type=ResearchFieldType(item.get("type", "text")),
                    required=bool(item.get("required", False)),
                    evidence_required=bool(item.get("evidence_required", True)),
                    human_review=bool(item.get("human_review", True)),
                    options=tuple(item.get("options", [])),
                )
                for item in criteria_data.get("research_fields", [])
            ),
        )
        sender_data = criteria_data.get("sender_profile", {})
        return AcquisitionTask(
            id=row["id"],
            name=row["name"],
            criteria=criteria,
            status=TaskStatus(row["status"]),
            sender_profile=SenderProfile(
                company_name=str(sender_data.get("company_name", "")),
                contact_name=str(sender_data.get("contact_name", "")),
                position=str(sender_data.get("position", "")),
            ),
        )

    def list(self) -> list[AcquisitionTask]:
        with _connect(self._database) as connection:
            rows = connection.execute(
                "SELECT id FROM acquisition_tasks ORDER BY rowid DESC"
            ).fetchall()
        return [task for row in rows if (task := self.get(row["id"])) is not None]


class SQLiteLeadRepository:
    def __init__(self, database: str | Path):
        self._database = database

    def save_assessments(self, task_id: str, results: list[AssessedLead]) -> None:
        with _connect(self._database) as connection:
            connection.executemany(
                """
                INSERT INTO lead_assessments (task_id, domain, lead_json, score_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(task_id, domain) DO UPDATE SET
                    lead_json=excluded.lead_json,
                    score_json=excluded.score_json
                """,
                [
                    (
                        task_id,
                        result.lead.domain,
                        json.dumps(
                            {
                                "company_name": result.lead.company_name,
                                "domain": result.lead.domain,
                                "emails": result.lead.emails,
                                "country": result.lead.country,
                                "quality": result.lead.quality,
                                "flags": result.lead.flags,
                                "sources": result.lead.sources,
                                "status": result.lead.status.value,
                                "qualified": result.qualified,
                                "rejection_reasons": result.rejection_reasons,
                            }
                        ),
                        json.dumps(
                            {
                                "total": result.score.total,
                                "priority": result.score.priority,
                                "breakdown": result.score.breakdown,
                            }
                        ),
                    )
                    for result in results
                ],
            )

    def list_assessments(self, task_id: str) -> list[AssessedLead]:
        with _connect(self._database) as connection:
            rows = connection.execute(
                """
                SELECT lead_json, score_json
                FROM lead_assessments
                WHERE task_id = ?
                ORDER BY rowid
                """,
                (task_id,),
            ).fetchall()
        results: list[AssessedLead] = []
        for row in rows:
            lead_data = json.loads(row["lead_json"])
            score_data = json.loads(row["score_json"])
            results.append(
                AssessedLead(
                    lead=CleanLead(
                        company_name=lead_data["company_name"],
                        domain=lead_data["domain"],
                        emails=tuple(lead_data["emails"]),
                        country=lead_data["country"],
                        quality=lead_data["quality"],
                        flags=tuple(lead_data["flags"]),
                        sources=tuple(tuple(source) for source in lead_data.get("sources", [])),
                        status=LeadStatus(lead_data.get("status", LeadStatus.NEW.value)),
                    ),
                    score=LeadScore(
                        total=score_data["total"],
                        priority=score_data["priority"],
                        breakdown=score_data["breakdown"],
                    ),
                    qualified=bool(lead_data.get("qualified", False)),
                    rejection_reasons=tuple(lead_data.get("rejection_reasons", [])),
                )
            )
        return results

    def update_score(self, task_id: str, domain: str, score: LeadScore) -> None:
        with _connect(self._database) as connection:
            row = connection.execute(
                "SELECT 1 FROM lead_assessments WHERE task_id = ? AND domain = ?",
                (task_id, domain),
            ).fetchone()
            if row is None:
                raise KeyError(f"Lead not found: {domain}")
            connection.execute(
                """
                UPDATE lead_assessments
                SET score_json = ?
                WHERE task_id = ? AND domain = ?
                """,
                (
                    json.dumps(
                        {
                            "total": score.total,
                            "priority": score.priority,
                            "breakdown": score.breakdown,
                        }
                    ),
                    task_id,
                    domain,
                ),
            )

    def update_research_evidence(
        self, task_id: str, domain: str, sources: tuple[tuple[str, str], ...]
    ) -> None:
        items = self.list_assessments(task_id)
        if not any(item.lead.domain == domain for item in items):
            raise KeyError(f"Lead not found: {domain}")
        self.save_assessments(
            task_id,
            [
                replace(item, lead=replace(item.lead, sources=sources))
                if item.lead.domain == domain
                else item
                for item in items
            ],
        )


class SQLiteResearchRepository:
    def __init__(self, database: str | Path):
        self._database = database

    def save(self, task_id: str, domain: str, report: ResearchResult) -> None:
        payload = {
            "company_name": report.company_name,
            "business_summary": report.business_summary,
            "customer_type": report.customer_type.value,
            "products": report.products,
            "country": report.country,
            "confidence": report.confidence,
            "evidence_url": report.evidence_url,
            "evidence_status": report.evidence_status.value,
            "website_language": report.website_language,
            "evidence_urls": report.evidence_urls or (report.evidence_url,),
            "custom_fields": {key: value.to_dict() for key, value in report.custom_fields.items()},
            "country_conflict": report.country_conflict,
        }
        with _connect(self._database) as connection:
            connection.execute(
                """
                INSERT INTO research_reports (task_id, domain, report_json)
                VALUES (?, ?, ?)
                ON CONFLICT(task_id, domain) DO UPDATE SET report_json=excluded.report_json
                """,
                (task_id, domain, json.dumps(payload)),
            )

    def get(self, task_id: str, domain: str) -> ResearchResult | None:
        with _connect(self._database) as connection:
            row = connection.execute(
                "SELECT report_json FROM research_reports WHERE task_id = ? AND domain = ?",
                (task_id, domain),
            ).fetchone()
        if row is None:
            return None
        return self._from_data(json.loads(row["report_json"]))

    def list_for_task(self, task_id: str) -> dict[str, ResearchResult]:
        """Load all research reports for a task with one database connection."""
        with _connect(self._database) as connection:
            rows = connection.execute(
                "SELECT domain, report_json FROM research_reports WHERE task_id = ?",
                (task_id,),
            ).fetchall()
        return {row["domain"]: self._from_data(json.loads(row["report_json"])) for row in rows}

    @staticmethod
    def _from_data(data: dict) -> ResearchResult:
        return ResearchResult(
            company_name=data["company_name"],
            business_summary=data["business_summary"],
            customer_type=CustomerType(data["customer_type"]),
            products=tuple(data["products"]),
            country=data["country"],
            confidence=data["confidence"],
            evidence_url=data["evidence_url"],
            evidence_status=EvidenceStatus(data["evidence_status"]),
            website_language=data.get("website_language", "unknown"),
            evidence_urls=tuple(data.get("evidence_urls", [data["evidence_url"]])),
            custom_fields={
                key: ResearchFieldValue(
                    value=str(value.get("value", "")),
                    status=str(value.get("status", "unknown")),
                    confidence=float(value.get("confidence", 0)),
                    sources=tuple(value.get("sources", [])),
                    checked_at=str(value.get("checked_at", "")),
                )
                for key, value in data.get("custom_fields", {}).items()
            },
            country_conflict=bool(data.get("country_conflict", False)),
        )


class SQLiteResearchRunRepository:
    def __init__(self, database: str | Path):
        self._database = database

    def save(self, run: ResearchRun) -> None:
        with _connect(self._database) as connection:
            connection.execute(
                """
                INSERT INTO research_runs (
                    id, task_id, domain, status, step, attempts, error, request_key,
                    source_url, weights_json, max_attempts, timeout_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    task_id=excluded.task_id,
                    domain=excluded.domain,
                    status=excluded.status,
                    step=excluded.step,
                    attempts=excluded.attempts,
                    error=excluded.error,
                    request_key=excluded.request_key,
                    source_url=excluded.source_url,
                    weights_json=excluded.weights_json,
                    max_attempts=excluded.max_attempts,
                    timeout_seconds=excluded.timeout_seconds
                """,
                (
                    run.id,
                    run.task_id,
                    run.domain,
                    run.status.value,
                    run.step.value,
                    run.attempts,
                    run.error,
                    run.request_key,
                    run.source_url,
                    json.dumps(dict(run.weights)),
                    run.max_attempts,
                    run.timeout_seconds,
                ),
            )

    def get(self, run_id: str) -> ResearchRun | None:
        with _connect(self._database) as connection:
            row = connection.execute(
                """
                SELECT id, task_id, domain, status, step, attempts, error, request_key,
                       source_url, weights_json, max_attempts, timeout_seconds
                FROM research_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        step = row["step"]
        if step == "executing":
            step = ResearchRunStep.FETCHING.value
        return ResearchRun(
            id=row["id"],
            task_id=row["task_id"],
            domain=row["domain"],
            status=ResearchRunStatus(row["status"]),
            step=ResearchRunStep(step),
            attempts=row["attempts"],
            error=row["error"],
            request_key=row["request_key"],
            source_url=row["source_url"],
            weights=tuple(json.loads(row["weights_json"]).items()),
            max_attempts=row["max_attempts"],
            timeout_seconds=row["timeout_seconds"],
        )

    def list_for_task(self, task_id: str) -> list[ResearchRun]:
        with _connect(self._database) as connection:
            rows = connection.execute(
                """
                SELECT id, task_id, domain, status, step, attempts, error, request_key,
                       source_url, weights_json, max_attempts, timeout_seconds
                FROM research_runs
                WHERE task_id = ?
                ORDER BY rowid
                """,
                (task_id,),
            ).fetchall()
        return [
            ResearchRun(
                id=row["id"],
                task_id=row["task_id"],
                domain=row["domain"],
                status=ResearchRunStatus(row["status"]),
                step=ResearchRunStep(
                    ResearchRunStep.FETCHING.value if row["step"] == "executing" else row["step"]
                ),
                attempts=row["attempts"],
                error=row["error"],
                request_key=row["request_key"],
                source_url=row["source_url"],
                weights=tuple(json.loads(row["weights_json"]).items()),
                max_attempts=row["max_attempts"],
                timeout_seconds=row["timeout_seconds"],
            )
            for row in rows
        ]

    def find_by_request_key(self, task_id: str, request_key: str) -> ResearchRun | None:
        if not request_key:
            return None
        with _connect(self._database) as connection:
            row = connection.execute(
                "SELECT id FROM research_runs WHERE task_id = ? AND request_key = ?",
                (task_id, request_key),
            ).fetchone()
        return self.get(row["id"]) if row else None

    def list_running(self) -> list[ResearchRun]:
        with _connect(self._database) as connection:
            rows = connection.execute(
                "SELECT id FROM research_runs WHERE status = ? ORDER BY rowid",
                (ResearchRunStatus.RUNNING.value,),
            ).fetchall()
        return [run for row in rows if (run := self.get(row["id"])) is not None]


class SQLiteDiscoveryRunRepository:
    def __init__(self, database: str | Path):
        self._database = database

    def save(self, run: DiscoveryRun) -> None:
        with _connect(self._database) as connection:
            connection.execute(
                """
                INSERT INTO discovery_runs (
                    id, task_id, status, step, candidate_count, website_count,
                    public_email_count, qualified_count, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    task_id=excluded.task_id, status=excluded.status, step=excluded.step,
                    candidate_count=excluded.candidate_count, website_count=excluded.website_count,
                    public_email_count=excluded.public_email_count,
                    qualified_count=excluded.qualified_count, error=excluded.error
                """,
                (
                    run.id, run.task_id, run.status.value, run.step.value,
                    run.candidate_count, run.website_count, run.public_email_count,
                    run.qualified_count, run.error,
                ),
            )

    def get(self, run_id: str) -> DiscoveryRun | None:
        with _connect(self._database) as connection:
            row = connection.execute(
                "SELECT * FROM discovery_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def list_for_task(self, task_id: str) -> list[DiscoveryRun]:
        with _connect(self._database) as connection:
            rows = connection.execute(
                "SELECT * FROM discovery_runs WHERE task_id = ? ORDER BY rowid",
                (task_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def fail_running(self, error: str) -> int:
        """将服务重启前遗留的运行中记录收敛为可重试的失败状态。"""
        with _connect(self._database) as connection:
            cursor = connection.execute(
                """
                UPDATE discovery_runs
                SET status = ?, step = ?, error = ?
                WHERE status = ?
                """,
                (
                    DiscoveryRunStatus.FAILED.value,
                    DiscoveryRunStep.FAILED.value,
                    error,
                    DiscoveryRunStatus.RUNNING.value,
                ),
            )
        return cursor.rowcount

    @staticmethod
    def _from_row(row) -> DiscoveryRun:
        return DiscoveryRun(
            id=row["id"], task_id=row["task_id"],
            status=DiscoveryRunStatus(row["status"]), step=DiscoveryRunStep(row["step"]),
            candidate_count=row["candidate_count"], website_count=row["website_count"],
            public_email_count=row["public_email_count"], qualified_count=row["qualified_count"],
            error=row["error"],
        )


class SQLiteEmailDraftRepository:
    def __init__(self, database: str | Path):
        self._database = database

    def save(self, draft: EmailDraft) -> None:
        with _connect(self._database) as connection:
            connection.execute(
                """
                INSERT INTO email_drafts (
                    id, task_id, lead_domain, recipient_email, subject, body,
                    evidence_urls_json, status, reviewed_by, review_note
                    ,kind, language, language_source, language_requires_review
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    task_id=excluded.task_id,
                    lead_domain=excluded.lead_domain,
                    recipient_email=excluded.recipient_email,
                    subject=excluded.subject,
                    body=excluded.body,
                    evidence_urls_json=excluded.evidence_urls_json,
                    status=excluded.status,
                    reviewed_by=excluded.reviewed_by,
                    review_note=excluded.review_note
                    ,kind=excluded.kind, language=excluded.language,
                    language_source=excluded.language_source,
                    language_requires_review=excluded.language_requires_review
                """,
                (
                    draft.id,
                    draft.task_id,
                    draft.lead_domain,
                    draft.recipient_email,
                    draft.subject,
                    draft.body,
                    json.dumps(draft.evidence_urls),
                    draft.status.value,
                    draft.reviewed_by,
                    draft.review_note,
                    draft.kind.value,
                    draft.language,
                    draft.language_source,
                    int(draft.language_requires_review),
                ),
            )

    def get(self, draft_id: str) -> EmailDraft | None:
        with _connect(self._database) as connection:
            row = connection.execute(
                "SELECT * FROM email_drafts WHERE id = ?", (draft_id,)
            ).fetchone()
        if row is None:
            return None
        return EmailDraft(
            id=row["id"],
            task_id=row["task_id"],
            lead_domain=row["lead_domain"],
            recipient_email=row["recipient_email"],
            subject=row["subject"],
            body=row["body"],
            evidence_urls=tuple(json.loads(row["evidence_urls_json"])),
            status=EmailDraftStatus(row["status"]),
            reviewed_by=row["reviewed_by"],
            review_note=row["review_note"],
            kind=EmailDraftKind(row["kind"]),
            language=row["language"],
            language_source=row["language_source"],
            language_requires_review=bool(row["language_requires_review"]),
        )

    def latest_for_lead(self, task_id: str, lead_domain: str) -> EmailDraft | None:
        with _connect(self._database) as connection:
            row = connection.execute(
                "SELECT id FROM email_drafts WHERE task_id = ? AND lead_domain = "
                "? ORDER BY rowid DESC LIMIT 1",
                (task_id, lead_domain),
            ).fetchone()
        return self.get(row["id"]) if row else None

    def list_for_lead(self, task_id: str, lead_domain: str) -> list[EmailDraft]:
        with _connect(self._database) as connection:
            rows = connection.execute(
                "SELECT id FROM email_drafts WHERE task_id = ? AND lead_domain = ? ORDER BY rowid",
                (task_id, lead_domain),
            ).fetchall()
        return [self.get(row["id"]) for row in rows]

    def list_for_task(self, task_id: str) -> list[EmailDraft]:
        with _connect(self._database) as connection:
            rows = connection.execute(
                "SELECT id FROM email_drafts WHERE task_id = ? AND kind = ? ORDER BY rowid",
                (task_id, EmailDraftKind.OUTREACH.value),
            ).fetchall()
        return [self.get(row["id"]) for row in rows]


class SQLiteAuditEventRepository:
    def __init__(self, database: str | Path):
        self._database = database

    def save(self, event: AuditEvent) -> None:
        with _connect(self._database) as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    id, entity_type, entity_id, action, actor,
                    from_status, to_status, note, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.entity_type,
                    event.entity_id,
                    event.action,
                    event.actor,
                    event.from_status,
                    event.to_status,
                    event.note,
                    event.occurred_at,
                ),
            )

    def list_for_entity(self, entity_type: str, entity_id: str) -> list[AuditEvent]:
        with _connect(self._database) as connection:
            rows = connection.execute(
                """
                SELECT id, entity_type, entity_id, action, actor,
                       from_status, to_status, note, occurred_at
                FROM audit_events
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY occurred_at, rowid
                """,
                (entity_type, entity_id),
            ).fetchall()
        return [
            AuditEvent(
                id=row["id"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                action=row["action"],
                actor=row["actor"],
                from_status=row["from_status"],
                to_status=row["to_status"],
                note=row["note"],
                occurred_at=row["occurred_at"],
            )
            for row in rows
        ]


class SQLiteInboundEmailRepository:
    def __init__(self, database: str | Path):
        self._database = database

    def save(self, message: InboundEmail) -> None:
        with _connect(self._database) as connection:
            connection.execute(
                """
                INSERT INTO inbound_emails (
                    message_id, uid, in_reply_to, references_json, from_email,
                    to_emails_json, subject, body, received_at, thread_key,
                    task_id, lead_domain, is_bounce
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    uid=excluded.uid, task_id=excluded.task_id,
                    lead_domain=excluded.lead_domain, is_bounce=excluded.is_bounce
                """,
                (
                    message.message_id,
                    message.uid,
                    message.in_reply_to,
                    json.dumps(message.references),
                    message.from_email,
                    json.dumps(message.to_emails),
                    message.subject,
                    message.body,
                    message.received_at,
                    message.thread_key,
                    message.task_id,
                    message.lead_domain,
                    int(message.is_bounce),
                ),
            )

    def get_by_message_id(self, message_id: str) -> InboundEmail | None:
        with _connect(self._database) as connection:
            row = connection.execute(
                "SELECT * FROM inbound_emails WHERE message_id = ?", (message_id,)
            ).fetchone()
        return _inbound_email(row) if row else None

    def list_for_task(self, task_id: str) -> list[InboundEmail]:
        with _connect(self._database) as connection:
            rows = connection.execute(
                "SELECT * FROM inbound_emails WHERE task_id = ? ORDER BY rowid",
                (task_id,),
            ).fetchall()
        return [_inbound_email(row) for row in rows]


def _inbound_email(row) -> InboundEmail:
    return InboundEmail(
        uid=row["uid"],
        message_id=row["message_id"],
        in_reply_to=row["in_reply_to"],
        references=tuple(json.loads(row["references_json"])),
        from_email=row["from_email"],
        to_emails=tuple(json.loads(row["to_emails_json"])),
        subject=row["subject"],
        body=row["body"],
        received_at=row["received_at"],
        thread_key=row["thread_key"],
        task_id=row["task_id"],
        lead_domain=row["lead_domain"],
        is_bounce=bool(row["is_bounce"]),
    )


class SQLiteReplyAnalysisRepository:
    def __init__(self, database: str | Path):
        self._database = database

    def save(self, analysis: ReplyAnalysis) -> None:
        with _connect(self._database) as connection:
            connection.execute(
                """
                INSERT INTO reply_analyses (
                    id, message_id, task_id, lead_domain, category, confidence,
                    risk_level, suggested_action, needs_human_review, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    task_id=excluded.task_id, lead_domain=excluded.lead_domain,
                    category=excluded.category, confidence=excluded.confidence,
                    risk_level=excluded.risk_level, suggested_action=excluded.suggested_action,
                    needs_human_review=excluded.needs_human_review,
                    evidence_json=excluded.evidence_json
                """,
                (
                    analysis.id,
                    analysis.message_id,
                    analysis.task_id,
                    analysis.lead_domain,
                    analysis.category.value,
                    analysis.confidence,
                    analysis.risk_level,
                    analysis.suggested_action,
                    int(analysis.needs_human_review),
                    json.dumps(analysis.evidence),
                ),
            )

    def get_by_message_id(self, message_id: str) -> ReplyAnalysis | None:
        with _connect(self._database) as connection:
            row = connection.execute(
                "SELECT * FROM reply_analyses WHERE message_id = ?", (message_id,)
            ).fetchone()
        return _reply_analysis(row) if row else None

    def list_for_task(self, task_id: str) -> list[ReplyAnalysis]:
        with _connect(self._database) as connection:
            rows = connection.execute(
                "SELECT * FROM reply_analyses WHERE task_id = ? ORDER BY rowid",
                (task_id,),
            ).fetchall()
        return [_reply_analysis(row) for row in rows]


def _reply_analysis(row) -> ReplyAnalysis:
    return ReplyAnalysis(
        id=row["id"],
        message_id=row["message_id"],
        task_id=row["task_id"],
        lead_domain=row["lead_domain"],
        category=ReplyCategory(row["category"]),
        confidence=row["confidence"],
        risk_level=row["risk_level"],
        suggested_action=row["suggested_action"],
        needs_human_review=bool(row["needs_human_review"]),
        evidence=tuple(json.loads(row["evidence_json"])),
    )


class SQLiteFollowUpTaskRepository:
    def __init__(self, database: str | Path):
        self._database = database

    def save_new(self, task_id, lead_domain, message_id, title, description):
        item = FollowUpTask.create(task_id, lead_domain, message_id, title, description)
        return self.save(item)

    def save(self, item: FollowUpTask):
        with _connect(self._database) as connection:
            connection.execute(
                """
                INSERT INTO follow_up_tasks (
                    id, task_id, lead_domain, message_id, title, description,
                    status, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status, completed_at=excluded.completed_at
                """,
                (
                    item.id,
                    item.task_id,
                    item.lead_domain,
                    item.message_id,
                    item.title,
                    item.description,
                    item.status.value,
                    item.created_at,
                    item.completed_at,
                ),
            )
        return item

    def get_by_message_id(self, message_id):
        with _connect(self._database) as connection:
            row = connection.execute(
                "SELECT * FROM follow_up_tasks WHERE message_id = ?", (message_id,)
            ).fetchone()
        return _follow_up_task(row) if row else None

    def get(self, item_id):
        with _connect(self._database) as connection:
            row = connection.execute(
                "SELECT * FROM follow_up_tasks WHERE id = ?", (item_id,)
            ).fetchone()
        return _follow_up_task(row) if row else None

    def list_for_task(self, task_id):
        with _connect(self._database) as connection:
            rows = connection.execute(
                "SELECT * FROM follow_up_tasks WHERE task_id = ? ORDER BY rowid",
                (task_id,),
            ).fetchall()
        return [_follow_up_task(row) for row in rows]


def _follow_up_task(row) -> FollowUpTask:
    return FollowUpTask(
        id=row["id"],
        task_id=row["task_id"],
        lead_domain=row["lead_domain"],
        message_id=row["message_id"],
        title=row["title"],
        description=row["description"],
        status=FollowUpStatus(row["status"]),
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


class SQLiteEmailSendAttemptRepository:
    def __init__(self, database: str | Path):
        self._database = database

    def save(self, attempt: EmailSendAttempt) -> None:
        with _connect(self._database) as connection:
            connection.execute(
                """
                INSERT INTO email_send_attempts (
                    id, draft_id, recipient_email, subject, status,
                    provider_message_id, error, created_at, request_key, body_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.id,
                    attempt.draft_id,
                    attempt.recipient_email,
                    attempt.subject,
                    attempt.status.value,
                    attempt.provider_message_id,
                    attempt.error,
                    attempt.created_at,
                    attempt.request_key,
                    attempt.body_hash,
                ),
            )

    def list_for_draft(self, draft_id: str) -> list[EmailSendAttempt]:
        with _connect(self._database) as connection:
            rows = connection.execute(
                "SELECT * FROM email_send_attempts WHERE draft_id = ? ORDER BY rowid",
                (draft_id,),
            ).fetchall()
        return [
            EmailSendAttempt(
                id=row["id"],
                draft_id=row["draft_id"],
                recipient_email=row["recipient_email"],
                subject=row["subject"],
                status=EmailSendStatus(row["status"]),
                provider_message_id=row["provider_message_id"],
                error=row["error"],
                created_at=row["created_at"],
                request_key=row["request_key"],
                body_hash=row["body_hash"],
            )
            for row in rows
        ]

    def was_recipient_contacted_since(self, recipient_email: str, days: int) -> bool:
        from datetime import datetime, timedelta, timezone

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with _connect(self._database) as connection:
            row = connection.execute(
                """
                SELECT 1 FROM email_send_attempts
                WHERE lower(recipient_email) = lower(?)
                  AND status = 'sent' AND created_at >= ?
                LIMIT 1
                """,
                (recipient_email, cutoff),
            ).fetchone()
        return row is not None

    def sent_recipient_emails(self) -> set[str]:
        with _connect(self._database) as connection:
            rows = connection.execute(
                "SELECT DISTINCT lower(recipient_email) AS recipient_email "
                "FROM email_send_attempts WHERE status = 'sent'"
            ).fetchall()
        return {row["recipient_email"] for row in rows if row["recipient_email"]}

    def find_by_request_key(self, draft_id: str, request_key: str) -> EmailSendAttempt | None:
        if not request_key:
            return None
        with _connect(self._database) as connection:
            row = connection.execute(
                "SELECT * FROM email_send_attempts WHERE draft_id = ? AND request_key = ?",
                (draft_id, request_key),
            ).fetchone()
        if row is None:
            return None
        return EmailSendAttempt(
            id=row["id"],
            draft_id=row["draft_id"],
            recipient_email=row["recipient_email"],
            subject=row["subject"],
            status=EmailSendStatus(row["status"]),
            provider_message_id=row["provider_message_id"],
            error=row["error"],
            created_at=row["created_at"],
            request_key=row["request_key"],
            body_hash=row["body_hash"],
        )
