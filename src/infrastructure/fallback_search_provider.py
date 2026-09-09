"""搜索适配器组合：优先静态请求，必要时自动切换无界面浏览器。"""

from __future__ import annotations

from src.infrastructure.google_search_provider import SearchProviderError


class FallbackSearchProvider:
    def __init__(self, primary, fallback=None, *additional):
        self._providers = tuple(
            provider for provider in (primary, fallback, *additional) if provider is not None
        )

    def search(self, criteria):
        errors = []
        for provider in self._providers:
            try:
                return provider.search(criteria)
            except SearchProviderError as error:
                errors.append(error)
        if errors:
            raise SearchProviderError(
                "all configured search providers failed: "
                + "; ".join(str(error) for error in errors)
            ) from errors[-1]
        raise SearchProviderError("no search provider is configured")
