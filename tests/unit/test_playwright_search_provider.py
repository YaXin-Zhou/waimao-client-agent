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


def test_browser_provider_enables_bounded_user_handoff_by_default():
    provider = PlaywrightSearchProvider()

    assert provider._headless is True
    assert provider._headful_on_challenge is True
    assert provider._challenge_timeout_ms == 180_000


def test_browser_provider_continues_after_visible_verification_clears():
    class Body:
        def __init__(self):
            self.reads = 0

        def inner_text(self):
            self.reads += 1
            return "Before you continue" if self.reads == 1 else "Search results"

    class Page:
        url = "https://www.google.com/search"

        def __init__(self):
            self.body = Body()

        def locator(self, selector):
            return self.body

        def wait_for_timeout(self, _milliseconds):
            return None

    provider = PlaywrightSearchProvider(challenge_timeout=1)
    provider._wait_for_user_verification(Page())
