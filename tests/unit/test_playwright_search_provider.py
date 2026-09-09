from src.infrastructure.playwright_search_provider import PlaywrightSearchProvider


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
