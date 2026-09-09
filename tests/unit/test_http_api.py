import json
from dataclasses import replace

from src.application.acquisition_service import AcquisitionService, AssessedLead
from src.application.reply_analysis import classify_inbound
from src.application.reply_analysis_service import ReplyAnalysisService
from src.application.reply_draft_service import ReplyDraftService
from src.domain.audit_event import AuditEvent
from src.domain.custom_research import ResearchFieldValue
from src.domain.email_draft import EmailDraft
from src.domain.inbound_email import InboundEmail
from src.domain.lead import CleanLead, LeadRecord, LeadScore
from src.domain.research import CustomerType, EvidenceStatus, ResearchResult
from src.domain.research_run import ResearchRun
from src.domain.task import AcquisitionCriteria, AcquisitionTask, TaskStatus
from src.infrastructure.google_search_provider import SearchProviderError
from src.infrastructure.website_fetcher import PublicEmail, SourceDocument
from src.interfaces.http_api import ApiApplication


class Tasks:
    def __init__(self, task):
        self.tasks = [task]

    def get(self, task_id):
        return next((task for task in self.tasks if task.id == task_id), None)

    def list(self):
        return list(self.tasks)

    def save(self, task):
        self.tasks = [item for item in self.tasks if item.id != task.id]
        self.tasks.append(task)


class Leads:
    def __init__(self, results):
        self.results = results

    def list_assessments(self, task_id):
        return self.results

    def save_assessments(self, task_id, results):
        self.results = results


class SearchProvider:
    def search(self, criteria):
        return [
            LeadRecord(
                "Discovered Alpine",
                "discovered.example",
                "sales@discovered.example",
                "Germany",
                "https://discovered.example",
                "Google result for portable power station",
            )
        ]


class ContactReader:
    def fetch(self, url):
        return SourceDocument(
            url,
            "Contact",
            "Contact Alpine",
            (PublicEmail("info@alpine.example", url, "Contact info@alpine.example"),),
        )


class Research:
    def __init__(self):
        self.report = None

    def get(self, task_id, domain):
        self.report = self.report or ResearchResult(
            "Alpine Energy",
            "Online distributor",
            CustomerType.DISTRIBUTOR,
            ("power station",),
            "Germany",
            0.9,
            "https://alpine.example/about",
            EvidenceStatus.SUFFICIENT,
            website_language="en",
            custom_fields={
                "buyer_role": ResearchFieldValue(
                    value="Sourcing Manager",
                    status="verified",
                    confidence=0.88,
                    sources=("https://alpine.example/contact",),
                    checked_at="2026-09-09T10:00:00Z",
                )
            },
            evidence_urls=(
                "https://alpine.example/about",
                "https://alpine.example/contact",
            ),
        )
        return self.report

    def save(self, task_id, domain, report):
        self.report = report


class Drafts:
    def __init__(self, draft):
        self.draft = draft

    def get(self, draft_id):
        return self.draft if draft_id == self.draft.id else None

    def save(self, draft):
        self.draft = draft

    def latest_for_lead(self, task_id, lead_domain):
        return (
            self.draft
            if self.draft.task_id == task_id and self.draft.lead_domain == lead_domain
            else None
        )


class AuditEvents:
    def __init__(self):
        self.events = []

    def save(self, event: AuditEvent):
        self.events.append(event)

    def list_for_entity(self, entity_type, entity_id):
        return [
            event
            for event in self.events
            if event.entity_type == entity_type and event.entity_id == entity_id
        ]


class DraftGenerator:
    def generate(
        self,
        task_id,
        lead,
        research,
        template,
        product,
        sender_profile=None,
        requested_language="auto",
    ):
        return EmailDraft.create(
            task_id,
            lead.domain,
            lead.emails[0],
            "Generated",
            "Generated body",
            (research.evidence_url,),
        )


class InboundMessages:
    def __init__(self, message):
        self.message = message

    def get_by_message_id(self, message_id):
        return self.message if message_id == self.message.message_id else None

    def list_for_task(self, task_id):
        return [self.message]


class ReplyAnalyses:
    def __init__(self, analysis):
        self.analysis = analysis

    def get_by_message_id(self, message_id):
        return self.analysis if message_id == self.analysis.message_id else None

    def list_for_task(self, task_id):
        return [self.analysis]


class ReplyDraftProvider:
    def generate_json(self, prompt):
        return {
            "subject": "Re: Your price request",
            "body": "Thank you. We will prepare the requested information.",
        }


class Translation:
    def preview(self, draft, target):
        return {
            "draft_id": draft.id,
            "target_language": target,
            "subject": "中文主题",
            "body": "中文正文",
        }


class ResearchRuns:
    def __init__(self, runs):
        self.runs = runs

    def list_for_task(self, task_id):
        return [run for run in self.runs if run.task_id == task_id]


class ResearchExecution:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def execute(self, task_id, lead, source_url, weights, max_attempts=2, timeout_seconds=120):
        self.calls.append(
            (task_id, lead.domain, source_url, weights, max_attempts, timeout_seconds)
        )
        return self.result


def make_app():
    task = AcquisitionTask.create("Power station", AcquisitionCriteria(product="power station"))
    lead = CleanLead(
        "Alpine Energy", "alpine.example", ("sales@alpine.example",), "Germany", "complete"
    )
    draft = EmailDraft.create(
        task.id, lead.domain, lead.emails[0], "Subject", "Body", ("https://alpine.example/about",)
    )
    assessed = AssessedLead(lead, LeadScore(72, "B", {"product": 30}))
    audit = AuditEvents()
    app = ApiApplication(Tasks(task), Leads([assessed]), Research(), Drafts(draft), audit=audit)
    return app, task, draft, audit


def test_api_returns_leads_and_research_detail():
    app, task, _, _ = make_app()

    status, payload = app.handle("GET", f"/api/tasks/{task.id}/leads/alpine.example")

    assert status == 200
    assert payload["lead"]["company_name"] == "Alpine Energy"
    assert payload["lead"]["website"] == "https://alpine.example"
    assert payload["research"]["evidence_status"] == "sufficient"
    assert payload["research"]["country_conflict"] is False
    assert payload["research"]["evidence_urls"] == [
        "https://alpine.example/about",
        "https://alpine.example/contact",
    ]
    assert payload["research"]["custom_fields"]["buyer_role"]["value"] == "Sourcing Manager"
    assert payload["research"]["custom_fields"]["buyer_role"]["sources"] == [
        "https://alpine.example/contact"
    ]
    assert payload["draft"]["recipient_email"] == "sales@alpine.example"


def test_api_reviews_custom_research_field_and_persists_status():
    app, task, _, _ = make_app()

    status, payload = app.handle(
        "PATCH",
        f"/api/tasks/{task.id}/leads/alpine.example/research-fields/buyer_role",
        {"status": "verified", "value": "Strategic Sourcing Manager"},
    )

    assert status == 200
    assert payload["custom_fields"]["buyer_role"]["status"] == "verified"
    assert payload["custom_fields"]["buyer_role"]["value"] == "Strategic Sourcing Manager"
    assert payload["custom_fields"]["buyer_role"]["confidence"] == 1.0
    assert app._research.report.custom_fields["buyer_role"].status == "verified"


def test_api_updates_existing_task_criteria():
    task = AcquisitionTask.create("Configurable", AcquisitionCriteria(product="old service"))
    tasks = Tasks(task)
    leads = Leads([])
    app = ApiApplication(
        tasks, leads, Research(), Drafts(None), acquisition=AcquisitionService(tasks, leads)
    )

    status, payload = app.handle(
        "PATCH",
        f"/api/tasks/{task.id}/criteria",
        json.dumps(
            {
                "criteria": {
                    "product": "CNC precision parts",
                    "business_offerings": [
                        {
                            "name": "CNC machining",
                            "key": "cnc_parts",
                            "keywords": ["CNC"],
                        }
                    ],
                    "research_fields": [
                        {
                            "name": "Buyer role",
                            "key": "buyer_role",
                        }
                    ],
                }
            }
        ),
    )

    assert status == 200
    assert payload["criteria"]["product"] == "CNC precision parts"
    assert payload["criteria"]["business_offerings"][0]["key"] == "cnc_parts"
    assert payload["criteria"]["research_fields"][0]["key"] == "buyer_role"


def test_api_returns_tasks_without_hardcoded_task_id():
    app, task, _, _ = make_app()

    status, payload = app.handle("GET", "/api/tasks")

    assert status == 200
    assert payload["items"][0]["id"] == task.id


def test_api_exposes_research_run_list_and_research_result():
    app, task, _, _ = make_app()
    result = type(
        "Result",
        (),
        {
            "run": ResearchRun.start(task.id, "alpine.example").attempted().succeed(),
            "assessment": type(
                "Assessment",
                (),
                {
                    "research": Research().get(task.id, "alpine.example"),
                    "score": LeadScore(82, "A", {"product": 40}),
                },
            )(),
        },
    )()
    execution = ResearchExecution(result)
    runs = ResearchRuns([result.run])
    app = ApiApplication(
        app._tasks,
        app._leads,
        app._research,
        app._drafts,
        acquisition=app._acquisition,
        audit=app._audit,
        research_execution=execution,
        research_runs=runs,
    )

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/leads/alpine.example/research",
        {
            "source_url": "https://alpine.example/about",
            "weights": {"product": 40},
            "max_attempts": 3,
        },
    )
    assert status == 200
    assert payload["run"]["status"] == "succeeded"
    assert payload["research"]["evidence_status"] == "sufficient"
    assert execution.calls[0][4] == 3

    status, payload = app.handle("GET", f"/api/tasks/{task.id}/research-runs")
    assert status == 200
    assert payload["items"][0]["domain"] == "alpine.example"


def test_api_creates_task_from_form_configuration():
    app, _, _, _ = make_app()

    status, payload = app.handle(
        "POST",
        "/api/tasks",
        {
            "name": "France solar distributors",
            "criteria": {
                "product": "portable solar generator",
                "countries": ["France"],
                "customer_types": ["distributor"],
                "daily_limit": 5,
            },
            "sender_profile": {
                "company_name": "Northstar Trading",
                "contact_name": "Li Ming",
                "position": "Sales Manager",
            },
        },
    )

    assert status == 201
    assert payload["name"] == "France solar distributors"
    assert payload["status"] == "draft"
    assert app._tasks.get(payload["id"]).criteria.countries == ("France",)
    assert app._tasks.get(payload["id"]).sender_profile.company_name == "Northstar Trading"


def test_api_returns_lead_list():
    app, task, _, _ = make_app()

    status, payload = app.handle("GET", f"/api/tasks/{task.id}/leads")

    assert status == 200
    assert payload["items"][0]["lead"]["domain"] == "alpine.example"
    assert payload["summary"]["candidate_count"] == 1
    assert payload["summary"]["funnel"]["public_email_count"] == 1


def test_api_lead_list_sanitizes_legacy_source_evidence():
    app, task, _, _ = make_app()
    result = app._leads.results[0]
    app._leads.results[0] = replace(
        result,
        lead=replace(
            result.lead,
            sources=(
                ("https://alpine.example", "Public sales contact"),
                ("https://alpine.example", "hero-banner.png"),
                ("https://alpine.example", "contoso@example.com"),
            ),
        ),
    )

    status, payload = app.handle("GET", f"/api/tasks/{task.id}/leads")

    assert status == 200
    assert payload["items"][0]["lead"]["sources"] == [
        ["https://alpine.example", "Public sales contact"]
    ]


def test_api_updates_contact_only_with_source_evidence_and_keeps_score():
    app, task, _, _ = make_app()

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/leads/alpine.example/contact",
        {
            "email": "contact@alpine.example",
            "source_url": "https://alpine.example/contact",
            "source_excerpt": "Public sales contact",
        },
    )

    assert status == 200
    assert payload["lead"]["emails"] == ["sales@alpine.example", "contact@alpine.example"]
    assert payload["score"]["total"] == 72


def test_api_updates_existing_task_sender_profile():
    app, task, _, _ = make_app()

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/sender-profile",
        {
            "company_name": "Northstar Trading",
            "contact_name": "Li Ming",
            "position": "Sales Manager",
        },
    )

    assert status == 200
    assert payload["sender_profile"]["company_name"] == "Northstar Trading"
    assert app._tasks.get(task.id).sender_profile.contact_name == "Li Ming"


def test_api_transitions_task_and_records_audit_event():
    app, task, _, audit = make_app()

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/transition",
        {"status": "ready", "actor": "reviewer-1", "note": "Configuration checked"},
    )

    assert status == 200
    assert payload["status"] == TaskStatus.READY.value
    assert audit.events[0].entity_type == "acquisition_task"
    assert audit.events[0].from_status == "draft"

    status, events = app.handle("GET", f"/api/tasks/{task.id}/audit-events")

    assert status == 200
    assert events["items"][0]["to_status"] == "ready"


def test_api_rejects_invalid_task_transition():
    app, task, _, _ = make_app()

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/transition",
        {"status": "completed", "actor": "reviewer-1"},
    )

    assert status == 400
    assert "Invalid task transition" in payload["error"]


def test_api_assesses_external_records_with_request_configuration():
    app, task, _, _ = make_app()

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/assess",
        {
            "records": [
                {
                    "company_name": " Alpine Energy ",
                    "website": "https://www.alpine.example/contact",
                    "email": "Sales@alpine.example",
                    "country": "DE",
                    "source_url": "https://alpine.example/contact",
                    "source_excerpt": "Distributor contact",
                }
            ],
            "weights": {"product_fit": 40, "country_fit": 30},
            "signals_by_domain": {"alpine.example": {"product_fit": 35, "country_fit": 30}},
        },
    )

    assert status == 200
    assert payload["items"][0]["lead"]["domain"] == "alpine.example"
    assert payload["items"][0]["score"]["total"] == 65


def test_api_discovers_and_assesses_using_configured_search_provider():
    app, task, _, _ = make_app()
    app._acquisition = AcquisitionService(app._tasks, app._leads, search_provider=SearchProvider())

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/discover",
        {"weights": {"product_match": 40}, "signals_by_domain": {}},
    )

    assert status == 200
    assert payload["items"][0]["lead"]["domain"] == "discovered.example"
    assert payload["items"][0]["lead"]["sources"][0][0] == "https://discovered.example"
    assert payload["summary"]["candidate_count"] == 1
    assert payload["summary"]["qualified_count"] == 1
    assert payload["summary"]["shortfall"] == task.criteria.qualified_lead_limit - 1
    assert payload["summary"]["funnel"] == {
        "website_count": 1,
        "public_email_count": 1,
        "website_evidence_count": 1,
        "product_evidence_count": 1,
    }


def test_api_returns_retryable_search_error_without_creating_results():
    app, task, _, _ = make_app()

    class BlockedSearchProvider:
        def search(self, criteria):
            raise SearchProviderError("Google consent or unusual-traffic page")

    app._acquisition = AcquisitionService(
        app._tasks, app._leads, search_provider=BlockedSearchProvider()
    )

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/discover",
        {"weights": {}, "signals_by_domain": {}},
    )

    assert status == 503
    assert payload == {
        "error": "Google consent or unusual-traffic page",
        "code": "search_provider_unavailable",
        "retryable": True,
    }


def test_api_imports_browser_discovery_results_through_same_assessment_pipeline():
    app, task, _, _ = make_app()

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/discover/import",
        {
            "source_mode": "browser",
            "records": [
                {
                    "company_name": "Visible Search Result",
                    "website": "https://visible.example/contact",
                    "country": "Germany",
                    "source_url": "https://www.google.com.hk/search?q=solar+generator",
                    "source_excerpt": "Visible Google result excerpt",
                }
            ],
            "weights": {"evidence_quality": 5},
            "signals_by_domain": {},
        },
    )

    assert status == 200
    assert payload["items"][0]["lead"]["domain"] == "visible.example"
    assert payload["items"][0]["lead"]["sources"] == [
        ["https://www.google.com.hk/search?q=solar+generator", "Visible Google result excerpt"]
    ]


def test_api_rejects_non_browser_discovery_imports():
    app, task, _, _ = make_app()

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/discover/import",
        {"source_mode": "manual", "records": []},
    )

    assert status == 400
    assert payload["error"] == "browser discovery import requires source_mode=browser"


def test_api_discovers_public_contacts_without_model_and_keeps_evidence():
    app, task, _, _ = make_app()
    app._website_reader = ContactReader()

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/leads/alpine.example/contacts/discover",
        {},
    )

    assert status == 200
    assert payload["lead"]["emails"] == ["sales@alpine.example", "info@alpine.example"]
    assert payload["lead"]["sources"][-1] == [
        "https://alpine.example",
        "Contact info@alpine.example",
    ]


def test_api_rejects_non_object_scoring_configuration():
    app, task, _, _ = make_app()

    status, payload = app.handle(
        "POST", f"/api/tasks/{task.id}/assess", {"records": [], "weights": []}
    )

    assert status == 400
    assert "must be objects" in payload["error"]


def test_api_approval_updates_draft_without_sending():
    app, _, draft, audit = make_app()

    status, payload = app.handle(
        "POST", f"/api/drafts/{draft.id}/approve", {"reviewer": "reviewer-1"}
    )

    assert status == 200
    assert payload["status"] == "approved"
    assert app._drafts.draft.recipient_email == "sales@alpine.example"
    assert len(audit.events) == 1
    assert audit.events[0].from_status == "pending_review"
    assert audit.events[0].to_status == "approved"

    status, events = app.handle("GET", f"/api/drafts/{draft.id}/audit-events")

    assert status == 200
    assert events["items"][0]["actor"] == "reviewer-1"


def test_api_returns_json_error_for_unknown_draft():
    app, _, _, _ = make_app()

    status, payload = app.handle(
        "POST", "/api/drafts/missing/reject", json.dumps({"reviewer": "r", "note": "x"})
    )

    assert status == 404
    assert payload["error"] == "Draft not found: missing"


def test_api_translates_draft_for_preview_without_replacing_source():
    app, _, draft, _ = make_app()
    app._translation = Translation()

    status, payload = app.handle(
        "POST", f"/api/drafts/{draft.id}/translate", {"target_language": "zh-CN"}
    )

    assert status == 200
    assert payload["subject"] == "中文主题"
    assert payload["body"] == "中文正文"
    assert app._drafts.draft.subject == "Subject"


def test_api_generates_and_persists_reviewable_draft():
    app, task, draft, _ = make_app()
    app._email_drafts = DraftGenerator()

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/leads/alpine.example/draft",
        {"template": "Intro for {company} about {product}", "product": "power station"},
    )

    assert status == 201
    assert payload["status"] == "pending_review"
    assert payload["recipient_email"] == "sales@alpine.example"
    assert app._drafts.draft.id == payload["id"]


def test_api_generates_reply_draft_from_analyzed_customer_message():
    app, task, _, _ = make_app()
    message = InboundEmail.create(
        "9",
        "<customer-reply@example>",
        "",
        (),
        "buyer@alpine.example",
        ("sales@alpine.example",),
        "Re: quote",
        "Please send your price.",
        "2026-09-09T10:00:00+00:00",
        task.id,
        "alpine.example",
    )
    analysis = classify_inbound(message)
    app = ApiApplication(
        app._tasks,
        app._leads,
        app._research,
        app._drafts,
        acquisition=app._acquisition,
        audit=app._audit,
        inbound_emails=InboundMessages(message),
        reply_analysis=ReplyAnalysisService(InboundMessages(message), ReplyAnalyses(analysis)),
        reply_drafts=ReplyDraftService(ReplyDraftProvider()),
    )

    status, payload = app.handle(
        "POST", f"/api/tasks/{task.id}/reply-drafts", {"message_id": message.message_id}
    )

    assert status == 201
    assert payload["recipient_email"] == "buyer@alpine.example"
    assert payload["status"] == "pending_review"


def test_api_draft_requires_research_before_generation():
    app, task, _, _ = make_app()
    app._email_drafts = DraftGenerator()
    app._research.get = lambda task_id, domain: None

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/leads/alpine.example/draft",
        {"template": "Intro for {company}", "product": "power station"},
    )

    assert status == 400
    assert payload["error"] == "research report is required before drafting"
