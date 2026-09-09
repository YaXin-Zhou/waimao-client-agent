"""Bing HTML 搜索适配器，作为 Google 受限时的自动第二来源。"""

from __future__ import annotations

import base64
from html import unescape
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import parse_qs, quote_plus, urlsplit
from urllib.request import Request, urlopen

from src.application.search_queries import build_search_queries
from src.domain.lead import LeadRecord, canonical_website_domain
from src.domain.task import AcquisitionCriteria, effective_candidate_limit
from src.infrastructure.google_search_provider import GoogleSearchProvider, SearchProviderError


class _BingResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_result = False
        self._in_heading = False
        self._in_title = False
        self._href = ""
        self._text: list[str] = []
        self.results: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        classes = set(attributes.get("class", "").split())
        if tag == "li" and "b_algo" in classes:
            self._in_result = True
        elif self._in_result and tag == "h2":
            self._in_heading = True
        elif self._in_result and self._in_heading and tag == "a" and not self._href:
            href = attributes.get("href", "")
            if href:
                self._href = href
                self._text = []
                self._in_title = True

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_title:
            title = " ".join("".join(self._text).split())
            if title and self._href:
                self.results.append((self._href, title))
            self._href = ""
            self._text = []
            self._in_title = False
        elif tag == "h2":
            self._in_heading = False
        elif tag == "li" and self._in_result:
            self._in_result = False


class BingSearchProvider:
    def __init__(
        self,
        opener: Callable[..., object] = urlopen,
        timeout: float = 15.0,
        max_results_per_query: int = 10,
        host: str = "www.bing.com",
    ) -> None:
        if timeout <= 0 or max_results_per_query <= 0:
            raise ValueError("Bing search timeout and page size must be positive")
        if not host.strip() or "/" in host:
            raise ValueError("Bing search host must be a hostname")
        self._opener = opener
        self._timeout = timeout
        self._max_results = max_results_per_query
        self._host = host.strip()

    def search(self, criteria: AcquisitionCriteria) -> list[LeadRecord]:
        candidate_limit = effective_candidate_limit(criteria)
        records: list[LeadRecord] = []
        seen_domains: set[str] = set()
        for query in build_search_queries(criteria):
            for start in range(1, candidate_limit + 1, self._max_results):
                url = (
                    f"https://{self._host}/search?q={quote_plus(query)}"
                    f"&count={self._max_results}&first={start}"
                )
                request = Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; ClientResearch/1.0)"},
                )
                try:
                    response = self._opener(request, timeout=self._timeout)
                    html = response.read().decode("utf-8", errors="replace")
                except Exception as error:
                    raise SearchProviderError(f"Bing search failed for query: {query}") from error
                parser = _BingResultParser()
                parser.feed(unescape(html))
                added = 0
                for href, title in parser.results:
                    parsed = urlsplit(href)
                    resolved = self._resolve_result_url(href)
                    parsed = urlsplit(resolved)
                    domain = canonical_website_domain(resolved)
                    if (
                        not GoogleSearchProvider._is_candidate(resolved, title)
                        or not parsed.hostname
                        or not domain
                    ):
                        continue
                    if domain in seen_domains:
                        continue
                    seen_domains.add(domain)
                    records.append(
                        LeadRecord(
                            company_name=title,
                            website=resolved,
                            source_url=url,
                            source_excerpt=title,
                        )
                    )
                    added += 1
                    if len(records) >= candidate_limit:
                        return records
                if added == 0:
                    break
        if not records:
            raise SearchProviderError("Bing search returned no public website results")
        return records

    @staticmethod
    def _resolve_result_url(href: str) -> str:
        parsed = urlsplit(href)
        if not (parsed.hostname or "").endswith("bing.com"):
            return href
        token = parse_qs(parsed.query).get("u", [""])[0]
        if not token.startswith("a1"):
            return ""
        try:
            encoded = token[2:]
            encoded += "=" * (-len(encoded) % 4)
            return base64.urlsafe_b64decode(encoded).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return ""
