"""只读收件邮件和线程关联规则。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parsedate_to_datetime


@dataclass(frozen=True)
class InboundEmail:
    uid: str
    message_id: str
    in_reply_to: str
    references: tuple[str, ...]
    from_email: str
    to_emails: tuple[str, ...]
    subject: str
    body: str
    received_at: str
    thread_key: str
    task_id: str = ""
    lead_domain: str = ""
    is_bounce: bool = False

    @classmethod
    def create(
        cls,
        uid: str,
        message_id: str,
        in_reply_to: str,
        references: tuple[str, ...],
        from_email: str,
        to_emails: tuple[str, ...],
        subject: str,
        body: str,
        received_at: str,
        task_id: str = "",
        lead_domain: str = "",
    ) -> "InboundEmail":
        normalized_subject = normalize_subject(subject)
        thread_key = in_reply_to or (references[0] if references else "") or normalized_subject
        return cls(
            uid=uid,
            message_id=message_id or f"uid:{uid}",
            in_reply_to=in_reply_to,
            references=references,
            from_email=from_email.lower(),
            to_emails=tuple(item.lower() for item in to_emails),
            subject=subject.strip(),
            body=body.strip(),
            received_at=received_at,
            thread_key=thread_key,
            task_id=task_id,
            lead_domain=lead_domain,
            is_bounce=is_bounce_subject(subject) or is_bounce_sender(from_email),
        )


def normalize_subject(subject: str) -> str:
    value = subject.strip()
    while re.match(r"^(re|fw|fwd)\s*:\s*", value, re.IGNORECASE):
        value = re.sub(r"^(re|fw|fwd)\s*:\s*", "", value, count=1, flags=re.IGNORECASE)
    return " ".join(value.lower().split())


def is_bounce_subject(subject: str) -> bool:
    value = subject.lower()
    return any(
        token in value
        for token in ("delivery status notification", "mail delivery", "undeliverable", "退信")
    )


def is_bounce_sender(sender: str) -> bool:
    value = sender.lower()
    return "mailer-daemon" in value or "postmaster" in value


def parse_received_date(value: str) -> str:
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError, OverflowError):
        return value.strip()
