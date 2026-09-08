"""开发信人工审核用例。"""

from __future__ import annotations

from src.domain.audit_event import AuditEvent
from src.domain.email_draft import EmailDraft


class EmailReviewService:
    def __init__(self, repository, audit_repository=None):
        self._repository = repository
        self._audit = audit_repository

    def approve(self, draft_id: str, reviewer: str) -> EmailDraft:
        return self._apply(draft_id, lambda draft: draft.approve(reviewer))

    def request_revision(self, draft_id: str, reviewer: str, note: str) -> EmailDraft:
        return self._apply(
            draft_id, lambda draft: draft.request_revision(reviewer, note)
        )

    def reject(self, draft_id: str, reviewer: str, note: str) -> EmailDraft:
        return self._apply(draft_id, lambda draft: draft.reject(reviewer, note))

    def _apply(self, draft_id: str, transition) -> EmailDraft:
        draft = self._repository.get(draft_id)
        if draft is None:
            raise KeyError(f"Draft not found: {draft_id}")
        reviewed = transition(draft)
        self._repository.save(reviewed)
        if self._audit is not None:
            self._audit.save(AuditEvent.status_change(
                entity_type="email_draft",
                entity_id=draft.id,
                action="review",
                actor=reviewed.reviewed_by,
                from_status=draft.status.value,
                to_status=reviewed.status.value,
                note=reviewed.review_note,
            ))
        return reviewed
