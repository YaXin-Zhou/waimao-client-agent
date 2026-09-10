"""Local machine translation adapters."""

from __future__ import annotations


class LocalArgosTranslationProvider:
    """Translate with an installed Argos Translate model."""

    def translate(self, text: str, source: str, target: str) -> str:
        if not text.strip():
            return text

        import argostranslate.translate as translate

        # Argos uses language codes, not the browser-style ``auto`` and
        # ``zh-CN`` values used by the HTTP contract. Drafts are generated in
        # English, so ``auto`` is safely mapped to the installed en->zh model.
        source = "en" if source == "auto" else source
        target = "zh" if target == "zh-CN" else target

        translated = translate.translate(text, source, target)
        if not translated or "Error 500 (Server Error)" in translated:
            raise RuntimeError("local Argos translation returned an invalid result")
        return translated


# Import-compatible name for older integrations. This is now local and does
# not delegate to Google or another external translation service.
GoogleMachineTranslationProvider = LocalArgosTranslationProvider
