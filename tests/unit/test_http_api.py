import json

from src.application.acquisition_service import AssessedLead
from src.domain.email_draft import EmailDraft
from src.domain.lead import CleanLead, LeadScore
from src.domain.research import CustomerType, EvidenceStatus, ResearchResult
from src.domain.task import AcquisitionCriteria, AcquisitionTask
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


class Research:
    def get(self, task_id, domain):
        return ResearchResult(
            "Alpine Energy", "Online distributor", CustomerType.DISTRIBUTOR,
            ("power station",), "Germany", .9, "https://alpine.example/about",
            EvidenceStatus.SUFFICIENT,
        )


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


class DraftGenerator:
    def generate(self, task_id, lead, research, template, product, sender_profile=None):
        return EmailDraft.create(
            task_id,
            lead.domain,
            lead.emails[0],
            "Generated",
            "Generated body",
            (research.evidence_url,),
        )


class Translation:
    def preview(self, draft, target):
        return {
            "draft_id": draft.id,
            "target_language": target,
            "subject": "中文主题",
            "body": "中文正文",
        }


def make_app():
    task = AcquisitionTask.create("Power station", AcquisitionCriteria(product="power station"))
    lead = CleanLead(
        "Alpine Energy", "alpine.example", ("sales@alpine.example",), "Germany", "complete"
    )
    draft = EmailDraft.create(
        task.id, lead.domain, lead.emails[0], "Subject", "Body", ("https://alpine.example/about",)
    )
    assessed = AssessedLead(lead, LeadScore(72, "B", {"product": 30}))
    app = ApiApplication(Tasks(task), Leads([assessed]), Research(), Drafts(draft))
    return app, task, draft


def test_api_returns_leads_and_research_detail():
    app, task, _ = make_app()

    status, payload = app.handle("GET", f"/api/tasks/{task.id}/leads/alpine.example")

    assert status == 200
    assert payload["lead"]["company_name"] == "Alpine Energy"
    assert payload["lead"]["website"] == "https://alpine.example"
    assert payload["research"]["evidence_status"] == "sufficient"
    assert payload["draft"]["recipient_email"] == "sales@alpine.example"


def test_api_returns_tasks_without_hardcoded_task_id():
    app, task, _ = make_app()

    status, payload = app.handle("GET", "/api/tasks")

    assert status == 200
    assert payload["items"][0]["id"] == task.id


def test_api_creates_task_from_form_configuration():
    app, _, _ = make_app()

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
    app, task, _ = make_app()

    status, payload = app.handle("GET", f"/api/tasks/{task.id}/leads")

    assert status == 200
    assert payload["items"][0]["lead"]["domain"] == "alpine.example"


def test_api_updates_contact_only_with_source_evidence_and_keeps_score():
    app, task, _ = make_app()

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
    assert payload["lead"]["emails"] == ("sales@alpine.example", "contact@alpine.example")
    assert payload["score"]["total"] == 72


def test_api_updates_existing_task_sender_profile():
    app, task, _ = make_app()

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


def test_api_assesses_external_records_with_request_configuration():
    app, task, _ = make_app()

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/assess",
        {
            "records": [{
                "company_name": " Alpine Energy ",
                "website": "https://www.alpine.example/contact",
                "email": "Sales@alpine.example",
                "country": "DE",
                "source_url": "https://alpine.example/contact",
                "source_excerpt": "Distributor contact",
            }],
            "weights": {"product_fit": 40, "country_fit": 30},
            "signals_by_domain": {
                "alpine.example": {"product_fit": 35, "country_fit": 30}
            },
        },
    )

    assert status == 200
    assert payload["items"][0]["lead"]["domain"] == "alpine.example"
    assert payload["items"][0]["score"]["total"] == 65


def test_api_rejects_non_object_scoring_configuration():
    app, task, _ = make_app()

    status, payload = app.handle(
        "POST", f"/api/tasks/{task.id}/assess", {"records": [], "weights": []}
    )

    assert status == 400
    assert "must be objects" in payload["error"]


def test_api_approval_updates_draft_without_sending():
    app, _, draft = make_app()

    status, payload = app.handle(
        "POST", f"/api/drafts/{draft.id}/approve", {"reviewer": "reviewer-1"}
    )

    assert status == 200
    assert payload["status"] == "approved"
    assert app._drafts.draft.recipient_email == "sales@alpine.example"


def test_api_returns_json_error_for_unknown_draft():
    app, _, _ = make_app()

    status, payload = app.handle(
        "POST", "/api/drafts/missing/reject", json.dumps({"reviewer": "r", "note": "x"})
    )

    assert status == 404
    assert payload["error"] == "Draft not found: missing"


def test_api_translates_draft_for_preview_without_replacing_source():
    app, _, draft = make_app()
    app._translation = Translation()

    status, payload = app.handle(
        "POST", f"/api/drafts/{draft.id}/translate", {"target_language": "zh-CN"}
    )

    assert status == 200
    assert payload["subject"] == "中文主题"
    assert payload["body"] == "中文正文"
    assert app._drafts.draft.subject == "Subject"


def test_api_generates_and_persists_reviewable_draft():
    app, task, draft = make_app()
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


def test_api_draft_requires_research_before_generation():
    app, task, _ = make_app()
    app._email_drafts = DraftGenerator()
    app._research.get = lambda task_id, domain: None

    status, payload = app.handle(
        "POST",
        f"/api/tasks/{task.id}/leads/alpine.example/draft",
        {"template": "Intro for {company}", "product": "power station"},
    )

    assert status == 400
    assert payload["error"] == "research report is required before drafting"
