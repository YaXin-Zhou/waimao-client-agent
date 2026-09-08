import pytest

from src.application.email_review_service import EmailReviewService
from src.domain.email_draft import EmailDraft, EmailDraftStatus


class MemoryDraftRepository:
    def __init__(self, draft=None):
        self.draft = draft

    def get(self, draft_id):
        return self.draft if self.draft and self.draft.id == draft_id else None

    def save(self, draft):
        self.draft = draft


def draft():
    return EmailDraft(
        "draft-1",
        "task-1",
        "alpine.example",
        "sales@alpine.example",
        "Portable power",
        "Hello Alpine team.",
        ("https://alpine.example/about",),
    )


def test_review_service_approves_and_persists_draft():
    repository = MemoryDraftRepository(draft())

    result = EmailReviewService(repository).approve("draft-1", " reviewer-1 ")

    assert result.status is EmailDraftStatus.APPROVED
    assert result.reviewed_by == "reviewer-1"
    assert repository.draft == result


def test_review_service_requires_note_for_revision():
    repository = MemoryDraftRepository(draft())

    with pytest.raises(ValueError, match="revision note"):
        EmailReviewService(repository).request_revision("draft-1", "reviewer-1", " ")

    assert repository.draft.status is EmailDraftStatus.PENDING_REVIEW


def test_review_service_fails_for_unknown_draft():
    with pytest.raises(KeyError, match="Draft not found"):
        EmailReviewService(MemoryDraftRepository()).reject(
            "missing", "reviewer-1", "not a fit"
        )


def test_review_service_does_not_send_email():
    result = EmailReviewService(MemoryDraftRepository(draft())).approve(
        "draft-1", "reviewer-1"
    )

    assert result.status is EmailDraftStatus.APPROVED
    assert not hasattr(result, "send")


def test_rejected_draft_cannot_be_approved_again():
    rejected = draft().reject("reviewer-1", "not a fit")

    with pytest.raises(ValueError, match="cannot be reviewed"):
        rejected.approve("reviewer-2")
