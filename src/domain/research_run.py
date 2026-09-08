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
    EXECUTING = "executing"
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

    @classmethod
    def start(cls, task_id: str, domain: str, request_key: str = "") -> "ResearchRun":
        return cls(id=str(uuid4()), task_id=task_id, domain=domain, request_key=request_key)

    def attempted(self) -> "ResearchRun":
        return replace(self, attempts=self.attempts + 1, step=ResearchRunStep.EXECUTING)

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
