from src.application.acquisition_service import AssessedLead
from src.domain.lead import CleanLead, LeadScore
from src.infrastructure.memory_repositories import InMemoryLeadRepository


def _assessed(domain: str) -> AssessedLead:
    return AssessedLead(
        lead=CleanLead(domain, domain, (f"info@{domain}",), "Germany", "complete"),
        score=LeadScore(60, "B", {"product_match": 30, "market_match": 20, "email_quality": 10}),
        qualified=True,
    )


def test_memory_repository_accumulates_search_rounds_by_domain():
    repository = InMemoryLeadRepository()
    repository.save_assessments("task", [_assessed("first.de")])
    repository.save_assessments("task", [_assessed("second.de"), _assessed("first.de")])

    rows = repository.list_assessments("task")
    assert [row.lead.domain for row in rows] == ["first.de", "second.de"]
