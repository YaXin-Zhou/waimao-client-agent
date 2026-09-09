"""搜索适配器组合：优先静态请求，必要时自动切换无界面浏览器。"""

from __future__ import annotations

from src.infrastructure.google_search_provider import SearchProviderError


class FallbackSearchProvider:
    def __init__(self, primary, fallback=None):
        self._primary = primary
        self._fallback = fallback

    def search(self, criteria):
        try:
            return self._primary.search(criteria)
        except SearchProviderError as primary_error:
            if self._fallback is None:
                raise
            try:
                return self._fallback.search(criteria)
            except SearchProviderError as fallback_error:
                raise SearchProviderError(
                    f"static search failed and browser fallback failed: {fallback_error}"
                ) from primary_error
