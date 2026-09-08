"""Google HTML 搜索适配器。

该适配器只采集搜索结果中的公开链接和页面标题，不猜测邮箱，也不承担
清洗、评分或背调职责。浏览器/其他搜索服务可以在同一 SearchProvider 边界替换它。
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Callable
from urllib.parse import parse_qs, quote_plus, urlsplit
from urllib.request import Request, urlopen

from src.application.search_queries import build_search_queries
from src.domain.lead import LeadRecord
from src.domain.task import AcquisitionCriteria


class SearchProviderError(RuntimeError):
    """搜索服务不可用、返回异常页面或无法解析时抛出。"""


class _GoogleResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._href = ""
        self._text: list[str] = []
        self.results: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag != "a" or self._href:
            return
        href = dict(attrs).get("href", "")
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._href:
            return
        title = " ".join("".join(self._text).split())
        if title:
            self.results.append((self._href, title))
        self._href = ""
        self._text = []


class GoogleSearchProvider:
    """通过 Google 的公开 HTML 结果页获取有限数量候选官网。"""

    def __init__(
        self,
        opener: Callable[..., object] = urlopen,
        timeout: float = 15.0,
        max_results_per_query: int = 10,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_results_per_query <= 0:
            raise ValueError("max_results_per_query must be positive")
        self._opener = opener
        self._timeout = timeout
        self._max_results = max_results_per_query

    def search(self, criteria: AcquisitionCriteria) -> list[LeadRecord]:
        results: list[LeadRecord] = []
        seen_urls: set[str] = set()
        for query in build_search_queries(criteria):
            request = Request(
                f"https://www.google.com/search?q={quote_plus(query)}&num={self._max_results}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; ClientResearch/1.0)"},
            )
            try:
                response = self._opener(request, timeout=self._timeout)
                html = response.read().decode("utf-8", errors="replace")
            except Exception as error:  # network/HTTP errors must not become empty results
                raise SearchProviderError(f"Google search failed for query: {query}") from error
            if self._requires_browser(html):
                raise SearchProviderError(
                    "Google returned a JavaScript-only or consent page; use the browser adapter"
                )
            parser = _GoogleResultParser()
            parser.feed(html)
            for href, title in parser.results:
                url = self._result_url(href)
                if not self._is_candidate(url) or url in seen_urls:
                    continue
                seen_urls.add(url)
                results.append(
                    LeadRecord(
                        company_name=title,
                        website=url,
                        source_url=url,
                        source_excerpt=f"Google result for: {query}",
                    )
                )
                if len(results) >= criteria.daily_limit:
                    return results
        return results

    @staticmethod
    def _result_url(href: str) -> str:
        parsed = urlsplit(href)
        if parsed.path == "/url":
            return parse_qs(parsed.query).get("q", [""])[0]
        return href

    @staticmethod
    def _is_candidate(url: str) -> bool:
        parsed = urlsplit(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not (
            parsed.hostname or ""
        ).endswith("google.com")

    @staticmethod
    def _requires_browser(html: str) -> bool:
        markers = ("/httpservice/retry/enablejs", "enable javascript", "consent.google")
        lowered = html.lower()
        return any(marker in lowered for marker in markers)
