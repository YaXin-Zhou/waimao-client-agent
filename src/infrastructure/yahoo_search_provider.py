"""Yahoo HTML 搜索适配器，获取公开企业官网候选。"""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from urllib.parse import quote_plus, unquote, urlsplit
from urllib.request import Request, urlopen

from src.application.search_queries import build_search_queries_for_round
from src.domain.lead import LeadRecord, canonical_website_domain
from src.domain.task import effective_candidate_limit
from src.infrastructure.google_search_provider import GoogleSearchProvider, SearchProviderError


class _YahooResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_result = False
        self._href = ""
        self._text: list[str] = []
        self.results: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag != "a" or self._in_result:
            return
        attributes = dict(attrs)
        classes = set(attributes.get("class", "").split())
        if "d-ib" in classes and "va-top" in classes:
            self._in_result = True
            self._href = attributes.get("href", "")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._in_result:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result:
            title = " ".join("".join(self._text).split())
            # Yahoo prefixes result titles with breadcrumb text. Keep the
            # actual page title so identity matching does not learn navigation
            # labels as the company name.
            title = title.split("›")[-1].strip()
            if title and self._href:
                self.results.append((self._href, title))
            self._in_result = False
            self._href = ""
            self._text = []


class YahooSearchProvider:
    def __init__(
        self,
        opener: Callable[..., object] = urlopen,
        timeout: float = 15.0,
        max_results_per_query: int = 10,
        host: str = "search.yahoo.com",
    ) -> None:
        if timeout <= 0 or max_results_per_query <= 0:
            raise ValueError("Yahoo search timeout and page size must be positive")
        if not host.strip() or "/" in host:
            raise ValueError("Yahoo search host must be a hostname")
        self._opener = opener
        self._timeout = timeout
        self._max_results = max_results_per_query
        self._host = host.strip()

    def search(self, criteria) -> list[LeadRecord]:
        return self.search_round(criteria, 0)

    def search_round(self, criteria, round_index: int = 0) -> list[LeadRecord]:
        """Search a rotated query pass for cumulative discovery.

        Later passes add a different buyer-intent word, so repeated searches
        do not simply replay Yahoo's first-page results.
        """
        candidate_limit = effective_candidate_limit(criteria)
        records: list[LeadRecord] = []
        seen_domains: set[str] = set()
        queries = build_search_queries_for_round(criteria, round_index)
        intent_suffixes = ("", "contact", "supplier", "manufacturer", "factory", "distributor")
        suffix = intent_suffixes[round_index % len(intent_suffixes)]
        if suffix:
            queries = tuple(f"{query} {suffix}" for query in queries)
        # Yahoo occasionally stalls or returns 500 for one combination. A
        # small bounded pool prevents that one query from serially delaying
        # every other country/industry combination.
        with ThreadPoolExecutor(max_workers=min(6, len(queries) or 1)) as executor:
            query_results = executor.map(self._fetch_query, queries)
            for query, results in zip(queries, query_results):
              url = f"https://{self._host}/search?p={quote_plus(query)}&nojs=1"
              for href, title in results[: self._max_results]:
                resolved = self._resolve_result_url(href)
                domain = canonical_website_domain(resolved)
                if (
                    not GoogleSearchProvider._is_candidate(resolved, title)
                    or not GoogleSearchProvider._has_country_signal(
                        criteria, f"{title} {resolved}"
                    )
                    or not self._is_query_relevant(title, resolved)
                    or not domain
                    or domain in seen_domains
                ):
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
                if len(records) >= candidate_limit:
                    return records
        if not records:
            raise SearchProviderError("Yahoo search returned no public website results")
        return records

    def _fetch_query(self, query: str) -> list[tuple[str, str]]:
        url = f"https://{self._host}/search?p={quote_plus(query)}&nojs=1"
        request = Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ClientResearch/1.0)"},
        )
        try:
            response = self._opener(request, timeout=self._timeout)
            html = response.read().decode("utf-8", errors="replace")
        except Exception:
            return []
        parser = _YahooResultParser()
        parser.feed(unescape(html))
        return parser.results

    @staticmethod
    def _resolve_result_url(href: str) -> str:
        parsed = urlsplit(href)
        if parsed.hostname != "r.search.yahoo.com":
            return href
        marker = "/RU="
        if marker not in parsed.path:
            return ""
        encoded = parsed.path.split(marker, 1)[1].split("/", 1)[0]
        return unquote(encoded)

    @staticmethod
    def _is_query_relevant(title: str, url: str) -> bool:
        text = f"{title} {url}".lower()
        return not any(
            marker in text
            for marker in (
                "intramuscular",
                "nursing",
                "healthencyclopedia",
                "encyclopedia",
                "symptom",
                "dictionary",
                "meaning of",
            "how to",
            "hotel",
            "resort",
            "lodges",
            "travel",
            "adventure",
            "calculator",
            "percentage",
            "percent",
            "festival",
            "synchrony account",
        )
        )
