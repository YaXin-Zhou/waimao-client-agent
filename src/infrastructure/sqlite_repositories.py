"""SQLite 持久化适配器。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.application.acquisition_service import AssessedLead
from src.domain.audit_event import AuditEvent
from src.domain.email_draft import EmailDraft, EmailDraftStatus
from src.domain.lead import CleanLead, LeadScore, LeadStatus
from src.domain.research import CustomerType, EvidenceStatus, ResearchResult
from src.domain.research_run import ResearchRun, ResearchRunStatus
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
            attempts INTEGER NOT NULL,
            error TEXT NOT NULL
        )
        """
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
        )
        """
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
            "keywords": task.criteria.keywords,
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
            keywords=tuple(criteria_data.get("keywords", [])),
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
                "SELECT id FROM acquisition_tasks ORDER BY rowid"
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
                        json.dumps({
                            "company_name": result.lead.company_name,
                            "domain": result.lead.domain,
                            "emails": result.lead.emails,
                            "country": result.lead.country,
                            "quality": result.lead.quality,
                            "flags": result.lead.flags,
                            "sources": result.lead.sources,
                            "status": result.lead.status.value,
                        }),
                        json.dumps({
                            "total": result.score.total,
                            "priority": result.score.priority,
                            "breakdown": result.score.breakdown,
                        }),
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
                )
            )
        return results


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
        data = json.loads(row["report_json"])
        return ResearchResult(
            company_name=data["company_name"],
            business_summary=data["business_summary"],
            customer_type=CustomerType(data["customer_type"]),
            products=tuple(data["products"]),
            country=data["country"],
            confidence=data["confidence"],
            evidence_url=data["evidence_url"],
            evidence_status=EvidenceStatus(data["evidence_status"]),
        )


class SQLiteResearchRunRepository:
    def __init__(self, database: str | Path):
        self._database = database

    def save(self, run: ResearchRun) -> None:
        with _connect(self._database) as connection:
            connection.execute(
                """
                INSERT INTO research_runs (id, task_id, domain, status, attempts, error)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    task_id=excluded.task_id,
                    domain=excluded.domain,
                    status=excluded.status,
                    attempts=excluded.attempts,
                    error=excluded.error
                """,
                (
                    run.id,
                    run.task_id,
                    run.domain,
                    run.status.value,
                    run.attempts,
                    run.error,
                ),
            )

    def get(self, run_id: str) -> ResearchRun | None:
        with _connect(self._database) as connection:
            row = connection.execute(
                """
                SELECT id, task_id, domain, status, attempts, error
                FROM research_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return ResearchRun(
            id=row["id"],
            task_id=row["task_id"],
            domain=row["domain"],
            status=ResearchRunStatus(row["status"]),
            attempts=row["attempts"],
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        )

    def latest_for_lead(self, task_id: str, lead_domain: str) -> EmailDraft | None:
        with _connect(self._database) as connection:
            row = connection.execute(
                "SELECT id FROM email_drafts WHERE task_id = ? AND lead_domain = "
                "? ORDER BY rowid DESC LIMIT 1",
                (task_id, lead_domain),
            ).fetchone()
        return self.get(row["id"]) if row else None


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
