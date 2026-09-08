"""人工确认后的邮件发送用例。"""

from __future__ import annotations

from typing import Protocol

from src.domain.email_send import EmailSendAttempt
from src.domain.send_safety import SendPolicy, check_send_safety


class EmailSender(Protocol):
    def send(self, draft) -> str: ...


class EmailSendService:
    def __init__(self, drafts, sender, attempts):
        self._drafts = drafts
        self._sender = sender
        self._attempts = attempts

    def send(
        self,
        draft_id: str,
        policy: SendPolicy,
        confirmed: bool,
        recipient_email: str,
        subject: str,
        body: str,
    ) -> EmailSendAttempt:
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise KeyError(f"Draft not found: {draft_id}")
        safety = check_send_safety(draft, policy)
        if not safety.allowed:
            raise ValueError("send blocked: " + "; ".join(safety.reasons))
        if not confirmed:
            raise ValueError("explicit human confirmation is required")
        if (recipient_email, subject, body) != (
            draft.recipient_email, draft.subject, draft.body
        ):
            raise ValueError("send confirmation does not match the current draft")
        try:
            provider_message_id = self._sender.send(draft)
        except Exception as error:
            attempt = EmailSendAttempt.failed(
                draft.id, draft.recipient_email, draft.subject, str(error)
            )
            self._attempts.save(attempt)
            raise
        attempt = EmailSendAttempt.sent(
            draft.id, draft.recipient_email, draft.subject, provider_message_id
        )
        self._attempts.save(attempt)
        return attempt
