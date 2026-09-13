"""搜索适配器组合：优先静态请求，必要时自动切换无界面浏览器。"""

from __future__ import annotations

import time
from urllib.parse import urlsplit

from src.domain.task import effective_candidate_limit
from src.infrastructure.google_search_provider import SearchChallengeError, SearchProviderError


class FallbackSearchProvider:
    def __init__(self, primary, fallback=None, *additional,
                 provider_interval_seconds: float = 0.0,
                 max_duration_seconds: float = 240.0,
                 sleep=time.sleep, clock=time.monotonic):
        if provider_interval_seconds < 0:
            raise ValueError("provider_interval_seconds must not be negative")
        if max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds must be positive")
        self._providers = tuple(
            provider for provider in (primary, fallback, *additional) if provider is not None
        )
        self._provider_interval_seconds = provider_interval_seconds
        self._max_duration_seconds = max_duration_seconds
        self._sleep = sleep
        self._clock = clock

    def search(self, criteria):
        return self._search(criteria, 0)

    def search_round(self, criteria, round_index: int = 0):
        return self._search(criteria, round_index)

    def _search(self, criteria, round_index: int):
        target = (
            effective_candidate_limit(criteria)
            if hasattr(criteria, "candidate_limit") or hasattr(criteria, "daily_limit")
            else 0
        )
        errors = []
        collected = []
        seen = set()
        started_at = self._clock()
        for provider_index, provider in enumerate(self._providers):
            elapsed = self._clock() - started_at
            if elapsed >= self._max_duration_seconds:
                raise SearchProviderError(
                    "search round exceeded its time limit; try again later"
                )
            if provider_index and self._provider_interval_seconds:
                remaining = self._max_duration_seconds - elapsed
                if remaining <= 0:
                    raise SearchProviderError(
                        "search round exceeded its time limit; try again later"
                    )
                self._sleep(min(self._provider_interval_seconds, remaining))
            try:
                search_round = getattr(provider, "search_round", None)
                records = (
                    search_round(criteria, round_index)
                    if callable(search_round)
                    else provider.search(criteria)
                )
            except SearchProviderError as error:
                if isinstance(error, SearchChallengeError):
                    raise
                errors.append(error)
                continue
            if not records:
                errors.append(
                    SearchProviderError(
                        f"{provider.__class__.__name__} returned no public website results"
                    )
                )
                continue
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
            if getattr(provider, "return_immediately_after_results", False):
                return collected
        if collected:
            return collected
        if errors:
            raise SearchProviderError(
                "all configured search providers failed: "
                + "; ".join(str(error) for error in errors)
            ) from errors[-1]
        raise SearchProviderError("no search provider is configured")

    @staticmethod
    def _record_key(record) -> str:
        website = str(getattr(record, "website", "")).strip()
        if website:
            parsed = urlsplit(website)
            return (parsed.hostname or website).lower().removeprefix("www.")
        return repr(record)
