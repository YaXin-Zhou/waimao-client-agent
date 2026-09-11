"""把用户配置的获客条件转换为确定性的搜索词。"""

from __future__ import annotations

import json
from itertools import product
from urllib.parse import quote
from urllib.request import urlopen

from src.domain.task import AcquisitionCriteria, configured_research_terms


_TRANSLATION_CACHE: dict[str, str] = {}


def _search_term(value: str) -> str:
    """将中文输入转换为英文搜索词，转换只发生在后端查询构建阶段。"""
    value = value.strip()
    if not value or not any("\u3400" <= char <= "\u9fff" for char in value):
        return value
    if value in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[value]
    try:
        endpoint = (
            "https://translate.googleapis.com/translate_a/single?client=gtx"
            f"&sl=auto&tl=en&dt=t&q={quote(value)}"
        )
        payload = json.loads(urlopen(endpoint, timeout=8).read().decode("utf-8"))
        translated = " ".join(
            str(part[0]) for part in payload[0] if part and part[0]
        )
        result = translated or value
    except Exception:
        result = value
    _TRANSLATION_CACHE[value] = result
    return result


def _translated(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_search_term(value) for value in values if value.strip()))


def build_search_queries(criteria: AcquisitionCriteria) -> tuple[str, ...]:
    terms = _translated(configured_research_terms(criteria))
    industries = _translated(criteria.industries) or ("",)
    customer_types = _translated(criteria.customer_types) or ("",)
    countries = _translated(criteria.countries) or ("",)

    queries: list[str] = []

    def add(*parts: str) -> None:
        query = " ".join(part.strip() for part in parts if part.strip())
        if query and query not in queries:
            queries.append(query)

    # Search in layers. The first layer keeps the strongest intent signal;
    # later layers widen discovery when a search engine ranks too few results
    # for an over-constrained query. Qualification still enforces the user's
    # configured country, industry, and public-email requirements afterwards.
    for term, industry, country, customer_type in product(
        terms, industries, countries, customer_types
    ):
        add(term, industry, customer_type, country)
    for term, industry, country in product(terms, industries, countries):
        add(term, industry, country)
    for term, country in product(terms, countries):
        add(term, country)
    for term, industry in product(terms, industries):
        add(term, industry)
    for term in terms:
        add(term)
    # Keep flexible user criteria, but bound the cartesian product so a browser
    # provider cannot spend minutes serially opening dozens of near-duplicate
    # result pages.  Small explicit test/task configurations remain unchanged.
    max_queries = 24
    return tuple(queries[:max_queries])


def build_search_queries_for_round(
    criteria: AcquisitionCriteria,
    round_index: int = 0,
    max_queries: int = 4,
) -> tuple[str, ...]:
    """Return a small rotating slice of configured queries for one run.

    Discovery is designed to accumulate throughout a day.  Running every
    country/industry combination against every public search engine in one
    click is both slow and likely to trigger rate limits, so later rounds pick
    up where earlier ones stopped.
    """
    if max_queries <= 0:
        raise ValueError("max_queries must be positive")
    queries = build_search_queries(criteria)
    # Country is a hard business constraint.  Do not silently fall back to a
    # product-only query when the user supplied countries; that is how generic
    # dictionaries, encyclopedias, and unrelated-country pages enter the pool.
    country_terms = _translated(criteria.countries)
    if country_terms:
        queries = tuple(
            query
            for query in queries
            if any(country.casefold() in query.casefold() for country in country_terms)
        )
    if len(queries) <= max_queries:
        return queries
    start = (max(0, round_index) * max_queries) % len(queries)
    return tuple(queries[(start + offset) % len(queries)] for offset in range(max_queries))
