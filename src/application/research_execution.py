"""带重试和执行记录的研究流程外壳。"""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from src.application.research_workflow import ResearchAssessment
from src.domain.lead import CleanLead
from src.domain.research import EvidenceStatus
from src.domain.research_run import ResearchRun, ResearchRunStep


@dataclass(frozen=True)
class ResearchExecutionResult:
    run: ResearchRun
    assessment: ResearchAssessment


class ResearchTimeoutError(TimeoutError):
    """研究运行超过整体截止时间。"""


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
        timeout_seconds: int = 120,
        run: ResearchRun | None = None,
    ) -> ResearchExecutionResult:
        if self._tasks.get(task_id) is None:
            raise KeyError(f"Task not found: {task_id}")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        run = run or ResearchRun.start(
            task_id, lead.domain, timeout_seconds=timeout_seconds
        )
        timeout_seconds = run.timeout_seconds or timeout_seconds
        deadline = monotonic() + timeout_seconds
        self._runs.save(run)
        last_error: Exception | None = None
        for _ in range(max_attempts):
            run = run.attempted()
            self._runs.save(run)
            try:
                self._check_deadline(deadline)
                assessment = self._workflow.run(
                    task_id, lead, source_url, weights,
                    progress=lambda step: self._progress(run, step, deadline),
                )
                self._check_deadline(deadline)
            except (ConnectionError, OSError, TimeoutError) as error:
                last_error = error
                continue
            except Exception as error:
                run = run.fail(str(error))
                self._runs.save(run)
                raise
            review_required = self._requires_human_review(task_id, assessment)
            run = run.succeed(review_required=review_required)
            self._runs.save(run)
            return ResearchExecutionResult(run, assessment)
        run = run.fail(str(last_error) if last_error else "research failed")
        self._runs.save(run)
        raise last_error or RuntimeError("research failed")

    def _progress(self, run: ResearchRun, step: ResearchRunStep, deadline: float) -> None:
        self._check_deadline(deadline)
        self._runs.save(run.progress(step))

    @staticmethod
    def _check_deadline(deadline: float) -> None:
        if monotonic() > deadline:
            raise ResearchTimeoutError("research run exceeded timeout_seconds")

    def _requires_human_review(self, task_id: str, assessment: ResearchAssessment) -> bool:
        if assessment.research.evidence_status is EvidenceStatus.INSUFFICIENT:
            return True
        task = self._tasks.get(task_id)
        if task is None:
            return True
        return any(
            definition.human_review
            and (
                assessment.research.custom_fields.get(definition.key) is None
                or assessment.research.custom_fields[definition.key].status != "verified"
            )
            for definition in task.criteria.research_fields
        )
