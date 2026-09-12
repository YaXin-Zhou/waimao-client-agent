"""DuckDuckGo HTML search adapter for public company website discovery."""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import parse_qs, quote_plus, unquote, urlsplit
from urllib.request import Request, urlopen

from src.application.search_queries import build_search_queries_for_round
from src.domain.lead import LeadRecord, canonical_website_domain
from src.domain.task import AcquisitionCriteria, effective_candidate_limit
from src.infrastructure.google_search_provider import GoogleSearchProvider, SearchProviderError


class _DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_link = False
        self._href = ""
        self._text: list[str] = []
        self.results: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        if tag == "a" and "result__a" in set(attributes.get("class", "").split()):
            self._in_link = True
            self._href = attributes.get("href", "")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._in_link:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_link:
            title = " ".join("".join(self._text).split())
            if title and self._href:
                self.results.append((self._href, title))
            self._in_link, self._href, self._text = False, "", []


class DuckDuckGoSearchProvider:
    def __init__(self, opener: Callable[..., object] = urlopen, timeout: float = 15.0,
                 max_results_per_query: int = 10, host: str = "html.duckduckgo.com") -> None:
        if timeout <= 0 or max_results_per_query <= 0:
            raise ValueError("DuckDuckGo search timeout and page size must be positive")
        if not host.strip() or "/" in host:
            raise ValueError("DuckDuckGo search host must be a hostname")
        self._opener, self._timeout = opener, timeout
        self._max_results, self._host = max_results_per_query, host.strip()

    def search(self, criteria: AcquisitionCriteria) -> list[LeadRecord]:
        return self.search_round(criteria, 0)

    def search_round(self, criteria: AcquisitionCriteria, round_index: int = 0) -> list[LeadRecord]:
        target = effective_candidate_limit(criteria)
        suffix = ("", "supplier", "manufacturer", "company", "contact", "purchasing")[round_index % 6]
        records, seen = [], set()
        for base_query in build_search_queries_for_round(criteria, round_index):
            query = f"{base_query} {suffix}".strip()
            request = Request(f"https://{self._host}/html/?q={quote_plus(query)}&num={self._max_results}",
                              headers={"User-Agent": "Mozilla/5.0 (compatible; ClientResearch/1.0)"})
            try:
                html = self._opener(request, timeout=self._timeout).read().decode("utf-8", errors="replace")
            except Exception as error:
                raise SearchProviderError(f"DuckDuckGo search failed for query: {query}") from error
            parser = _DuckDuckGoResultParser()
            parser.feed(unescape(html))
            for href, title in parser.results:
                resolved = self._resolve_result_url(href)
                domain = canonical_website_domain(resolved)
                if (not GoogleSearchProvider._is_candidate(resolved, title)
                        or not self._is_query_relevant(query, title, resolved)
                        or not urlsplit(resolved).hostname or not domain or domain in seen):
                    continue
                seen.add(domain)
                records.append(LeadRecord(title, resolved, source_url=request.full_url,
                                          source_excerpt=title))
                if len(records) >= target:
                    return records
        if not records:
            raise SearchProviderError("DuckDuckGo search returned no public website results")
        return records

    @staticmethod
    def _resolve_result_url(href: str) -> str:
        parsed = urlsplit(href if href.startswith("http") else f"https:{href}")
        if parsed.hostname != "duckduckgo.com" or not parsed.path.startswith("/l/"):
            return href
        encoded = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(encoded) if encoded else ""

    @staticmethod
    def _is_query_relevant(query: str, title: str, url: str) -> bool:
        text = f"{title} {url}".lower()
        blocked = ("directory", "top 10", "top 100", "/companies/", "/search/", "list of",
                   "wiki", "recipe", "charity", "foundation", "forum", "news")
        if any(marker in text for marker in blocked):
            return False
        terms = {token for token in query.lower().split() if len(token) >= 4}
        return not terms or any(token in text for token in terms)
