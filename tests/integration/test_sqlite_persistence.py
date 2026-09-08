from src.application.acquisition_service import AcquisitionService
from src.domain.lead import LeadRecord
from src.domain.task import AcquisitionCriteria
from src.infrastructure.sqlite_repositories import SQLiteLeadRepository, SQLiteTaskRepository


def test_task_and_assessments_survive_repository_recreation(tmp_path):
    database = tmp_path / "acquisition.db"
    task_repository = SQLiteTaskRepository(database)
    lead_repository = SQLiteLeadRepository(database)
    service = AcquisitionService(task_repository, lead_repository)
    task = service.create_task(
        "Portable power leads",
        AcquisitionCriteria(product="portable power station", countries=("Germany",)),
    )
    service.assess_leads(
        task.id,
        [LeadRecord("Alpine Camp Supply", "https://alpine.example", "sales@alpine.example", "DE")],
        weights={"product_match": 30, "market_match": 20},
        signals_by_domain={"alpine.example": {"product_match": 30, "market_match": 20}},
    )

    reloaded_service = AcquisitionService(
        SQLiteTaskRepository(database), SQLiteLeadRepository(database)
    )

    assert reloaded_service.list_leads(task.id)[0].lead.company_name == "Alpine Camp Supply"
    assert reloaded_service.list_leads(task.id)[0].score.total == 50
