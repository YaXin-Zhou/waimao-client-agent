"""把用户配置的获客条件转换为确定性的搜索词。"""

from __future__ import annotations

from itertools import product

from src.domain.task import AcquisitionCriteria, configured_research_terms


def build_search_queries(criteria: AcquisitionCriteria) -> tuple[str, ...]:
    terms = configured_research_terms(criteria)
    industries = criteria.industries or ("",)
    customer_types = criteria.customer_types or ("",)
    countries = criteria.countries or ("",)

    queries: list[str] = []
    for term, industry, country, customer_type in product(
        terms, industries, countries, customer_types
    ):
        query = " ".join(
            part.strip() for part in (term, industry, customer_type, country) if part.strip()
        )
        if query and query not in queries:
            queries.append(query)
    return tuple(queries)
