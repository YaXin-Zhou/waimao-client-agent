"""Language selection rules for outbound email drafts."""

from __future__ import annotations

import re
from dataclasses import dataclass

SUPPORTED_LANGUAGES = {
    "English": "English",
    "Spanish": "Spanish",
    "Russian": "Russian",
    "German": "German",
    "French": "French",
    "Italian": "Italian",
    "Portuguese": "Portuguese",
    "Chinese": "Chinese",
}


@dataclass(frozen=True)
class LanguageDecision:
    language: str
    source: str
    confidence: float
    requires_review: bool


def resolve_language(
    requested: str,
    country: str,
    website_language: str = "",
    country_languages: dict[str, str] | None = None,
) -> LanguageDecision:
    """Resolve an email language without treating country as a certainty."""
    explicit = _canonical(requested)
    if explicit and explicit.lower() not in {"auto", "automatic", "unknown"}:
        return LanguageDecision(explicit, "task configuration", 1.0, False)

    website = _canonical(website_language)
    if website and website.lower() != "unknown":
        return LanguageDecision(website, "website language", 0.95, False)

    mapping = country_languages or {}
    market = _canonical(mapping.get(country.strip(), ""))
    if market:
        return LanguageDecision(market, "target market", 0.70, False)

    return LanguageDecision("English", "fallback", 0.35, True)


def detect_reply_language(text: str) -> str:
    """Best-effort, non-LLM detection used only to guide reply drafting."""
    if re.search(r"[\u4e00-\u9fff]", text):
        return "Chinese"
    if re.search(r"[\u0400-\u04ff]", text):
        return "Russian"
    lowered = f" {text.lower()} "
    scores = {
        "Spanish": sum(lowered.count(token) for token in (" el ", " la ", " que ", " gracias ")),
        "German": sum(lowered.count(token) for token in (" der ", " die ", " und ", " danke ")),
        "French": sum(lowered.count(token) for token in (" le ", " les ", " nous ", " merci ")),
        "Italian": sum(lowered.count(token) for token in (" il ", " che ", " per ", " grazie ")),
        "Portuguese": sum(
            lowered.count(token)
            for token in (" o ", " que ", " para ", " obrigado ")
        ),
    }
    language, score = max(scores.items(), key=lambda item: item[1], default=("English", 0))
    return language if score > 0 else "English"


def _canonical(value: str) -> str:
    text = str(value or "").strip()
    aliases = {
        "en": "English", "es": "Spanish", "ru": "Russian", "de": "German",
        "fr": "French", "it": "Italian", "pt": "Portuguese", "zh": "Chinese",
    }
    return aliases.get(text.lower(), text if text in SUPPORTED_LANGUAGES else "")
