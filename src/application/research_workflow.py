"""研究流程编排：将官网采集、背调、评分和持久化连接起来。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.application.research_service import research_company
from src.application.research_signals import build_research_signals
from src.domain.lead import CleanLead, LeadScore, score_lead
from src.domain.research import ResearchResult


class TaskReader(Protocol):
    def get(self, task_id: str): ...


class WebsiteReader(Protocol):
    def fetch(self, url: str): ...


class ResearchWriter(Protocol):
    def save(self, task_id: str, domain: str, report: ResearchResult) -> None: ...


@dataclass(frozen=True)
class ResearchAssessment:
    research: ResearchResult
    score: LeadScore


class ResearchWorkflow:
    def __init__(
        self,
        tasks: TaskReader,
        website_reader: WebsiteReader,
        ai_provider,
        research_writer: ResearchWriter,
    ):
        self._tasks = tasks
        self._websites = website_reader
        self._ai = ai_provider
        self._reports = research_writer

    def run(
        self,
        task_id: str,
        lead: CleanLead,
        source_url: str,
        weights: dict[str, int],
    ) -> ResearchAssessment:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        document = self._websites.fetch(source_url)
        research = research_company(self._ai, lead, document.url, document.text)
        signals = build_research_signals(lead, research, task.criteria)
        score = score_lead(lead, weights, signals)
        self._reports.save(task_id, lead.domain, research)
        return ResearchAssessment(research=research, score=score)
