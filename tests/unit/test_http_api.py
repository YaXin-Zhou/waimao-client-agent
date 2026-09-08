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
        },
    )

    assert status == 201
    assert payload["name"] == "France solar distributors"
    assert payload["status"] == "draft"
    assert app._tasks.get(payload["id"]).criteria.countries == ("France",)


def test_api_returns_lead_list():
    app, task, _ = make_app()

    status, payload = app.handle("GET", f"/api/tasks/{task.id}/leads")

    assert status == 200
    assert payload["items"][0]["lead"]["domain"] == "alpine.example"


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
