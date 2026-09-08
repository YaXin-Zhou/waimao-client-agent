"""阿里企业邮箱 SMTP 适配器；仅由人工确认后的发送用例调用。"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage


@dataclass(frozen=True)
class AliSmtpConfig:
    host: str
    username: str
    password: str
    port: int = 465

    @property
    def configured(self) -> bool:
        return bool(self.host and self.username and self.password)


class AliSmtpMailer:
    def __init__(self, config: AliSmtpConfig, connection_factory=smtplib.SMTP_SSL):
        self._config = config
        self._connection_factory = connection_factory

    def send(self, draft) -> str:
        if not self._config.configured:
            raise RuntimeError("Ali SMTP is not configured")
        message = EmailMessage()
        message["From"] = self._config.username
        message["To"] = draft.recipient_email
        message["Subject"] = draft.subject
        message.set_content(draft.body)
        with self._connection_factory(self._config.host, self._config.port) as connection:
            connection.login(self._config.username, self._config.password)
            result = connection.send_message(message)
        return str(result) if result else message.get("Message-ID", "")
