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
