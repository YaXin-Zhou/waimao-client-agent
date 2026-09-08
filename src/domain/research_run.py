"""研究执行记录和可恢复状态。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import uuid4


class ResearchRunStatus(StrEnum):
    RUNNING = "running"
    REVIEW_REQUIRED = "review_required"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ResearchRunStep(StrEnum):
    QUEUED = "queued"
    FETCHING = "fetching"
    ANALYZING = "analyzing"
    SCORING = "scoring"
    PERSISTING = "persisting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ResearchRun:
    id: str
    task_id: str
    domain: str
    status: ResearchRunStatus = ResearchRunStatus.RUNNING
    step: ResearchRunStep = ResearchRunStep.QUEUED
    attempts: int = 0
    error: str = ""
    request_key: str = ""
    source_url: str = ""
    weights: tuple[tuple[str, int], ...] = ()
    max_attempts: int = 2

    @classmethod
    def start(
        cls, task_id: str, domain: str, request_key: str = "", source_url: str = "",
        weights: dict[str, int] | None = None, max_attempts: int = 2,
    ) -> "ResearchRun":
        return cls(
            id=str(uuid4()), task_id=task_id, domain=domain, request_key=request_key,
            source_url=source_url, weights=tuple(sorted((weights or {}).items())),
            max_attempts=max_attempts,
        )

    def attempted(self) -> "ResearchRun":
        return replace(self, attempts=self.attempts + 1, step=ResearchRunStep.FETCHING)

    def progress(self, step: ResearchRunStep) -> "ResearchRun":
        if self.status is not ResearchRunStatus.RUNNING:
            return self
        return replace(self, step=step, error="")

    def succeed(self, review_required: bool = False) -> "ResearchRun":
        status = (
            ResearchRunStatus.REVIEW_REQUIRED
            if review_required
            else ResearchRunStatus.SUCCEEDED
        )
        return replace(self, status=status, step=ResearchRunStep.COMPLETED, error="")

    def fail(self, error: str) -> "ResearchRun":
        return replace(
            self,
            status=ResearchRunStatus.FAILED,
            step=ResearchRunStep.FAILED,
            error=error,
        )
