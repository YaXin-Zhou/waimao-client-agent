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
    assert not PlaywrightSearchProvider._is_blocked(
        "https://www.google.com/search", "Search results. Please enable JavaScript."
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


def test_browser_provider_continues_when_results_appear_with_stale_challenge_text():
    class Body:
        def inner_text(self):
            return "Search results. Detected unusual traffic"

    class Results:
        def count(self):
            return 3

    class Page:
        url = "https://www.google.com/search"

        def locator(self, selector):
            return Results() if selector == "#search h3, #rso h3, a h3" else Body()

        def wait_for_timeout(self, _milliseconds):
            raise AssertionError("verification should finish without waiting")

    provider = PlaywrightSearchProvider(challenge_timeout=1)
    provider._wait_for_user_verification(Page())


def test_browser_provider_opens_challenge_in_a_visible_front_window():
    class Chromium:
        def __init__(self):
            self.options = None

        def launch(self, **options):
            self.options = options
            return object()

    class Playwright:
        def __init__(self):
            self.chromium = Chromium()

    playwright = Playwright()
    provider = PlaywrightSearchProvider()
    provider._launch_browser(playwright, headless=False)

    assert playwright.chromium.options["headless"] is False
    assert "--new-window" in playwright.chromium.options["args"]
    assert "--start-maximized" in playwright.chromium.options["args"]
    assert "--no-startup-window" in playwright.chromium.options["ignore_default_args"]
