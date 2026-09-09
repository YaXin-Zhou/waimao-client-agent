from src.application.research_workflow import ResearchWorkflow
from src.domain.lead import CleanLead
from src.domain.research import CustomerType, EvidenceStatus
from src.domain.task import AcquisitionCriteria, AcquisitionTask
from src.infrastructure.website_fetcher import SourceDocument


class FakeTaskRepository:
    def __init__(self, task):
        self.task = task

    def get(self, task_id):
        return self.task if task_id == self.task.id else None


class FakeFetcher:
    def fetch(self, url):
        return SourceDocument(
            url, "About Alpine", "Alpine distributes portable power stations in Germany."
        )


class MultiSourceFetcher(FakeFetcher):
    def __init__(self):
        self.urls = []

    def fetch(self, url):
        self.urls.append(url)
        return SourceDocument(
            url, "Source", f"Alpine source confirms portable power stations: {url}"
        )


class FakeProvider:
    def generate_json(self, prompt):
        return {
            "business_summary": "Distributor of portable power stations.",
            "customer_type": "distributor",
            "products": ["portable power stations"],
            "country": "Germany",
            "confidence": 0.9,
        }


class FakeResearchRepository:
    def __init__(self):
        self.items = {}

    def save(self, task_id, domain, report):
        self.items[(task_id, domain)] = report


def test_workflow_connects_fetch_research_score_and_persistence():
    task = AcquisitionTask.create(
        "Germany power leads",
        AcquisitionCriteria(product="portable power station", countries=("Germany",)),
    )
    repository = FakeResearchRepository()
    lead = CleanLead("Alpine", "alpine.example", ("sales@alpine.example",), "Germany", "complete")
    workflow = ResearchWorkflow(FakeTaskRepository(task), FakeFetcher(), FakeProvider(), repository)

    assessment = workflow.run(
        task.id,
        lead,
        "https://alpine.example/about",
        weights={
            "product_match": 30,
            "market_match": 20,
            "email_quality": 15,
            "evidence_quality": 5,
        },
    )

    assert assessment.research.customer_type is CustomerType.DISTRIBUTOR
    assert assessment.research.evidence_status is EvidenceStatus.SUFFICIENT
    assert assessment.score.total == 70
    assert repository.items[(task.id, "alpine.example")] == assessment.research


def test_workflow_fetches_lead_sources_and_preserves_the_successful_source_set():
    task = AcquisitionTask.create(
        "Germany power leads",
        AcquisitionCriteria(product="portable power station", countries=("Germany",)),
    )
    repository = FakeResearchRepository()
    fetcher = MultiSourceFetcher()
    lead = CleanLead(
        "Alpine",
        "alpine.example",
        ("sales@alpine.example",),
        "Germany",
        "complete",
        sources=(
            ("https://alpine.example/about", "about"),
            ("https://alpine.example/team", "team"),
        ),
    )
    workflow = ResearchWorkflow(FakeTaskRepository(task), fetcher, FakeProvider(), repository)

    assessment = workflow.run(
        task.id,
        lead,
        "https://alpine.example/about",
        weights={"product_match": 30, "market_match": 20},
    )

    assert fetcher.urls == ["https://alpine.example/about", "https://alpine.example/team"]
    assert assessment.research.evidence_urls == tuple(fetcher.urls)
