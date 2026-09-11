"""启动本地 SQLite HTTP API。"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.application.acquisition_service import AcquisitionService  # noqa: E402
from src.application.discovery_queue import DiscoveryJobQueue  # noqa: E402
from src.application.email_draft_service import EmailDraftService  # noqa: E402
from src.application.email_send_service import EmailSendService  # noqa: E402
from src.application.follow_up_task_service import FollowUpTaskService  # noqa: E402
from src.application.mailbox_sync import MailboxSyncService  # noqa: E402
from src.application.reply_analysis_service import ReplyAnalysisService  # noqa: E402
from src.application.reply_draft_service import ReplyDraftService  # noqa: E402
from src.application.research_execution import ResearchExecutionService  # noqa: E402
from src.application.research_queue import ResearchJobQueue  # noqa: E402
from src.application.research_workflow import ResearchWorkflow  # noqa: E402
from src.application.send_safety_service import SendSafetyService  # noqa: E402
from src.application.translation_service import TranslationService  # noqa: E402
from src.infrastructure.ali_imap import AliImapConfig, AliImapMailbox  # noqa: E402
from src.infrastructure.ali_smtp import AliSmtpConfig, AliSmtpMailer  # noqa: E402
from src.infrastructure.bing_search_provider import BingSearchProvider  # noqa: E402
from src.infrastructure.deepseek_provider import DeepSeekConfig, DeepSeekProvider  # noqa: E402
from src.infrastructure.fallback_search_provider import FallbackSearchProvider  # noqa: E402
from src.infrastructure.google_search_provider import GoogleSearchProvider  # noqa: E402
from src.infrastructure.machine_translation_provider import (  # noqa: E402
    GoogleMachineTranslationProvider,
)
from src.infrastructure.playwright_search_provider import PlaywrightSearchProvider  # noqa: E402
from src.infrastructure.sqlite_repositories import (  # noqa: E402
    SQLiteAuditEventRepository,
    SQLiteDiscoveryRunRepository,
    SQLiteEmailDraftRepository,
    SQLiteEmailSendAttemptRepository,
    SQLiteFollowUpTaskRepository,
    SQLiteInboundEmailRepository,
    SQLiteLeadRepository,
    SQLiteReplyAnalysisRepository,
    SQLiteResearchRepository,
    SQLiteResearchRunRepository,
    SQLiteTaskRepository,
)
from src.infrastructure.website_fetcher import WebsiteFetcher  # noqa: E402
from src.infrastructure.yahoo_search_provider import YahooSearchProvider  # noqa: E402
from src.interfaces.http_api import ApiApplication  # noqa: E402

DATABASE = ROOT / "data" / "runtime" / "acquisition.db"
LOGGER = logging.getLogger("waimao.api")
logging.basicConfig(level=logging.INFO, format="%(message)s")


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
language_policy_path = ROOT / "config" / "language_policy.json"
language_policy = (
    json.loads(language_policy_path.read_text(encoding="utf-8"))
    if language_policy_path.exists()
    else {}
)
task_repository = SQLiteTaskRepository(DATABASE)
lead_repository = SQLiteLeadRepository(DATABASE)
research_repository = SQLiteResearchRepository(DATABASE)
research_run_repository = SQLiteResearchRunRepository(DATABASE)
discovery_run_repository = SQLiteDiscoveryRunRepository(DATABASE)
inbound_email_repository = SQLiteInboundEmailRepository(DATABASE)
reply_analysis_repository = SQLiteReplyAnalysisRepository(DATABASE)
email_draft_repository = SQLiteEmailDraftRepository(DATABASE)
email_send_attempt_repository = SQLiteEmailSendAttemptRepository(DATABASE)
follow_up_task_repository = SQLiteFollowUpTaskRepository(DATABASE)
audit_repository = SQLiteAuditEventRepository(DATABASE)
static_search_provider = GoogleSearchProvider(
    timeout=float(config_values.get("SEARCH_TIMEOUT_SECONDS", "15")),
    max_results_per_query=int(config_values.get("SEARCH_RESULTS_PER_QUERY", "10")),
    host=config_values.get("SEARCH_GOOGLE_HOST", "www.google.com.hk"),
)
browser_search_provider = None
if config_values.get("SEARCH_BROWSER_ENABLED", "true").lower() == "true":
    browser_search_provider = PlaywrightSearchProvider(
        timeout=float(config_values.get("SEARCH_BROWSER_TIMEOUT_SECONDS", "30")),
        max_results_per_query=int(config_values.get("SEARCH_RESULTS_PER_QUERY", "10")),
        host=config_values.get("SEARCH_GOOGLE_HOST", "www.google.com.hk"),
        executable_path=config_values.get("SEARCH_BROWSER_EXECUTABLE", ""),
        headless=config_values.get("SEARCH_BROWSER_HEADLESS", "true").lower() == "true",
        proxy=config_values.get(
            "SEARCH_BROWSER_PROXY", config_values.get("HTTPS_PROXY", "")
        ),
    )
bing_search_provider = (
    BingSearchProvider(
        timeout=float(config_values.get("SEARCH_TIMEOUT_SECONDS", "15")),
        max_results_per_query=int(config_values.get("SEARCH_RESULTS_PER_QUERY", "10")),
        host=config_values.get("SEARCH_BING_HOST", "www.bing.com"),
    )
    if config_values.get("SEARCH_BING_ENABLED", "true").lower() == "true"
    else None
)
yahoo_search_provider = (
    YahooSearchProvider(
        timeout=float(config_values.get("SEARCH_TIMEOUT_SECONDS", "15")),
        max_results_per_query=int(config_values.get("SEARCH_RESULTS_PER_QUERY", "10")),
        host=config_values.get("SEARCH_YAHOO_HOST", "search.yahoo.com"),
    )
    if config_values.get("SEARCH_YAHOO_ENABLED", "true").lower() == "true"
    else None
)
# Bing is the first live source because it provides a bounded HTML result page
# in the current local network; Google remains available as a fallback when it
# is reachable, without making a blocked Google session delay every search.
search_provider = FallbackSearchProvider(
    yahoo_search_provider, bing_search_provider, static_search_provider, browser_search_provider
)
try:
    deepseek_provider = DeepSeekProvider(DeepSeekConfig.from_env_file(ROOT / "config" / ".env"))
except (FileNotFoundError, ValueError):
    deepseek_provider = None
try:
    email_draft_service = (
        EmailDraftService(deepseek_provider, language_policy.get("country_languages", {}))
        if deepseek_provider
        else None
    )
except (FileNotFoundError, ValueError):
    email_draft_service = None
research_execution = (
    ResearchExecutionService(
        task_repository,
        ResearchWorkflow(
            task_repository,
            WebsiteFetcher(timeout=int(config_values.get("WEBSITE_FETCH_TIMEOUT_SECONDS", "15"))),
            deepseek_provider,
            research_repository,
            lead_repository,
        ),
        research_run_repository,
    )
    if deepseek_provider is not None
    else None
)
research_queue = (
    ResearchJobQueue(
        research_execution,
        research_run_repository,
        lead_repository,
        max_workers=int(config_values.get("RESEARCH_QUEUE_WORKERS", "2")),
        max_pending=int(config_values.get("RESEARCH_QUEUE_MAX_PENDING", "100")),
        timeout_seconds=int(config_values.get("RESEARCH_TIMEOUT_SECONDS", "120")),
    )
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
mailbox_sync = MailboxSyncService(lead_repository, inbound_email_repository, audit=audit_repository)
follow_up_task_service = FollowUpTaskService(follow_up_task_repository)
reply_analysis_service = ReplyAnalysisService(
    inbound_email_repository, reply_analysis_repository, follow_up_task_service
)
send_safety_service = SendSafetyService(
    SQLiteEmailDraftRepository(DATABASE), email_send_attempt_repository
)
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
if research_queue is not None:
    research_queue.recover()
acquisition_service = AcquisitionService(
    task_repository,
    lead_repository,
    search_provider=search_provider,
    audit_repository=audit_repository,
    website_reader=WebsiteFetcher(
        timeout=int(config_values.get("WEBSITE_FETCH_TIMEOUT_SECONDS", "15"))
    ),
    website_workers=int(config_values.get("WEBSITE_FETCH_WORKERS", "8")),
    website_page_limit=int(config_values.get("WEBSITE_FETCH_PAGE_LIMIT", "3")),
    external_source_limit=int(config_values.get("WEBSITE_EXTERNAL_SOURCE_LIMIT", "1")),
)
discovery_queue = DiscoveryJobQueue(
    acquisition_service,
    discovery_run_repository,
    max_workers=int(config_values.get("DISCOVERY_QUEUE_WORKERS", "1")),
    max_pending=int(config_values.get("DISCOVERY_QUEUE_MAX_PENDING", "2")),
    max_search_rounds=int(config_values.get("DISCOVERY_MAX_SEARCH_ROUNDS", "6")),
    research_queue=research_queue,
)
application = ApiApplication(
    task_repository,
    lead_repository,
    research_repository,
    email_draft_repository,
    email_drafts=email_draft_service,
    translation=TranslationService(GoogleMachineTranslationProvider()),
    audit=audit_repository,
    acquisition=acquisition_service,
    website_reader=WebsiteFetcher(
        timeout=int(config_values.get("WEBSITE_FETCH_TIMEOUT_SECONDS", "15"))
    ),
    research_execution=research_execution,
    research_runs=research_run_repository,
    research_queue=research_queue,
    discovery_queue=discovery_queue,
    discovery_runs=discovery_run_repository,
    mailbox=mailbox,
    mailbox_sync=mailbox_sync,
    inbound_emails=inbound_email_repository,
    reply_analysis=reply_analysis_service,
    reply_drafts=ReplyDraftService(deepseek_provider) if deepseek_provider else None,
    follow_up_tasks=follow_up_task_service,
    send_safety=send_safety_service,
    email_send=email_send_service,
    sending_enabled=config_values.get("ALI_SMTP_SENDING_ENABLED", "false").lower() == "true",
)


class Handler(BaseHTTPRequestHandler):
    def _handle(self, method, body=None):
        started = time.perf_counter()
        status, payload = application.handle(method, self.path, body)
        LOGGER.info(
            json.dumps(
                {
                    "event": "http_request",
                    "method": method,
                    "path": self.path.split("?", 1)[0],
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
                ensure_ascii=False,
            )
        )
        self._respond(status, payload)

    def _respond(self, status, payload):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        self._handle("POST", body)

    def do_PATCH(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        self._handle("PATCH", body)

    def log_message(self, *_args):
        return


if __name__ == "__main__":
    port = int(os.environ.get("WAIMAO_API_PORT", "8001"))
    host = os.environ.get("WAIMAO_API_HOST", "127.0.0.1")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
