import json

from src.application.acquisition_service import AssessedLead
from src.domain.email_draft import EmailDraft
from src.domain.lead import CleanLead, LeadScore
from src.domain.research import CustomerType, EvidenceStatus, ResearchResult
from src.domain.task import AcquisitionCriteria, AcquisitionTask
from src.interfaces.http_api import ApiApplication


class Tasks:
    def __init__(self, task):
        self.task = task

    def get(self, task_id):
        return self.task if task_id == self.task.id else None


class Leads:
    def __init__(self, results):
        self.results = results

    def list_assessments(self, task_id):
        return self.results


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
    assert payload["research"]["evidence_status"] == "sufficient"


def test_api_returns_lead_list():
    app, task, _ = make_app()

    status, payload = app.handle("GET", f"/api/tasks/{task.id}/leads")

    assert status == 200
    assert payload["items"][0]["lead"]["domain"] == "alpine.example"


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
