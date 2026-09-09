from src.application.acquisition_service import AcquisitionService
from src.domain.audit_event import AuditEvent
from src.domain.lead import LeadRecord
from src.domain.task import AcquisitionCriteria
from src.infrastructure.sqlite_repositories import (
    SQLiteAuditEventRepository,
    SQLiteLeadRepository,
    SQLiteTaskRepository,
)


def test_task_and_assessments_survive_repository_recreation(tmp_path):
    database = tmp_path / "acquisition.db"
    task_repository = SQLiteTaskRepository(database)
    lead_repository = SQLiteLeadRepository(database)
    service = AcquisitionService(task_repository, lead_repository)
    task = service.create_task(
        "Portable power leads",
        AcquisitionCriteria(
            product="portable power station",
            countries=("Germany",),
            qualified_lead_limit=3,
            candidate_limit=20,
            minimum_qualification_score=45,
            require_public_email=True,
        ),
    )
    service.assess_leads(
        task.id,
            [
                LeadRecord(
                    "Alpine Camp Supply",
                    "https://alpine.example",
                    "sales@alpine.example",
                    "DE",
                    "https://alpine.example/contact",
                    "Alpine Camp Supply public sales contact for portable power stations",
                )
            ],
        weights={"product_match": 30, "market_match": 20},
        signals_by_domain={"alpine.example": {"product_match": 30, "market_match": 20}},
    )

    reloaded_service = AcquisitionService(
        SQLiteTaskRepository(database), SQLiteLeadRepository(database)
    )

    assert reloaded_service.list_leads(task.id)[0].lead.company_name == "Alpine Camp Supply"
    assert reloaded_service.list_leads(task.id)[0].score.total == 50
    reloaded_task = SQLiteTaskRepository(database).get(task.id)
    assert reloaded_task.criteria.qualified_lead_limit == 3
    assert reloaded_task.criteria.candidate_limit == 20
    assert reloaded_service.list_leads(task.id)[0].qualified


def test_audit_events_survive_repository_recreation(tmp_path):
    database = tmp_path / "acquisition.db"
    event = AuditEvent.status_change(
        "email_draft",
        "draft-1",
        "review",
        "reviewer-1",
        "pending_review",
        "revision_required",
        "Please add product evidence",
    )

    SQLiteAuditEventRepository(database).save(event)
    events = SQLiteAuditEventRepository(database).list_for_entity("email_draft", "draft-1")

    assert events[0].actor == "reviewer-1"
    assert events[0].note == "Please add product evidence"
