from src.domain.research_run import ResearchRun, ResearchRunStatus
from src.infrastructure.sqlite_repositories import SQLiteResearchRunRepository


def test_research_run_survives_repository_recreation(tmp_path):
    database = tmp_path / "runs.db"
    run = ResearchRun.start("task-1", "example.com").attempted()
    run = run.succeed(review_required=True)

    SQLiteResearchRunRepository(database).save(run)
    restored = SQLiteResearchRunRepository(database).get(run.id)

    assert restored == run
    assert restored.status is ResearchRunStatus.REVIEW_REQUIRED
