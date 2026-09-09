from src.domain.task import AcquisitionCriteria
from src.infrastructure.browser_search_provider import BrowserSearchProvider, BrowserSearchResult


def test_browser_provider_normalizes_visible_results_and_deduplicates_urls():
    calls = []

    def search_page(query, limit):
        calls.append((query, limit))
        return [
            BrowserSearchResult(
                " Solar-Generatoren.de ",
                " https://solar-generatoren.de/ ",
                "Solar equipment supplier in Germany",
            ),
            BrowserSearchResult("duplicate", "https://solar-generatoren.de/"),
            BrowserSearchResult("North Supply", "https://north.example/"),
        ]

    provider = BrowserSearchProvider(search_page)
    results = provider.search(
        AcquisitionCriteria(
            product="portable solar generator",
            daily_limit=2,
            qualified_lead_limit=2,
            candidate_limit=2,
        )
    )

    assert len(results) == 2
    assert results[0].company_name == "Solar-Generatoren.de"
    assert results[0].email == ""
    assert results[0].source_url == "https://solar-generatoren.de/"
    assert calls[0][1] == 2


def test_browser_provider_deduplicates_different_pages_from_one_domain():
    provider = BrowserSearchProvider(
        lambda query, limit: [
            BrowserSearchResult("About", "https://alpine.example/about"),
            BrowserSearchResult("Products", "https://www.alpine.example/products"),
            BrowserSearchResult("North", "https://north.example/"),
        ]
    )

    results = provider.search(
        AcquisitionCriteria(
            product="solar generator",
            daily_limit=2,
            qualified_lead_limit=2,
            candidate_limit=2,
        )
    )

    assert [item.website for item in results] == [
        "https://alpine.example/about",
        "https://north.example/",
    ]


def test_browser_provider_uses_all_configured_queries_until_limit():
    calls = []

    def search_page(query, limit):
        calls.append(query)
        return [BrowserSearchResult(query, f"https://{len(calls)}.example/")]

    provider = BrowserSearchProvider(search_page)
    results = provider.search(
        AcquisitionCriteria(
            product="solar generator",
            keywords=("solar generator", "portable power station"),
            daily_limit=2,
            qualified_lead_limit=2,
            candidate_limit=2,
        )
    )

    assert len(results) == 2
    assert calls == ["solar generator", "portable power station"]
