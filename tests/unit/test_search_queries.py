from src.application.search_queries import build_search_queries
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

    assert queries == (
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

    assert build_search_queries(criteria) == (
        "CNC machining Mexico",
        "precision machining Mexico",
    )


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

    assert queries == ('injection molded parts injection molded parts injection molded parts',)


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
