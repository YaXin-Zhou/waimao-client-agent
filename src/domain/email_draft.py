"""开发信草稿及人工审核状态。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import uuid4


class EmailDraftStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    REVISION_REQUIRED = "revision_required"
    APPROVED = "approved"
    REJECTED = "rejected"


class EmailDraftKind(StrEnum):
    OUTREACH = "outreach"
    REPLY = "reply"


@dataclass(frozen=True)
class EmailDraft:
    id: str
    task_id: str
    lead_domain: str
    recipient_email: str
    subject: str
    body: str
    evidence_urls: tuple[str, ...] = ()
    status: EmailDraftStatus = EmailDraftStatus.PENDING_REVIEW
    reviewed_by: str = ""
    review_note: str = ""
    kind: EmailDraftKind = EmailDraftKind.OUTREACH
    language: str = "English"
    language_source: str = "fallback"
    language_requires_review: bool = True

    @classmethod
    def create(
        cls,
        task_id: str,
        lead_domain: str,
        recipient_email: str,
        subject: str,
        body: str,
        evidence_urls: tuple[str, ...] = (),
        kind: EmailDraftKind = EmailDraftKind.OUTREACH,
        language: str = "English",
        language_source: str = "fallback",
        language_requires_review: bool = True,
    ) -> "EmailDraft":
        return cls(
            id=str(uuid4()),
            task_id=task_id,
            lead_domain=lead_domain,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            evidence_urls=evidence_urls,
            kind=kind,
            language=language,
            language_source=language_source,
            language_requires_review=language_requires_review,
        )

    def approve(self, reviewer: str) -> "EmailDraft":
        self._require_reviewer(reviewer)
        self._require_reviewable()
        return replace(
            self, status=EmailDraftStatus.APPROVED, reviewed_by=reviewer.strip()
        )

    def request_revision(self, reviewer: str, note: str) -> "EmailDraft":
        self._require_reviewer(reviewer)
        self._require_reviewable()
        if not note.strip():
            raise ValueError("revision note is required")
        return replace(
            self,
            status=EmailDraftStatus.REVISION_REQUIRED,
            reviewed_by=reviewer.strip(),
            review_note=note.strip(),
        )

    def reject(self, reviewer: str, note: str) -> "EmailDraft":
        self._require_reviewer(reviewer)
        self._require_reviewable()
        if not note.strip():
            raise ValueError("rejection note is required")
        return replace(
            self,
            status=EmailDraftStatus.REJECTED,
            reviewed_by=reviewer.strip(),
            review_note=note.strip(),
        )

    @staticmethod
    def _require_reviewer(reviewer: str) -> None:
        if not reviewer.strip():
            raise ValueError("reviewer is required")

    def _require_reviewable(self) -> None:
        if self.status not in (
            EmailDraftStatus.PENDING_REVIEW,
            EmailDraftStatus.REVISION_REQUIRED,
        ):
            raise ValueError("draft cannot be reviewed in its current status")
