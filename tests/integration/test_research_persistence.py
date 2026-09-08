from src.domain.research import CustomerType, EvidenceStatus, ResearchResult
from src.infrastructure.sqlite_repositories import SQLiteResearchRepository


def test_research_report_survives_repository_recreation(tmp_path):
    database = tmp_path / "research.db"
    report = ResearchResult(
        company_name="Alpine Camp Supply",
        business_summary="Outdoor power equipment distributor.",
        customer_type=CustomerType.DISTRIBUTOR,
        products=("portable power stations",),
        country="Germany",
        confidence=0.88,
        evidence_url="https://alpine.example/about",
        evidence_status=EvidenceStatus.SUFFICIENT,
    )
    SQLiteResearchRepository(database).save("task-1", "alpine.example", report)

    restored = SQLiteResearchRepository(database).get("task-1", "alpine.example")

    assert restored == report
