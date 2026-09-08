import pytest

from src.application.email_send_service import EmailSendService
from src.domain.email_draft import EmailDraft, EmailDraftStatus
from src.domain.send_safety import SendPolicy


class Drafts:
    def __init__(self, draft):
        self.draft = draft

    def get(self, draft_id):
        return self.draft if draft_id == self.draft.id else None


class Attempts:
    def __init__(self):
        self.items = []

    def save(self, attempt):
        self.items.append(attempt)

    def find_by_request_key(self, draft_id, request_key):
        return next(
            (
                item for item in self.items
                if item.draft_id == draft_id and item.request_key == request_key
            ),
            None,
        )


class FakeSender:
    def __init__(self):
        self.calls = 0

    def send(self, draft):
        self.calls += 1
        return "<provider-message-id>"


def approved_draft():
    draft = EmailDraft.create("task-1", "alpine.example", "sales@alpine.example", "Subject", "Body")
    return draft.approve("Reviewer")


def test_send_requires_exact_manual_snapshot_and_records_attempt():
    item = approved_draft()
    sender = FakeSender()
    attempts = Attempts()
    service = EmailSendService(Drafts(item), sender, attempts)

    result = service.send(
        item.id, SendPolicy(), True, item.recipient_email, item.subject, item.body
    )

    assert result.status.value == "sent"
    assert sender.calls == 1
    assert attempts.items == [result]


def test_send_never_calls_provider_without_confirmation():
    item = approved_draft()
    sender = FakeSender()
    service = EmailSendService(Drafts(item), sender, Attempts())

    with pytest.raises(ValueError, match="confirmation"):
        service.send(item.id, SendPolicy(), False, item.recipient_email, item.subject, item.body)

    assert sender.calls == 0


def test_send_never_calls_provider_for_unapproved_draft():
    item = EmailDraft.create("task-1", "alpine.example", "sales@alpine.example", "Subject", "Body")
    sender = FakeSender()
    service = EmailSendService(Drafts(item), sender, Attempts())

    with pytest.raises(ValueError, match="blocked"):
        service.send(item.id, SendPolicy(), True, item.recipient_email, item.subject, item.body)

    assert item.status is EmailDraftStatus.PENDING_REVIEW
    assert sender.calls == 0


def test_same_send_request_is_reused_but_content_change_is_rejected():
    item = approved_draft()
    sender = FakeSender()
    attempts = Attempts()
    service = EmailSendService(Drafts(item), sender, attempts)
    first = service.send(
        item.id, SendPolicy(), True, item.recipient_email, item.subject, item.body,
        request_key="send-1",
    )

    second = service.send(
        item.id, SendPolicy(), True, item.recipient_email, item.subject, item.body,
        request_key="send-1",
    )
    assert second == first
    assert sender.calls == 1
    with pytest.raises(ValueError, match="different content"):
        service.send(
            item.id, SendPolicy(), True, item.recipient_email, item.subject, "Changed",
            request_key="send-1",
        )
