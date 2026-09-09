"""获客发现运行记录及其可观察阶段。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import uuid4


class DiscoveryRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DiscoveryRunStep(StrEnum):
    QUEUED = "queued"
    SEARCHING = "searching"
    ENRICHING = "enriching"
    ASSESSING = "assessing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class DiscoveryRun:
    id: str
    task_id: str
    status: DiscoveryRunStatus = DiscoveryRunStatus.RUNNING
    step: DiscoveryRunStep = DiscoveryRunStep.QUEUED
    candidate_count: int = 0
    website_count: int = 0
    public_email_count: int = 0
    qualified_count: int = 0
    error: str = ""

    @classmethod
    def start(cls, task_id: str) -> "DiscoveryRun":
        return cls(id=str(uuid4()), task_id=task_id)

    def progress(self, step: DiscoveryRunStep, **counts: int) -> "DiscoveryRun":
        return replace(self, step=step, error="", **counts)

    def succeed(self, **counts: int) -> "DiscoveryRun":
        return replace(
            self,
            status=DiscoveryRunStatus.SUCCEEDED,
            step=DiscoveryRunStep.COMPLETED,
            error="",
            **counts,
        )

    def fail(self, error: str) -> "DiscoveryRun":
        return replace(
            self,
            status=DiscoveryRunStatus.FAILED,
            step=DiscoveryRunStep.FAILED,
            error=error,
        )
