"""Brave HTML search adapter for public company website discovery."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Callable
from urllib.parse import quote_plus, urlsplit
from urllib.request import Request, urlopen

from src.application.search_queries import build_search_queries_for_round
from src.domain.lead import LeadRecord, canonical_website_domain
from src.domain.task import AcquisitionCriteria, effective_candidate_limit
from src.infrastructure.google_search_provider import GoogleSearchProvider, SearchProviderError


class _BraveResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._href = ""
        self._text: list[str] = []
        self.results: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag != "a" or self._href:
            return
        href = dict(attrs).get("href", "")
        parsed = urlsplit(href)
        if parsed.scheme in {"http", "https"} and parsed.hostname:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._href:
            return
        title = " ".join("".join(self._text).split())
        self.results.append((self._href, title))
        self._href = ""
        self._text = []


class BraveSearchProvider:
    def __init__(self, opener: Callable[..., object] = urlopen, timeout: float = 15.0,
                 max_results_per_query: int = 10, host: str = "search.brave.com") -> None:
        if timeout <= 0 or max_results_per_query <= 0:
            raise ValueError("Brave search timeout and page size must be positive")
        if not host.strip() or "/" in host:
            raise ValueError("Brave search host must be a hostname")
        self._opener, self._timeout = opener, timeout
        self._max_results, self._host = max_results_per_query, host.strip()

    def search(self, criteria: AcquisitionCriteria) -> list[LeadRecord]:
        return self.search_round(criteria, 0)

    def search_round(self, criteria: AcquisitionCriteria, round_index: int = 0) -> list[LeadRecord]:
        target = effective_candidate_limit(criteria)
        suffix = ("", "manufacturer", "supplier", "company", "contact", "purchasing")[round_index % 6]
        records, seen = [], set()
        for base_query in build_search_queries_for_round(criteria, round_index):
            query = f"{base_query} {suffix}".strip()
            request = Request(f"https://{self._host}/search?q={quote_plus(query)}&source=web",
                              headers={"User-Agent": "Mozilla/5.0 (compatible; ClientResearch/1.0)"})
            try:
                html = self._opener(request, timeout=self._timeout).read().decode("utf-8", errors="replace")
            except Exception as error:
                raise SearchProviderError(f"Brave search failed for query: {query}") from error
            parser = _BraveResultParser()
            parser.feed(html)
            for url, title in parser.results:
                domain = canonical_website_domain(url)
                if (not GoogleSearchProvider._is_candidate(url, title)
                        or not self._is_query_relevant(query, title, url)
                        or not domain or domain in seen):
                    continue
                seen.add(domain)
                records.append(LeadRecord(title or domain, url, source_url=request.full_url,
                                          source_excerpt=title or domain))
                if len(records) >= target:
                    return records
        if not records:
            raise SearchProviderError("Brave search returned no public website results")
        return records

    @staticmethod
    def _is_query_relevant(query: str, title: str, url: str) -> bool:
        text = f"{title} {url}".lower()
        blocked = ("directory", "top 10", "top 100", "list of", "wiki", "recipe",
                   "charity", "foundation", "forum", "news", "linkedin.com")
        if any(marker in text for marker in blocked):
            return False
        terms = {term for term in query.lower().split() if len(term) >= 4}
        return not terms or any(term in text for term in terms)
