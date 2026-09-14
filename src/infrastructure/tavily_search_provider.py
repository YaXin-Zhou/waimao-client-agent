"""Tavily Search API adapter for bounded public company discovery."""

from __future__ import annotations

import json
import re
import time
from dataclasses import replace
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from src.application.search_queries import build_search_queries_for_round
from src.domain.lead import LeadRecord, canonical_website_domain
from src.domain.task import AcquisitionCriteria, effective_candidate_limit
from src.infrastructure.google_search_provider import GoogleSearchProvider, SearchProviderError


class TavilySearchProvider:
    """Use Tavily's supported JSON API instead of scraping search HTML."""

    # Tavily is an API-backed source. Once it returns public-web candidates,
    # do not continue into HTML/browser fallbacks for the same round; doing so
    # can trigger search-engine challenges even though the configured source
    # already succeeded. Fallbacks remain available when Tavily errors or
    # returns no usable candidates.
    return_immediately_after_results = True
    _DIRECTORY_DOMAINS = frozenset({
        "wlw.de",
        "europages.com",
        "europages.co.uk",
    })

    def __init__(
        self,
        api_key: str,
        opener: Callable[..., object] = urlopen,
        timeout: float = 20.0,
        max_results_per_query: int = 10,
        max_queries_per_round: int = 8,
        endpoint: str = "https://api.tavily.com/search",
        keyword_expander=None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Tavily API key is required")
        if timeout <= 0 or not 1 <= max_results_per_query <= 20:
            raise ValueError("Tavily timeout and page size must be valid")
        if not 1 <= max_queries_per_round <= 24:
            raise ValueError("Tavily query count must be between 1 and 24")
        if not endpoint.startswith("https://"):
            raise ValueError("Tavily API endpoint must use HTTPS")
        self._api_key = api_key.strip()
        self._opener = opener
        self._timeout = timeout
        self._max_results = max_results_per_query
        self._max_queries = max_queries_per_round
        self._endpoint = endpoint
        self._keyword_expander = keyword_expander
        self._excluded_domains: set[str] = set()

    def remember_domains(self, domains: set[str] | list[str] | tuple[str, ...]) -> None:
        """Exclude domains already stored in the local customer database."""
        self._excluded_domains.update(
            str(domain).strip().casefold().removeprefix("www.")
            for domain in domains
            if str(domain).strip()
        )

    def search(self, criteria: AcquisitionCriteria) -> list[LeadRecord]:
        return self.search_round(criteria, 0)

    def search_round(
        self, criteria: AcquisitionCriteria, round_index: int = 0
    ) -> list[LeadRecord]:
        target = effective_candidate_limit(criteria)
        records: list[LeadRecord] = []
        seen: set[str] = set()
        search_criteria = criteria
        if self._keyword_expander is not None:
            expanded = self._keyword_expander.expand(criteria)
            if expanded:
                search_criteria = replace(
                    criteria,
                    keywords=tuple(dict.fromkeys((*criteria.keywords, *expanded))),
                )
        queries = build_search_queries_for_round(
            search_criteria, round_index, max_queries=self._max_queries
        )
        query_pool_reused = (
            round_index > 0
            and (
                len(build_search_queries_for_round(search_criteria, 0, max_queries=len(queries) or 1))
                <= self._max_queries
                or round_index
                >= (len(build_search_queries_for_round(search_criteria, 0, max_queries=self._max_queries)) + self._max_queries - 1)
                // self._max_queries
            )
        )
        for query in queries:
            payload = self._request(query)
            for result in payload.get("results", []):
                if not isinstance(result, dict):
                    continue
                url = str(result.get("url", "")).strip()
                title = str(result.get("title", "")).strip()
                content = str(result.get("content", "")).strip()
                domain = canonical_website_domain(url)
                if (
                    not domain
                    or not GoogleSearchProvider._is_candidate(url, title)
                    or not self._is_company_result(title, f"{content} {url}")
                    or domain.casefold() in self._excluded_domains
                    or domain in seen
                ):
                    continue
                seen.add(domain)
                self._excluded_domains.add(domain.casefold().removeprefix("www."))
                records.append(
                    LeadRecord(
                        company_name=title or domain,
                        website=url,
                        source_url=self._endpoint,
                        source_excerpt=content or title or domain,
                    )
                )
                if len(records) >= target:
                    return records[:target]
        # Directories are useful for enumeration but are not company websites.
        # Use a few directory entries only as names to seed a second, official-
        # website lookup. This adds recall without ever persisting a directory
        # page as a customer or treating its contact data as verified.
        if len(records) < target:
            records.extend(
                self._discover_official_sites_from_directories(
                    search_criteria,
                    records,
                    target,
                    round_index,
                )
            )
            if records:
                return records[:target]
        if not records:
            if query_pool_reused:
                raise SearchProviderError(
                    "Tavily query pool exhausted; no new public website results"
                )
            raise SearchProviderError("Tavily returned no public website results")
        return records

    def _discover_official_sites_from_directories(
        self,
        criteria: AcquisitionCriteria,
        existing: list[LeadRecord],
        target: int,
        round_index: int,
    ) -> list[LeadRecord]:
        """Turn a few directory names into official-site candidates.

        This is deliberately small and bounded: directory pages can be noisy,
        and the official-site lookup is an additional API call. The existing
        website fetcher and qualification gate remain responsible for public
        email and country verification.
        """
        countries = " ".join(value.strip() for value in criteria.countries if value.strip())
        terms = " ".join(value.strip() for value in criteria.keywords[:2] if value.strip())
        if not terms:
            terms = criteria.product.strip()
        directory_queries = (
            f"site:wlw.de {terms} {countries} supplier",
            f"site:europages.com {terms} {countries} manufacturer",
        )
        directory_query = directory_queries[round_index % len(directory_queries)]
        payload = self._request(directory_query)
        names: list[str] = []
        for result in payload.get("results", []):
            if not isinstance(result, dict):
                continue
            url = str(result.get("url", "")).strip()
            if self._directory_domain(url) not in self._DIRECTORY_DOMAINS:
                continue
            names.extend(self._extract_directory_company_names(
                f"{result.get('title', '')} {result.get('content', '')}"
            ))
        discovered: list[LeadRecord] = []
        seen = {canonical_website_domain(item.website) for item in existing}
        for name in dict.fromkeys(names):
            if len(discovered) + len(existing) >= target or len(discovered) >= 3:
                break
            lookup = f'"{name}" official website {countries} contact'
            lookup_payload = self._request(lookup)
            for result in lookup_payload.get("results", []):
                if not isinstance(result, dict):
                    continue
                url = str(result.get("url", "")).strip()
                title = str(result.get("title", "")).strip()
                content = str(result.get("content", "")).strip()
                domain = canonical_website_domain(url)
                if (
                    not domain
                    or domain in seen
                    or not GoogleSearchProvider._is_candidate(url, title)
                    or not self._is_company_result(title, f"{content} {url}")
                ):
                    continue
                seen.add(domain)
                self._excluded_domains.add(domain.casefold().removeprefix("www."))
                discovered.append(
                    LeadRecord(
                        company_name=title or name,
                        website=url,
                        source_url=self._endpoint,
                        source_excerpt=content or title or name,
                    )
                )
                break
        return discovered

    @classmethod
    def _directory_domain(cls, url: str) -> str:
        return (urlparse(url).hostname or "").lower().removeprefix("www.")

    @staticmethod
    def _extract_directory_company_names(text: str) -> tuple[str, ...]:
        """Extract only legal-name-shaped snippets from directory summaries."""
        pattern = re.compile(
            r"\b([A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9&'().,\-/ ]{2,80}?\s+"
            r"(?:GmbH(?:\s*&\s*Co\.\s*KG)?|AG|KG|UG|S\.?r\.?l\.?|"
            r"Ltd\.?|Inc\.?|LLC|SAS|S\.?A\.))\b"
        )
        return tuple(
            " ".join(match.split()).strip(" -|,;")
            for match in pattern.findall(text)
            if len(match.strip()) >= 4
        )

    def _request(self, query: str) -> dict:
        request = Request(
            self._endpoint,
            data=json.dumps(
                {
                    "query": query,
                    "search_depth": "basic",
                    "topic": "general",
                    "max_results": self._max_results,
                    "include_answer": False,
                    "include_raw_content": False,
                }
            ).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        for attempt in range(3):
            try:
                response = self._opener(request, timeout=self._timeout)
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
                break
            except HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise SearchProviderError(f"Tavily search failed for query: {query}") from error
                retry_after = error.headers.get("Retry-After", "5")
                try:
                    delay = min(max(float(retry_after), 1.0), 600.0)
                except (TypeError, ValueError):
                    delay = 5.0
                time.sleep(delay)
            except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
                if attempt == 2:
                    raise SearchProviderError(f"Tavily search failed for query: {query}") from error
                time.sleep(2.0 * (attempt + 1))
        if not isinstance(payload, dict):
            raise SearchProviderError("Tavily returned an invalid response")
        return payload

    @staticmethod
    def _is_company_result(title: str, content: str) -> bool:
        """Drop listicles, market reports, and other non-company landing pages."""
        text = f"{title} {content}".casefold()
        blocked_phrases = (
            "top 10",
            "top  twenty",
            "applications of",
            "how to",
            "complete guide",
            "sourcing guide",
            "industry outlook",
            "market outlook",
            "market forecast",
            "/horizon/",
            "for cars",
            "car mold cleaning",
            "mold cleaning for",
            "manufacturers, suppliers",
            "made in the usa",
            "etsy",
            "market size",
            "market sizing",
            "market report",
            "market analysis",
            "market share",
            "growth analysis",
            "industry report",
            "list of manufacturers",
            "manufacturers in",
            "directory listing",
            "company directory",
            "buyers list",
            "made-in-china",
            "towardsautomotive",
            "/report",
            "-report",
        )
        return not any(phrase in text for phrase in blocked_phrases)
