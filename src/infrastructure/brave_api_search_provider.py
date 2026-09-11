"""Official Brave Search API adapter for reliable public website discovery."""

from __future__ import annotations

import json
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.application.search_queries import build_search_queries_for_round
from src.domain.lead import LeadRecord, canonical_website_domain
from src.domain.task import AcquisitionCriteria, effective_candidate_limit
from src.infrastructure.google_search_provider import GoogleSearchProvider, SearchProviderError


_COUNTRY_CODES = {
    "china": "CN",
    "中国": "CN",
    "germany": "DE",
    "德国": "DE",
    "france": "FR",
    "法国": "FR",
    "italy": "IT",
    "意大利": "IT",
    "united states": "US",
    "usa": "US",
    "美国": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "英国": "GB",
}


class BraveApiSearchProvider:
    """Use Brave's supported JSON endpoint instead of scraping result HTML."""

    def __init__(
        self,
        api_key: str,
        opener: Callable[..., object] = urlopen,
        timeout: float = 15.0,
        max_results_per_query: int = 20,
        endpoint: str = "https://api.search.brave.com/res/v1/web/search",
    ) -> None:
        if not api_key.strip():
            raise ValueError("Brave Search API key is required")
        if timeout <= 0 or not 1 <= max_results_per_query <= 20:
            raise ValueError("Brave API timeout and page size must be valid")
        if not endpoint.startswith("https://"):
            raise ValueError("Brave API endpoint must use HTTPS")
        self._api_key = api_key.strip()
        self._opener = opener
        self._timeout = timeout
        self._max_results = max_results_per_query
        self._endpoint = endpoint

    def search(self, criteria: AcquisitionCriteria) -> list[LeadRecord]:
        return self.search_round(criteria, 0)

    def search_round(
        self, criteria: AcquisitionCriteria, round_index: int = 0
    ) -> list[LeadRecord]:
        target = effective_candidate_limit(criteria)
        suffixes = ("", "manufacturer", "supplier", "company", "contact", "purchasing")
        suffix = suffixes[round_index % len(suffixes)]
        country_code = self._single_country_code(criteria)
        records: list[LeadRecord] = []
        seen: set[str] = set()
        for base_query in build_search_queries_for_round(criteria, round_index):
            query = f"{base_query} {suffix}".strip()
            params = {"q": query, "count": self._max_results, "search_lang": "en"}
            if country_code:
                params["country"] = country_code
            request = Request(
                f"{self._endpoint}?{urlencode(params)}",
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self._api_key,
                },
            )
            try:
                payload = json.loads(
                    self._opener(request, timeout=self._timeout)
                    .read()
                    .decode("utf-8", errors="replace")
                )
            except Exception as error:
                raise SearchProviderError(
                    f"Brave Search API failed for query: {query}"
                ) from error
            for result in payload.get("web", {}).get("results", []):
                if not isinstance(result, dict):
                    continue
                url = str(result.get("url", "")).strip()
                title = str(result.get("title", "")).strip()
                description = str(result.get("description", "")).strip()
                domain = canonical_website_domain(url)
                if (
                    not GoogleSearchProvider._is_candidate(url, title)
                    or GoogleSearchProvider._has_obvious_country_mismatch(criteria, url)
                    or not self._is_query_relevant(query, title, url, description)
                    or not domain
                    or domain in seen
                ):
                    continue
                seen.add(domain)
                records.append(
                    LeadRecord(
                        company_name=title or domain,
                        website=url,
                        source_url=request.full_url,
                        source_excerpt=description or title or domain,
                    )
                )
                if len(records) >= target:
                    return records
        if not records:
            raise SearchProviderError("Brave Search API returned no public website results")
        return records

    @staticmethod
    def _single_country_code(criteria: AcquisitionCriteria) -> str:
        countries = tuple(str(country).strip().casefold() for country in criteria.countries if str(country).strip())
        return _COUNTRY_CODES.get(countries[0], "") if len(countries) == 1 else ""

    @staticmethod
    def _is_query_relevant(query: str, title: str, url: str, description: str) -> bool:
        text = f"{title} {url} {description}".lower()
        blocked = (
            "directory", "top 10", "top 100", "list of", "wiki", "recipe",
            "charity", "foundation", "wwf", "forum", "linkedin.com",
        )
        if any(marker in text for marker in blocked):
            return False
        terms = {term for term in query.lower().split() if len(term) >= 4}
        return not terms or any(term in text for term in terms)
