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


def test_google_provider_honors_daily_limit():
    html = "".join(
        f'<a href="https://example-{index}.com"><h3>Example {index}</h3></a>' for index in range(4)
    )
    provider = GoogleSearchProvider(opener=lambda request, timeout: FakeResponse(html))

    results = provider.search(AcquisitionCriteria(product="solar generator", daily_limit=2))

    assert len(results) == 2


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
