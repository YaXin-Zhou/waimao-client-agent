"""Google web translation adapter via deep-translator; no LLM/API token."""

from __future__ import annotations


class GoogleMachineTranslationProvider:
    def translate(self, text: str, source: str, target: str) -> str:
        from deep_translator import GoogleTranslator

        return GoogleTranslator(source=source, target=target).translate(text)
