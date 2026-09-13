"""把用户配置的获客条件转换为确定性的搜索词。"""

from __future__ import annotations

import json
from itertools import product
from urllib.parse import quote
from urllib.request import urlopen

from src.domain.task import AcquisitionCriteria, configured_research_terms


_TRANSLATION_CACHE: dict[str, str] = {}

# Keep common manufacturing terms precise. Generic machine translation turns
# "注塑件" into "mold", which produces unrelated mold-removal results.
_DOMAIN_TRANSLATIONS = {
    "注塑件": "injection molded parts",
    "注塑": "injection molding",
    "塑料件": "plastic parts",
    "塑料零件": "plastic parts",
    "CNC机加工": "CNC machining",
    "模具": "molds tooling",
    "汽车": "automotive",
    "汽车零部件": "automotive parts",
    "德国": "Germany",
    "法国": "France",
    "英国": "United Kingdom",
    "美国": "United States",
    "意大利": "Italy",
}

_TERM_ALIASES = {
    "注塑件": ("injection molding", "plastic injection moulding", "plastic components"),
    "injection molded parts": ("injection molding", "plastic injection moulding", "plastic components"),
    "塑料件": ("injection molded parts", "plastic components", "thermoplastic parts"),
    "塑料零件": ("injection molded parts", "plastic components", "thermoplastic parts"),
    "注塑": ("injection molded parts", "plastic injection moulding"),
    "模具": ("tooling", "injection molds", "mould making"),
    "模具制造": ("tooling", "injection molds", "mould making"),
    "cnc机加工": ("CNC machining", "precision machining", "machined components"),
    "cnc machining": ("precision machining", "machined components"),
}


def _search_term(value: str) -> str:
    """将中文输入转换为英文搜索词，转换只发生在后端查询构建阶段。"""
    value = value.strip()
    if not value or not any("\u3400" <= char <= "\u9fff" for char in value):
        return value
    if value in _DOMAIN_TRANSLATIONS:
        return _DOMAIN_TRANSLATIONS[value]
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


def search_term_variants(value: str) -> tuple[str, ...]:
    """Return a small bounded synonym set for one user-entered term."""
    original = value.strip()
    translated = _search_term(original)
    aliases = _TERM_ALIASES.get(original.casefold(), ())
    return tuple(dict.fromkeys(item for item in (translated, *aliases) if item.strip()))


def build_search_queries(criteria: AcquisitionCriteria) -> tuple[str, ...]:
    terms = tuple(
        dict.fromkeys(
            variant
            for term in configured_research_terms(criteria)
            for variant in search_term_variants(term)
        )
    )
    industries = _translated(criteria.industries) or ("",)
    customer_types = _translated(criteria.customer_types) or ("",)
    countries = _translated(criteria.countries) or ("",)

    queries: list[str] = []
    for term, industry, country, customer_type in product(
        terms, industries, countries, customer_types
    ):
        query = " ".join(
            part.strip() for part in (term, industry, customer_type, country) if part.strip()
        )
        if query and query not in queries:
            queries.append(query)
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
    """Return a rotating bounded slice for the optional API fallback."""
    if max_queries <= 0:
        raise ValueError("max_queries must be positive")
    queries = build_search_queries(criteria)
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
