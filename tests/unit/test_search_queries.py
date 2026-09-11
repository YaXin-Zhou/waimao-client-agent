from src.application.search_queries import build_search_queries, build_search_queries_for_round
from src.domain.task import AcquisitionCriteria


def test_build_search_queries_uses_user_configured_business_conditions():
    criteria = AcquisitionCriteria(
        product="portable solar generator",
        countries=("Germany", "France"),
        industries=("outdoor equipment",),
        customer_types=("distributor", "wholesaler"),
        keywords=("portable power station", "solar generator supplier"),
    )

    queries = build_search_queries(criteria)

    assert queries[:12] == (
        "portable solar generator outdoor equipment distributor Germany",
        "portable solar generator outdoor equipment wholesaler Germany",
        "portable solar generator outdoor equipment distributor France",
        "portable solar generator outdoor equipment wholesaler France",
        "portable power station outdoor equipment distributor Germany",
        "portable power station outdoor equipment wholesaler Germany",
        "portable power station outdoor equipment distributor France",
        "portable power station outdoor equipment wholesaler France",
        "solar generator supplier outdoor equipment distributor Germany",
        "solar generator supplier outdoor equipment wholesaler Germany",
        "solar generator supplier outdoor equipment distributor France",
        "solar generator supplier outdoor equipment wholesaler France",
    )
    assert "portable solar generator Germany" in queries


def test_build_search_queries_can_use_business_offering_terms_without_fixed_product():
    from src.domain.custom_research import BusinessOffering

    criteria = AcquisitionCriteria(
        countries=("Mexico",),
        business_offerings=(
            BusinessOffering(
                name="CNC machining",
                key="cnc_machining",
                keywords=("precision machining",),
            ),
        ),
    )

    queries = build_search_queries(criteria)
    assert queries[:2] == ("CNC machining Mexico", "precision machining Mexico")
    assert "CNC machining" in queries


def test_build_search_queries_has_a_product_only_fallback():
    assert build_search_queries(AcquisitionCriteria(product="solar lamp")) == ("solar lamp",)


def test_build_search_queries_translates_chinese_input_without_changing_the_criteria(monkeypatch):
    import json
    from src.application import search_queries

    class Response:
        def read(self):
            return json.dumps([[['injection molded parts', '']]]).encode('utf-8')

    search_queries._TRANSLATION_CACHE.clear()
    monkeypatch.setattr(search_queries, 'urlopen', lambda *_args, **_kwargs: Response())

    queries = build_search_queries(
        AcquisitionCriteria(product='注塑件', countries=('德国',), industries=('汽车',))
    )

    assert queries[:3] == (
        'injection molded parts injection molded parts injection molded parts',
        'injection molded parts injection molded parts',
        'injection molded parts',
    )


def test_country_slash_input_is_treated_as_multiple_countries():
    criteria = AcquisitionCriteria(
        product="注塑件",
        countries=("法国/美国",),
        industries=("汽车",),
    )

    assert criteria.countries == ("法国", "美国")


def test_build_search_queries_bounds_large_condition_combinations():
    criteria = AcquisitionCriteria(
        product="plastic parts",
        keywords=tuple(f"keyword-{index}" for index in range(6)),
        countries=tuple(f"country-{index}" for index in range(4)),
        industries=("automotive", "electronics"),
        customer_types=("manufacturer", "distributor"),
    )

    queries = build_search_queries(criteria)

    assert len(queries) == 24
    assert queries[0].startswith("plastic parts automotive manufacturer country-0")


def test_search_query_rounds_rotate_a_small_non_repeating_slice():
    criteria = AcquisitionCriteria(
        product="plastic parts",
        countries=("Germany", "France", "Italy"),
        industries=("automotive", "electronics"),
        customer_types=("manufacturer", "distributor"),
    )

    first = build_search_queries_for_round(criteria, 0, max_queries=4)
    second = build_search_queries_for_round(criteria, 1, max_queries=4)

    assert len(first) == len(second) == 4
    assert set(first).isdisjoint(second)


def test_search_query_rounds_never_drops_user_country_constraint():
    criteria = AcquisitionCriteria(
        product="plastic injection molding",
        countries=("Germany",),
    )

    queries = build_search_queries_for_round(criteria, 0, max_queries=20)

    assert queries
    assert all("germany" in query.casefold() for query in queries)
