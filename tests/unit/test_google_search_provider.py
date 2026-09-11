import pytest

from src.domain.task import AcquisitionCriteria
from src.infrastructure.google_search_provider import GoogleSearchProvider, SearchProviderError


class FakeResponse:
    def __init__(self, html):
        self.html = html

    def read(self):
        return self.html.encode()


def test_google_provider_extracts_public_urls_deduplicates_and_never_guesses_email():
    html = """
    <a href="/url?q=https://www.alpine.example/about"><h3>Alpine Energy</h3></a>
    <a href="https://www.alpine.example/about">Alpine duplicate</a>
    <a href="https://www.google.com/preferences">Google preferences</a>
    <a href="https://north.example/">North Supply</a>
    """

    provider = GoogleSearchProvider(
        opener=lambda request, timeout: FakeResponse(html), max_results_per_query=5
    )
    results = provider.search(AcquisitionCriteria(product="portable power station", daily_limit=5))

    assert [item.domain if hasattr(item, "domain") else item.website for item in results] == [
        "https://www.alpine.example/about",
        "https://north.example/",
    ]
    assert results[0].email == ""
    assert results[0].source_excerpt == "Alpine Energy"
    assert "google.com.hk/search" in results[0].source_url


def test_google_provider_deduplicates_multiple_pages_from_one_domain():
    html = (
        '<a href="https://alpine.example/about">About</a>'
        '<a href="https://alpine.example/products">Products</a>'
        '<a href="https://north.example/">North Supply</a>'
    )
    provider = GoogleSearchProvider(
        opener=lambda request, timeout: FakeResponse(html), max_results_per_query=5
    )

    results = provider.search(AcquisitionCriteria(product="portable power station", daily_limit=2))

    assert [item.website for item in results] == [
        "https://alpine.example/about",
        "https://north.example/",
    ]


def test_google_provider_continues_after_a_page_with_only_filtered_results():
    pages = {
        0: '<a href="https://www.linkedin.com/company/example">Directory</a>',
        5: '<a href="https://real-manufacturer.example/"><h3>Real Manufacturer</h3></a>',
    }

    def open_search(request, timeout):
        start = int(request.full_url.split("start=")[-1])
        return FakeResponse(pages.get(start, ""))

    provider = GoogleSearchProvider(opener=open_search, max_results_per_query=5)
    results = provider.search(
        AcquisitionCriteria(
            product="portable power station",
            daily_limit=1,
            qualified_lead_limit=1,
            candidate_limit=10,
        )
    )

    assert [item.website for item in results] == [
        "https://real-manufacturer.example/"
    ]


def test_google_provider_uses_default_candidate_pool_of_at_least_100():
    html = "".join(
        f'<a href="https://example-{index}.com"><h3>Example {index}</h3></a>' for index in range(4)
    )
    provider = GoogleSearchProvider(opener=lambda request, timeout: FakeResponse(html))

    results = provider.search(AcquisitionCriteria(product="solar generator", daily_limit=2))

    assert len(results) == 4


def test_google_provider_uses_daily_limit_when_it_exceeds_default_pool():
    html = "".join(
        f'<a href="https://large-{index}.com"><h3>Large {index}</h3></a>'
        for index in range(120)
    )
    provider = GoogleSearchProvider(opener=lambda request, timeout: FakeResponse(html))

    results = provider.search(
        AcquisitionCriteria(product="solar generator", daily_limit=120, qualified_lead_limit=1)
    )

    assert len(results) == 120


def test_google_provider_honors_explicit_candidate_limit():
    html = "".join(
        f'<a href="https://example-{index}.com"><h3>Example {index}</h3></a>' for index in range(4)
    )
    provider = GoogleSearchProvider(opener=lambda request, timeout: FakeResponse(html))

    results = provider.search(
        AcquisitionCriteria(
            product="solar generator",
            daily_limit=2,
            qualified_lead_limit=2,
            candidate_limit=2,
        )
    )

    assert len(results) == 2


def test_google_provider_excludes_job_boards_and_company_directories():
    assert not GoogleSearchProvider._is_candidate("https://www.indeed.com/viewjob?id=1")
    assert not GoogleSearchProvider._is_candidate("https://www.linkedin.com/company/example")
    assert not GoogleSearchProvider._is_candidate("https://www.zoominfo.com/c/example")
    assert GoogleSearchProvider._is_candidate("https://www.example-manufacturer.com/contact")


def test_google_provider_excludes_software_and_generic_industry_sites():
    assert not GoogleSearchProvider._is_candidate("https://portableapps.com/", "PortableApps")
    assert not GoogleSearchProvider._is_candidate("https://portapps.io/", "Portapps")
    assert not GoogleSearchProvider._is_candidate("https://sourceforge.net/projects/tool/", "Tool")
    assert not GoogleSearchProvider._is_candidate("https://themanufacturer.com/articles/injection-molding", "The Manufacturer")
    assert not GoogleSearchProvider._is_candidate("https://manufacturer.com/", "Manufacturer.com")


def test_google_provider_excludes_school_marketplace_and_research_titles():
    assert not GoogleSearchProvider._is_candidate("https://bsd405.org/", "Bellevue School District")
    assert not GoogleSearchProvider._is_candidate("https://tradeford.com/buyers", "Injection Mold Buyers List")
    assert not GoogleSearchProvider._is_candidate("https://nasdaq.com/", "Nasdaq - Listings, Market Data & Financial Technology")
    assert GoogleSearchProvider._is_candidate("https://real-mold-maker.example/", "Real Mold Maker")


def test_google_provider_excludes_informational_paths_and_public_institutions():
    assert not GoogleSearchProvider._is_candidate(
        "https://www.example.com/resources/plastic-guide"
    )
    assert not GoogleSearchProvider._is_candidate("https://www.epa.gov/plastics")
    assert not GoogleSearchProvider._is_candidate(
        "https://www.investopedia.com/terms/o/oem.asp"
    )
    assert not GoogleSearchProvider._is_candidate(
        "https://scienceinsights.org/how-is-plastic-recycled"
    )
    assert not GoogleSearchProvider._is_candidate("https://ourworldindata.org/plastic-pollution")
    assert not GoogleSearchProvider._is_candidate(
        "https://www-langer--group-eu.translate.goog/Injection-molding-series-production"
    )
    assert not GoogleSearchProvider._is_candidate(
        "https://example.com/collections/what-is-elastomers"
    )
    assert GoogleSearchProvider._is_candidate(
        "https://www.example-manufacturer.com/products/plastic-parts"
    )
    assert not GoogleSearchProvider._is_candidate(
        "https://www.example.com/plastic", "What is plastic injection molding?"
    )


def test_google_provider_surfaces_network_errors():
    def fail(request, timeout):
        raise TimeoutError("proxy timeout")

    provider = GoogleSearchProvider(opener=fail)

    with pytest.raises(SearchProviderError, match="Google search failed"):
        provider.search(AcquisitionCriteria(product="solar generator"))


def test_google_provider_does_not_treat_javascript_page_as_empty_results():
    provider = GoogleSearchProvider(
        opener=lambda request, timeout: FakeResponse(
            '<a href="/httpservice/retry/enablejs">click here</a>'
        )
    )

    with pytest.raises(SearchProviderError, match="JavaScript-only"):
        provider.search(AcquisitionCriteria(product="solar generator"))


def test_google_provider_uses_configured_regional_host_and_filters_google_links():
    captured = []

    def open_search(request, timeout):
        captured.append(request.full_url)
        return FakeResponse(
            '<a href="https://www.google.com.hk/preferences">Google</a>'
            '<a href="/url?q=https://real.example/">Real company</a>'
        )

    provider = GoogleSearchProvider(opener=open_search, host="www.google.com.hk")
    results = provider.search(AcquisitionCriteria(product="solar generator", daily_limit=1))

    assert captured[0].startswith("https://www.google.com.hk/search?")
    assert [item.website for item in results] == ["https://real.example/"]


def test_google_provider_rotates_buyer_intent_on_later_rounds():
    captured = []

    def open_search(request, timeout):
        captured.append(request.full_url)
        return FakeResponse('<a href="https://real.example/">Real company</a>')

    provider = GoogleSearchProvider(opener=open_search)
    provider.search_round(AcquisitionCriteria(product="solar generator", daily_limit=1), 2)
    assert "supplier" in captured[0]
