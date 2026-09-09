"""将已同步的收件邮件分类并保存；重复分析复用已有结果。"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.reply_analysis import classify_inbound


@dataclass(frozen=True)
class ReplyAnalysisBatchResult:
    analyzed: int
    reused: int
    skipped_system_notifications: int
    items: tuple


class ReplyAnalysisService:
    def __init__(self, messages, analyses, follow_up_tasks=None):
        self._messages = messages
        self._analyses = analyses
        self._follow_up_tasks = follow_up_tasks

    def analyze_task(self, task_id: str) -> ReplyAnalysisBatchResult:
        analyzed = 0
        reused = 0
        skipped_system_notifications = 0
        items = []
        for message in self._messages.list_for_task(task_id):
            if message.is_system_notification:
                skipped_system_notifications += 1
                continue
            existing = self._analyses.get_by_message_id(message.message_id)
            if existing is not None:
                reused += 1
                items.append(existing)
                continue
            analysis = classify_inbound(message)
            self._analyses.save(analysis)
            if self._follow_up_tasks is not None:
                self._follow_up_tasks.create_for_analysis(analysis)
            analyzed += 1
            items.append(analysis)
        return ReplyAnalysisBatchResult(
            analyzed, reused, skipped_system_notifications, tuple(items)
        )

    def list_for_task(self, task_id: str):
        return self._analyses.list_for_task(task_id)

    def get_by_message_id(self, message_id: str):
        return self._analyses.get_by_message_id(message_id)
