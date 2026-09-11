"""非大模型翻译服务：只负责预览，不修改原始草稿。"""

from __future__ import annotations

from typing import Protocol

from src.domain.email_draft import EmailDraft


class TranslationProvider(Protocol):
    def translate(self, text: str, source: str, target: str) -> str: ...


class TranslationService:
    def __init__(self, provider: TranslationProvider):
        self._provider = provider
        self._cache: dict[tuple[str, str, str], str] = {}

    def preview(self, draft: EmailDraft, target: str = "zh-CN") -> dict:
        if target != "zh-CN":
            raise ValueError("only zh-CN preview is supported")
        return {
            "draft_id": draft.id,
            "source_language": "auto",
            "target_language": target,
            "provider": "machine_translation",
            "subject": self._translate(draft.subject, target),
            "body": self._translate(draft.body, target),
            "is_preview": True,
        }

    def _translate(self, text: str, target: str) -> str:
        key = (text, "auto", target)
        if key not in self._cache:
            self._cache[key] = self._provider.translate(text, "auto", target)
        return self._cache[key]
