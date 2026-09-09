"""将当前任务中已持久化的客户档案导出为 CSV，不生成补充事实。"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "runtime" / "acquisition.db"
EXPORTS = ROOT / "data" / "exports"
sys.path.insert(0, str(ROOT))

from src.infrastructure.sqlite_repositories import (  # noqa: E402
    SQLiteLeadRepository,
    SQLiteResearchRepository,
    SQLiteTaskRepository,
)

FIELDS = (
    "company_name",
    "domain",
    "emails",
    "country",
    "quality",
    "flags",
    "score",
    "priority",
    "score_breakdown",
    "business_summary",
    "customer_type",
    "products",
    "research_country",
    "research_confidence",
    "evidence_url",
    "evidence_status",
    "source_urls",
)


def export_task(task_id: str, output: Path) -> int:
    tasks = SQLiteTaskRepository(DATABASE)
    if tasks.get(task_id) is None:
        raise ValueError(f"Task not found: {task_id}")
    leads = SQLiteLeadRepository(DATABASE)
    research = SQLiteResearchRepository(DATABASE)
    output.parent.mkdir(parents=True, exist_ok=True)
    task = tasks.get(task_id)
    custom_fields = tuple(field.key for field in task.criteria.research_fields)
    fields = FIELDS + custom_fields
    rows = []
    for assessed in leads.list_assessments(task_id):
        lead = assessed.lead
        report = research.get(task_id, lead.domain)
        row = {
            "company_name": lead.company_name,
            "domain": lead.domain,
            "emails": "; ".join(lead.emails),
            "country": lead.country,
            "quality": lead.quality,
            "flags": "; ".join(lead.flags),
            "score": assessed.score.total,
            "priority": assessed.score.priority,
            "score_breakdown": "; ".join(
                f"{key}={value}" for key, value in assessed.score.breakdown.items()
            ),
            "business_summary": report.business_summary if report else "",
            "customer_type": report.customer_type.value if report else "",
            "products": "; ".join(report.products) if report else "",
            "research_country": report.country if report else "",
            "research_confidence": report.confidence if report else "",
            "evidence_url": report.evidence_url if report else "",
            "evidence_status": report.evidence_status.value if report else "",
            "source_urls": "; ".join(source[0] for source in lead.sources),
        }
        for field_key in custom_fields:
            field = report.custom_fields.get(field_key) if report else None
            row[field_key] = field.value if field and field.status != "unknown" else ""
        rows.append(row)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or EXPORTS / (
        f"leads-{args.task_id}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.csv"
    )
    count = export_task(args.task_id, output)
    print(f"exported={count} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
