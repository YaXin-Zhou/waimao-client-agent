"""启动本地 SQLite HTTP API。"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.application.email_draft_service import EmailDraftService  # noqa: E402
from src.application.email_send_service import EmailSendService  # noqa: E402
from src.application.mailbox_sync import MailboxSyncService  # noqa: E402
from src.application.reply_analysis_service import ReplyAnalysisService  # noqa: E402
from src.application.research_execution import ResearchExecutionService  # noqa: E402
from src.application.research_queue import ResearchJobQueue  # noqa: E402
from src.application.research_workflow import ResearchWorkflow  # noqa: E402
from src.application.send_safety_service import SendSafetyService  # noqa: E402
from src.application.translation_service import TranslationService  # noqa: E402
from src.infrastructure.ali_imap import AliImapConfig, AliImapMailbox  # noqa: E402
from src.infrastructure.ali_smtp import AliSmtpConfig, AliSmtpMailer  # noqa: E402
from src.infrastructure.deepseek_provider import DeepSeekConfig, DeepSeekProvider  # noqa: E402
from src.infrastructure.machine_translation_provider import (  # noqa: E402
    GoogleMachineTranslationProvider,
)
from src.infrastructure.sqlite_repositories import (  # noqa: E402
    SQLiteAuditEventRepository,
    SQLiteEmailDraftRepository,
    SQLiteEmailSendAttemptRepository,
    SQLiteInboundEmailRepository,
    SQLiteLeadRepository,
    SQLiteReplyAnalysisRepository,
    SQLiteResearchRepository,
    SQLiteResearchRunRepository,
    SQLiteTaskRepository,
)
from src.infrastructure.website_fetcher import WebsiteFetcher  # noqa: E402
from src.interfaces.http_api import ApiApplication  # noqa: E402

DATABASE = ROOT / "data" / "runtime" / "acquisition.db"


def _config_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


config_values = _config_values(ROOT / "config" / ".env")
task_repository = SQLiteTaskRepository(DATABASE)
lead_repository = SQLiteLeadRepository(DATABASE)
research_repository = SQLiteResearchRepository(DATABASE)
research_run_repository = SQLiteResearchRunRepository(DATABASE)
inbound_email_repository = SQLiteInboundEmailRepository(DATABASE)
reply_analysis_repository = SQLiteReplyAnalysisRepository(DATABASE)
email_draft_repository = SQLiteEmailDraftRepository(DATABASE)
email_send_attempt_repository = SQLiteEmailSendAttemptRepository(DATABASE)
try:
    deepseek_provider = DeepSeekProvider(
        DeepSeekConfig.from_env_file(ROOT / "config" / ".env")
    )
except (FileNotFoundError, ValueError):
    deepseek_provider = None
try:
    email_draft_service = EmailDraftService(deepseek_provider) if deepseek_provider else None
except (FileNotFoundError, ValueError):
    email_draft_service = None
research_execution = (
    ResearchExecutionService(
        task_repository,
        ResearchWorkflow(
            task_repository,
            WebsiteFetcher(),
            deepseek_provider,
            research_repository,
        ),
        research_run_repository,
    )
    if deepseek_provider is not None
    else None
)
research_queue = (
    ResearchJobQueue(research_execution, research_run_repository)
    if research_execution is not None
    else None
)
imap_config = AliImapConfig(
    host=config_values.get("ALI_IMAP_HOST", "imap.qiye.aliyun.com"),
    username=config_values.get("ALI_IMAP_USERNAME", ""),
    password=config_values.get("ALI_IMAP_PASSWORD", ""),
    port=int(config_values.get("ALI_IMAP_PORT", "993")),
    mailbox=config_values.get("ALI_IMAP_MAILBOX", "INBOX"),
)
mailbox = AliImapMailbox(imap_config) if imap_config.configured else None
mailbox_sync = MailboxSyncService(lead_repository, inbound_email_repository)
reply_analysis_service = ReplyAnalysisService(inbound_email_repository, reply_analysis_repository)
send_safety_service = SendSafetyService(SQLiteEmailDraftRepository(DATABASE))
smtp_config = AliSmtpConfig(
    host=config_values.get("ALI_SMTP_HOST", "smtp.qiye.aliyun.com"),
    username=config_values.get("ALI_SMTP_USERNAME", ""),
    password=config_values.get("ALI_SMTP_PASSWORD", ""),
    port=int(config_values.get("ALI_SMTP_PORT", "465")),
)
smtp_mailer = AliSmtpMailer(smtp_config) if smtp_config.configured else None
email_send_service = EmailSendService(
    email_draft_repository,
    smtp_mailer or AliSmtpMailer(smtp_config),
    email_send_attempt_repository,
)
application = ApiApplication(
    task_repository,
    lead_repository,
    research_repository,
    email_draft_repository,
    email_drafts=email_draft_service,
    translation=TranslationService(GoogleMachineTranslationProvider()),
    audit=SQLiteAuditEventRepository(DATABASE),
    research_execution=research_execution,
    research_runs=research_run_repository,
    research_queue=research_queue,
    mailbox=mailbox,
    mailbox_sync=mailbox_sync,
    inbound_emails=inbound_email_repository,
    reply_analysis=reply_analysis_service,
    send_safety=send_safety_service,
    email_send=email_send_service,
)


class Handler(BaseHTTPRequestHandler):
    def _respond(self, status, payload):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        status, payload = application.handle("GET", self.path)
        self._respond(status, payload)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        status, payload = application.handle("POST", self.path, body)
        self._respond(status, payload)

    def log_message(self, *_args):
        return


if __name__ == "__main__":
    port = int(os.environ.get("WAIMAO_API_PORT", "8001"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
