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
        "portable power station outdoor equipment distributor Germany",
        "portable power station outdoor equipment wholesaler Germany",
        "portable power station outdoor equipment distributor France",
        "portable power station outdoor equipment wholesaler France",
        "solar generator supplier outdoor equipment distributor Germany",
        "solar generator supplier outdoor equipment wholesaler Germany",
        "solar generator supplier outdoor equipment distributor France",
        "solar generator supplier outdoor equipment wholesaler France",
    )


def test_build_search_queries_has_a_product_only_fallback():
    assert build_search_queries(AcquisitionCriteria(product="solar lamp")) == ("solar lamp",)
