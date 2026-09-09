from src.application.acquisition_service import AssessedLead
from src.application.research_workflow import ResearchWorkflow
from src.domain.lead import CleanLead, LeadScore
from src.domain.research import CustomerType, EvidenceStatus
from src.domain.task import AcquisitionCriteria, AcquisitionTask
from src.infrastructure.memory_repositories import InMemoryLeadRepository
from src.infrastructure.sqlite_repositories import SQLiteLeadRepository
from src.infrastructure.website_fetcher import SourceDocument


class Tasks:
    def __init__(self, task):
        self.task = task

    def get(self, task_id):
        return self.task if task_id == self.task.id else None


class Fetcher:
    def fetch(self, url):
        return SourceDocument(
            url,
            "About Alpine",
            "Alpine distributes portable power stations in Germany.",
        )


class Provider:
    def generate_json(self, prompt):
        return {
            "business_summary": "Distributor of portable power stations.",
            "customer_type": CustomerType.DISTRIBUTOR.value,
            "products": ["portable power stations"],
            "country": "Germany",
            "confidence": 0.9,
        }


def _run(task, leads, reports):
    lead = leads.list_assessments(task.id)[0].lead
    workflow = ResearchWorkflow(Tasks(task), Fetcher(), Provider(), reports, leads)
    return workflow.run(
        task.id,
        lead,
        "https://alpine.example/about",
        {"product_match": 30, "market_match": 20, "email_quality": 15, "evidence_quality": 5},
    )


def test_research_score_is_written_back_to_memory_leads():
    task = AcquisitionTask.create(
        "Germany power leads",
        AcquisitionCriteria(
            product="portable power station", countries=("Germany",)
        ),
    )
    leads = InMemoryLeadRepository()
    leads.save_assessments(
        task.id,
        [
            AssessedLead(
                CleanLead(
                    "Alpine",
                    "alpine.example",
                    ("sales@alpine.example",),
                    "Germany",
                    "complete",
                    sources=(("https://www.google.com/search?q=alpine", "Search result"),),
                ),
                LeadScore(0, "D", {}),
            )
        ],
    )

    result = _run(task, leads, type("Reports", (), {"save": lambda self, *_args: None})())

    assert result.score.total == 70
    assert leads.list_assessments(task.id)[0].score.total == 70
    assert leads.list_assessments(task.id)[0].lead.sources == (
        ("https://www.google.com/search?q=alpine", "Search result"),
        (
            "https://alpine.example/about",
            "Alpine distributes portable power stations in Germany.",
        ),
    )


def test_research_score_is_written_back_to_sqlite_leads(tmp_path):
    task = AcquisitionTask.create(
        "Germany power leads",
        AcquisitionCriteria(
            product="portable power station", countries=("Germany",)
        ),
    )
    leads = SQLiteLeadRepository(tmp_path / "score.db")
    leads.save_assessments(
        task.id,
        [
            AssessedLead(
                CleanLead(
                    "Alpine",
                    "alpine.example",
                    ("sales@alpine.example",),
                    "Germany",
                    "complete",
                    sources=(("https://www.google.com/search?q=alpine", "Search result"),),
                ),
                LeadScore(0, "D", {}),
            )
        ],
    )

    result = _run(task, leads, type("Reports", (), {"save": lambda self, *_args: None})())

    assert result.research.evidence_status is EvidenceStatus.SUFFICIENT
    assert leads.list_assessments(task.id)[0].score.total == 70
    assert leads.list_assessments(task.id)[0].lead.sources[1][0] == (
        "https://alpine.example/about"
    )
