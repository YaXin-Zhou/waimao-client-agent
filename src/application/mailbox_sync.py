"""同步收件箱，不包含任何发信能力。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

from src.domain.audit_event import AuditEvent
from src.domain.inbound_email import InboundEmail


class InboxReader(Protocol):
    def fetch_inbox(self) -> list[InboundEmail]: ...


class InboundEmailRepository(Protocol):
    def save(self, message: InboundEmail) -> None: ...

    def get_by_message_id(self, message_id: str) -> InboundEmail | None: ...

    def list_for_task(self, task_id: str) -> list[InboundEmail]: ...


@dataclass(frozen=True)
class MailboxSyncResult:
    fetched: int
    inserted: int
    skipped_duplicates: int
    bounce_count: int


class MailboxSyncService:
    def __init__(self, leads, repository: InboundEmailRepository, audit=None):
        self._leads = leads
        self._repository = repository
        self._audit = audit

    def sync(self, task_id: str, reader: InboxReader) -> MailboxSyncResult:
        assessments = self._leads.list_assessments(task_id)
        domains = {item.lead.domain.lower(): item.lead.domain for item in assessments}
        fetched = reader.fetch_inbox()
        inserted = 0
        duplicates = 0
        bounces = 0
        for message in fetched:
            if self._repository.get_by_message_id(message.message_id):
                duplicates += 1
                continue
            lead_domain = domains.get(_email_domain(message.from_email), "")
            associated = InboundEmail(
                **{**message.__dict__, "task_id": task_id, "lead_domain": lead_domain}
            )
            self._repository.save(associated)
            inserted += 1
            bounces += int(associated.is_bounce)
        result = MailboxSyncResult(len(fetched), inserted, duplicates, bounces)
        if self._audit:
            self._audit.save(
                AuditEvent.status_change(
                    "mailbox_sync", task_id, "mailbox_sync", "system",
                    "running", "completed",
                    note=(
                        f"fetched={result.fetched}; inserted={result.inserted}; "
                        f"duplicates={result.skipped_duplicates}; bounces={result.bounce_count}"
                    ),
                )
            )
        return result


def _email_domain(value: str) -> str:
    address = value.rsplit("<", 1)[-1].rstrip("> ").strip().lower()
    return urlparse(f"//{address}").hostname or ""
