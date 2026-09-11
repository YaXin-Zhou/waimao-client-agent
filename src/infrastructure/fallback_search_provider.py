"""搜索适配器组合：优先静态请求，必要时自动切换无界面浏览器。"""

from __future__ import annotations

import time
from urllib.parse import urlsplit

from src.domain.task import effective_candidate_limit
from src.infrastructure.google_search_provider import SearchProviderError


class FallbackSearchProvider:
    def __init__(
        self,
        primary,
        fallback=None,
        *additional,
        failure_cooldown_seconds: float = 0.0,
        stop_after_first_success: bool = False,
    ):
        if failure_cooldown_seconds < 0:
            raise ValueError("failure_cooldown_seconds must not be negative")
        self._providers = tuple(
            provider for provider in (primary, fallback, *additional) if provider is not None
        )
        self._failure_cooldown_seconds = failure_cooldown_seconds
        self._stop_after_first_success = stop_after_first_success
        self._failed_until: dict[int, float] = {}

    def search(self, criteria):
        return self._search(criteria, 0)

    def search_round(self, criteria, round_index: int = 0):
        return self._search(criteria, round_index)

    def remember_domains(self, domains):
        for provider in self._providers:
            remember = getattr(provider, "remember_domains", None)
            if callable(remember):
                remember(domains)

    def _search(self, criteria, round_index: int):
        target = (
            effective_candidate_limit(criteria)
            if hasattr(criteria, "candidate_limit") or hasattr(criteria, "daily_limit")
            else 0
        )
        errors = []
        collected = []
        seen = set()
        skipped = 0
        for provider in self._providers:
            failure_until = self._failed_until.get(id(provider), 0.0)
            if failure_until > time.monotonic():
                skipped += 1
                continue
            try:
                search_round = getattr(provider, "search_round", None)
                records = (
                    search_round(criteria, round_index)
                    if callable(search_round)
                    else provider.search(criteria)
                )
            except SearchProviderError as error:
                self._mark_failure(provider)
                errors.append(error)
                continue
            if not records:
                self._mark_failure(provider)
                errors.append(
                    SearchProviderError(
                        f"{provider.__class__.__name__} returned no public website results"
                    )
                )
                continue
            self._failed_until.pop(id(provider), None)
            if self._stop_after_first_success:
                return records
            # Preserve the old single-provider behavior for generic callers that
            # do not expose a task-sized candidate target.
            if target <= 0:
                return records
            for record in records:
                key = self._record_key(record)
                if key in seen:
                    continue
                seen.add(key)
                collected.append(record)
                if len(collected) >= target:
                    return collected[:target]
        if collected:
            return collected
        if errors:
            raise SearchProviderError(
                "all configured search providers failed: "
                + "; ".join(str(error) for error in errors)
            ) from errors[-1]
        if skipped:
            raise SearchProviderError(
                "search providers are cooling down after temporary failures; retry later"
            )
        raise SearchProviderError("no search provider is configured")

    def _mark_failure(self, provider) -> None:
        if self._failure_cooldown_seconds:
            self._failed_until[id(provider)] = (
                time.monotonic() + self._failure_cooldown_seconds
            )

    @staticmethod
    def _record_key(record) -> str:
        website = str(getattr(record, "website", "")).strip()
        if website:
            parsed = urlsplit(website)
            return (parsed.hostname or website).lower().removeprefix("www.")
        return repr(record)
