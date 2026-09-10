"""Local machine translation adapters."""

from __future__ import annotations

import sys
from pathlib import Path

class LocalArgosTranslationProvider:
    """Translate with an installed Argos Translate model."""

    @staticmethod
    def _ensure_translation_model(source: str, target: str) -> None:
        import argostranslate.translate as translate

        try:
            if translate.get_translation_from_codes(source, target) is not None:
                return
        except (AttributeError, KeyError):
            pass

        # PyInstaller bundles the model under the executable directory. Install
        # it once into Argos' local package store when the EXE starts using it.
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        model_dirs = sorted((bundle_root / "argos-packages").glob("translate-en_zh-*"))
        if not model_dirs:
            raise RuntimeError("local translation model is not installed")
        import argostranslate.package as package

        package.install_from_path(str(model_dirs[-1]))

    def translate(self, text: str, source: str, target: str) -> str:
        if not text.strip():
            return text

        import argostranslate.translate as translate

        # Argos uses language codes, not the browser-style ``auto`` and
        # ``zh-CN`` values used by the HTTP contract. Drafts are generated in
        # English, so ``auto`` is safely mapped to the installed en->zh model.
        source = "en" if source == "auto" else source
        target = "zh" if target == "zh-CN" else target
        self._ensure_translation_model(source, target)

        translated = translate.translate(text, source, target)
        if not translated or "Error 500 (Server Error)" in translated:
            raise RuntimeError("local Argos translation returned an invalid result")
        return translated


# Import-compatible name for older integrations. This is now local and does
# not delegate to Google or another external translation service.
GoogleMachineTranslationProvider = LocalArgosTranslationProvider
