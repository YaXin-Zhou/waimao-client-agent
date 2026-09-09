from src.infrastructure.playwright_search_provider import PlaywrightSearchProvider


class _Response:
    url = "https://example.com/company"


class _Request:
    def get(self, href, **kwargs):
        return _Response()


class _Page:
    request = _Request()


def test_browser_provider_stops_on_consent_and_traffic_pages():
    assert PlaywrightSearchProvider._is_blocked(
        "https://www.google.com/sorry/index", ""
    )
    assert PlaywrightSearchProvider._is_blocked(
        "https://www.google.com/search", "Before you continue to Google"
    )
    assert not PlaywrightSearchProvider._is_blocked(
        "https://www.google.com/search", "Search results"
    )


def test_browser_provider_resolves_google_hk_redirect_without_clicking():
    page = _Page()
    resolved = PlaywrightSearchProvider._resolve_result_url(
        page, "https://www.google.com.hk/url?q=https%3A%2F%2Fexample.com%2Fcompany"
    )
    assert resolved == "https://example.com/company"
