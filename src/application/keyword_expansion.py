"""Use the text model to suggest bounded discovery terms.

The model is an optional planner only. It never decides country or email
qualification, and invalid/failed suggestions are silently discarded so the
deterministic local search path remains available.
"""

from __future__ import annotations

import re
from typing import Protocol

from src.domain.task import AcquisitionCriteria, configured_research_terms


class JsonProvider(Protocol):
    def generate_json(self, prompt: str) -> dict: ...


class DeepSeekKeywordExpander:
    def __init__(self, provider: JsonProvider, max_terms: int = 8) -> None:
        if max_terms <= 0:
            raise ValueError("max_terms must be positive")
        self._provider = provider
        self._max_terms = max_terms
        self._cache: dict[tuple[str, ...], tuple[str, ...]] = {}

    def expand(self, criteria: AcquisitionCriteria) -> tuple[str, ...]:
        base_terms = configured_research_terms(criteria)
        # Industry and customer type shape buyer intent. Include them in the
        # cache key so changing the task conditions does not silently reuse a
        # term set produced for a different market. Countries remain outside
        # the model terms and are enforced deterministically by query building.
        cache_key = tuple(
            value.casefold()
            for value in (
                *base_terms,
                "__industries__",
                *criteria.industries,
                "__customer_types__",
                *criteria.customer_types,
            )
        )
        if cache_key in self._cache:
            return self._cache[cache_key]
        if not base_terms:
            return ()
        prompt = (
            "Suggest concise English B2B search terms for discovering companies "
            "that may buy or use the configured products/services. Return JSON "
            "with exactly one field: search_terms, an array of strings. "
            "Include synonyms, manufacturing terminology, and buyer-intent terms. "
            "Do not add countries, URLs, email addresses, company names, or claims. "
            "Do not repeat the supplied terms. Keep each term between 2 and 60 "
            f"characters and return at most {self._max_terms} terms.\n"
            f"Configured terms: {', '.join(base_terms)}\n"
            f"Target industries: {', '.join(criteria.industries)}\n"
            f"Target customer types: {', '.join(criteria.customer_types)}"
        )
        try:
            data = self._provider.generate_json(prompt)
            raw_terms = data.get("search_terms", [])
            if not isinstance(raw_terms, list):
                raise ValueError("search_terms must be an array")
            expanded = tuple(
                value
                for value in dict.fromkeys(
                    self._valid_term(item) for item in raw_terms
                )
                if value
            )[: self._max_terms]
        except Exception:
            expanded = ()
        self._cache[cache_key] = expanded
        return expanded

    @staticmethod
    def _valid_term(value: object) -> str:
        term = " ".join(str(value).split()).strip()
        if not 2 <= len(term) <= 60:
            return ""
        if re.search(r"https?://|www\.|@", term, re.IGNORECASE):
            return ""
        if any(char in term for char in "<>\n\r"):
            return ""
        return term
