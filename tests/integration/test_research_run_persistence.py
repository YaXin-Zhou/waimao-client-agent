from src.domain.research_run import ResearchRun, ResearchRunStatus
from src.infrastructure.sqlite_repositories import SQLiteResearchRunRepository


def test_research_run_survives_repository_recreation(tmp_path):
    database = tmp_path / "runs.db"
    run = ResearchRun.start(
        "task-1", "example.com", source_url="https://example.com",
        weights={"product": 40}, max_attempts=3,
    ).attempted()
    run = run.succeed(review_required=True)

    SQLiteResearchRunRepository(database).save(run)
    restored = SQLiteResearchRunRepository(database).get(run.id)

    assert restored == run
    assert restored.status is ResearchRunStatus.REVIEW_REQUIRED
    assert restored.step.value == "completed"
    assert restored.source_url == "https://example.com"
    assert restored.weights == (("product", 40),)
    assert restored.max_attempts == 3


def test_research_runs_can_be_listed_by_task(tmp_path):
    database = tmp_path / "runs.db"
    first = ResearchRun.start("task-1", "one.example").attempted()
    second = ResearchRun.start("task-1", "two.example").attempted()
    other = ResearchRun.start("task-2", "other.example").attempted()
    repository = SQLiteResearchRunRepository(database)
    for run in (first, second, other):
        repository.save(run)

    assert repository.list_for_task("task-1") == [first, second]
