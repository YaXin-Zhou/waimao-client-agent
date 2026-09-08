"""发送前安全检查；本模块不执行发送。"""

from __future__ import annotations

from dataclasses import dataclass
from email.utils import parseaddr
from pathlib import PurePath

from src.domain.email_draft import EmailDraft, EmailDraftStatus


@dataclass(frozen=True)
class SendPolicy:
    blocked_emails: tuple[str, ...] = ()
    blocked_domains: tuple[str, ...] = ()
    daily_limit: int = 0
    sent_today: int = 0
    contacted_recently: bool = False
    attachment_names: tuple[str, ...] = ()
    max_attachments: int = 5
    allowed_attachment_extensions: tuple[str, ...] = (
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"
    )


@dataclass(frozen=True)
class SendSafetyResult:
    allowed: bool
    requires_manual_confirmation: bool
    reasons: tuple[str, ...]


def check_send_safety(draft: EmailDraft, policy: SendPolicy) -> SendSafetyResult:
    reasons: list[str] = []
    address = parseaddr(draft.recipient_email)[1].strip().lower()
    domain = address.rsplit("@", 1)[-1] if "@" in address else ""
    if draft.status is not EmailDraftStatus.APPROVED:
        reasons.append("draft must be approved by a human reviewer")
    if not address or "@" not in address or not domain:
        reasons.append("recipient email is invalid")
    if address in {item.lower() for item in policy.blocked_emails}:
        reasons.append("recipient is on the blocklist")
    if domain in {item.lower() for item in policy.blocked_domains}:
        reasons.append("recipient domain is on the blocklist")
    if policy.daily_limit > 0 and policy.sent_today >= policy.daily_limit:
        reasons.append("daily sending limit has been reached")
    if policy.contacted_recently:
        reasons.append("recipient was contacted recently")
    if len(policy.attachment_names) > policy.max_attachments:
        reasons.append("attachment count exceeds the configured limit")
    allowed_extensions = {item.lower() for item in policy.allowed_attachment_extensions}
    for name in policy.attachment_names:
        path = PurePath(name)
        suffix = path.suffix.lower()
        if not name.strip() or path.name != name or suffix not in allowed_extensions:
            reasons.append(f"attachment is not allowed: {name}")
    return SendSafetyResult(
        allowed=not reasons,
        requires_manual_confirmation=True,
        reasons=tuple(reasons),
    )
