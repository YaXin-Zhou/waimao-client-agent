"""研究流程编排：将官网采集、背调、评分和持久化连接起来。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.application.research_service import research_company
from src.application.research_signals import build_research_signals
from src.domain.lead import CleanLead, LeadScore, score_lead
from src.domain.research import ResearchResult
from src.domain.research_run import ResearchRunStep


class TaskReader(Protocol):
    def get(self, task_id: str): ...


class WebsiteReader(Protocol):
    def fetch(self, url: str): ...


class ResearchWriter(Protocol):
    def save(self, task_id: str, domain: str, report: ResearchResult) -> None: ...


class LeadScoreWriter(Protocol):
    def update_score(self, task_id: str, domain: str, score: LeadScore) -> None: ...


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
        lead_score_writer: LeadScoreWriter | None = None,
    ):
        self._tasks = tasks
        self._websites = website_reader
        self._ai = ai_provider
        self._reports = research_writer
        self._lead_scores = lead_score_writer

    def run(
        self,
        task_id: str,
        lead: CleanLead,
        source_url: str,
        weights: dict[str, int],
        progress=None,
    ) -> ResearchAssessment:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if progress:
            progress(ResearchRunStep.FETCHING)
        source_urls = tuple(
            dict.fromkeys([source_url] + [url for url, _excerpt in lead.sources if url])
        )
        documents = []
        for url in source_urls:
            try:
                documents.append(self._websites.fetch(url))
            except (ConnectionError, OSError, TimeoutError):
                if url == source_url:
                    raise
        if progress:
            progress(ResearchRunStep.ANALYZING)
        if not documents:
            raise ValueError("no research source could be fetched")
        combined_text = "\n\n".join(
            f"SOURCE URL: {document.url}\n{document.text}" for document in documents
        )
        research = research_company(
            self._ai,
            lead,
            documents[0].url,
            combined_text,
            task.criteria.research_fields,
            tuple(document.url for document in documents),
        )
        if progress:
            progress(ResearchRunStep.SCORING)
        signals = build_research_signals(lead, research, task.criteria)
        score = score_lead(lead, weights, signals)
        if progress:
            progress(ResearchRunStep.PERSISTING)
        self._reports.save(task_id, lead.domain, research)
        if self._lead_scores is not None:
            self._lead_scores.update_score(task_id, lead.domain, score)
        return ResearchAssessment(research=research, score=score)
