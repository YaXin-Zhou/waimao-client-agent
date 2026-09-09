"""搜索适配器组合：优先静态请求，必要时自动切换无界面浏览器。"""

from __future__ import annotations

from urllib.parse import urlsplit

from src.domain.task import effective_candidate_limit
from src.infrastructure.google_search_provider import SearchProviderError


class FallbackSearchProvider:
    def __init__(self, primary, fallback=None, *additional):
        self._providers = tuple(
            provider for provider in (primary, fallback, *additional) if provider is not None
        )

    def search(self, criteria):
        target = (
            effective_candidate_limit(criteria)
            if hasattr(criteria, "candidate_limit") or hasattr(criteria, "daily_limit")
            else 0
        )
        errors = []
        collected = []
        seen = set()
        for provider in self._providers:
            try:
                records = provider.search(criteria)
            except SearchProviderError as error:
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
