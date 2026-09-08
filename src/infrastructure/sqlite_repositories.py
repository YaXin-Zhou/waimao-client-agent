"""SQLite 持久化适配器。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.application.acquisition_service import AssessedLead
from src.domain.lead import CleanLead, LeadScore
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
        )
        return AcquisitionTask(
            id=row["id"],
            name=row["name"],
            criteria=criteria,
            status=TaskStatus(row["status"]),
        )


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
                    ),
                    score=LeadScore(
                        total=score_data["total"],
                        priority=score_data["priority"],
                        breakdown=score_data["breakdown"],
                    ),
                )
            )
        return results
