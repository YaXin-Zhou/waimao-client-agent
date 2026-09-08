"""阿里企业邮箱 IMAP 只读适配器；本模块没有 SMTP 或发送方法。"""

from __future__ import annotations

import imaplib
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from typing import Callable

from src.domain.inbound_email import InboundEmail, parse_received_date


@dataclass(frozen=True)
class AliImapConfig:
    host: str
    username: str
    password: str
    port: int = 993
    mailbox: str = "INBOX"

    @property
    def configured(self) -> bool:
        return bool(self.host and self.username and self.password)


class AliImapMailbox:
    def __init__(self, config: AliImapConfig, connection_factory: Callable | None = None):
        self._config = config
        self._connection_factory = connection_factory or imaplib.IMAP4_SSL

    def fetch_inbox(self) -> list[InboundEmail]:
        if not self._config.configured:
            raise RuntimeError("Ali IMAP is not configured")
        connection = self._connection_factory(self._config.host, self._config.port)
        try:
            connection.login(self._config.username, self._config.password)
            status, _ = connection.select(self._config.mailbox, readonly=True)
            if status != "OK":
                raise RuntimeError("Ali IMAP mailbox cannot be opened read-only")
            status, data = connection.search(None, "ALL")
            if status != "OK":
                raise RuntimeError("Ali IMAP inbox search failed")
            messages = []
            for uid in (data[0] or b"").split():
                status, fetched = connection.fetch(uid, "(RFC822)")
                if status == "OK":
                    raw = next((item[1] for item in fetched if isinstance(item, tuple)), b"")
                    if raw:
                        messages.append(parse_email(uid.decode(), raw))
            return messages
        finally:
            try:
                connection.logout()
            except Exception:
                pass

    def test_connection(self) -> None:
        """只验证登录和只读打开，不搜索或读取邮件。"""
        if not self._config.configured:
            raise RuntimeError("Ali IMAP is not configured")
        connection = self._connection_factory(self._config.host, self._config.port)
        try:
            connection.login(self._config.username, self._config.password)
            status, _ = connection.select(self._config.mailbox, readonly=True)
            if status != "OK":
                raise RuntimeError("Ali IMAP mailbox cannot be opened read-only")
        finally:
            try:
                connection.logout()
            except Exception:
                pass


def parse_email(uid: str, raw: bytes) -> InboundEmail:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    body = _text_body(message)
    references = tuple(message.get("References", "").split())
    senders = getaddresses([message.get("From", "")])
    return InboundEmail.create(
        uid=uid,
        message_id=message.get("Message-ID", "").strip(),
        in_reply_to=message.get("In-Reply-To", "").strip(),
        references=references,
        from_email=senders[0][1] if senders else "",
        to_emails=tuple(address for _, address in getaddresses(message.get_all("To", []))),
        subject=str(message.get("Subject", "")),
        body=body,
        received_at=parse_received_date(message.get("Date", "")),
    )


def _text_body(message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                return part.get_content()
        return ""
    return message.get_content() if message.get_content_type() == "text/plain" else ""
