"""邮件发送结果；发送动作由应用层显式触发。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4


class EmailSendStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"


@dataclass(frozen=True)
class EmailSendAttempt:
    id: str
    draft_id: str
    recipient_email: str
    subject: str
    status: EmailSendStatus
    provider_message_id: str = ""
    error: str = ""
    created_at: str = ""
    request_key: str = ""
    body_hash: str = ""

    @classmethod
    def sent(
        cls, draft_id, recipient_email, subject, provider_message_id,
        request_key="", body_hash="",
    ):
        return cls(
            str(uuid4()), draft_id, recipient_email, subject,
            EmailSendStatus.SENT, provider_message_id=provider_message_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            request_key=request_key, body_hash=body_hash,
        )

    @classmethod
    def failed(cls, draft_id, recipient_email, subject, error, request_key="", body_hash=""):
        return cls(
            str(uuid4()), draft_id, recipient_email, subject,
            EmailSendStatus.FAILED, error=error,
            created_at=datetime.now(timezone.utc).isoformat(),
            request_key=request_key, body_hash=body_hash,
        )
