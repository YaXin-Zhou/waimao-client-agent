"""人工确认后的邮件发送用例。"""

from __future__ import annotations

import hashlib
from dataclasses import replace
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
        request_key: str = "",
    ) -> EmailSendAttempt:
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise KeyError(f"Draft not found: {draft_id}")
        body_hash = hashlib.sha256(
            f"{recipient_email}\0{subject}\0{body}".encode("utf-8")
        ).hexdigest()
        if request_key and hasattr(self._attempts, "find_by_request_key"):
            existing = self._attempts.find_by_request_key(draft.id, request_key)
            if existing is not None:
                if existing.body_hash != body_hash:
                    raise ValueError("send idempotency key was reused with different content")
                return existing
        if (
            policy.recent_contact_days > 0
            and hasattr(self._attempts, "was_recipient_contacted_since")
        ):
            policy = replace(
                policy,
                contacted_recently=self._attempts.was_recipient_contacted_since(
                    draft.recipient_email, policy.recent_contact_days
                ),
            )
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
                draft.id, draft.recipient_email, draft.subject, str(error), request_key, body_hash
            )
            self._attempts.save(attempt)
            raise
        attempt = EmailSendAttempt.sent(
            draft.id, draft.recipient_email, draft.subject, provider_message_id,
            request_key, body_hash,
        )
        self._attempts.save(attempt)
        return attempt

    def list_attempts(self, draft_id: str):
        return self._attempts.list_for_draft(draft_id)
