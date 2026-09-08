"""开发信人工审核用例。"""

from __future__ import annotations

from src.domain.email_draft import EmailDraft


class EmailReviewService:
    def __init__(self, repository):
        self._repository = repository

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
        return reviewed
