"""带重试和执行记录的研究流程外壳。"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.research_workflow import ResearchAssessment
from src.domain.lead import CleanLead
from src.domain.research import EvidenceStatus
from src.domain.research_run import ResearchRun


@dataclass(frozen=True)
class ResearchExecutionResult:
    run: ResearchRun
    assessment: ResearchAssessment


class ResearchExecutionService:
    def __init__(self, tasks, workflow, run_repository):
        self._tasks = tasks
        self._workflow = workflow
        self._runs = run_repository

    def execute(
        self,
        task_id: str,
        lead: CleanLead,
        source_url: str,
        weights: dict[str, int],
        max_attempts: int = 2,
    ) -> ResearchExecutionResult:
        if self._tasks.get(task_id) is None:
            raise KeyError(f"Task not found: {task_id}")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        run = ResearchRun.start(task_id, lead.domain)
        self._runs.save(run)
        last_error: Exception | None = None
        for _ in range(max_attempts):
            run = run.attempted()
            self._runs.save(run)
            try:
                assessment = self._workflow.run(task_id, lead, source_url, weights)
            except (ConnectionError, OSError, TimeoutError) as error:
                last_error = error
                continue
            except Exception as error:
                run = run.fail(str(error))
                self._runs.save(run)
                raise
            review_required = assessment.research.evidence_status is EvidenceStatus.INSUFFICIENT
            run = run.succeed(review_required=review_required)
            self._runs.save(run)
            return ResearchExecutionResult(run, assessment)
        run = run.fail(str(last_error) if last_error else "research failed")
        self._runs.save(run)
        raise last_error or RuntimeError("research failed")
