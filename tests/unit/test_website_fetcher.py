from src.infrastructure.website_fetcher import WebsiteFetcher


def test_fetcher_extracts_readable_text_and_keeps_source_metadata():
    def fake_open(url, timeout):
        assert url == "https://alpine.example/about"
        assert timeout == 15
        return (
            b"<html><head><title>About</title></head><body>"
            b"<h1>Alpine</h1><p>Outdoor distributor.</p>"
            b"<script>ignore()</script></body></html>"
        )

    document = WebsiteFetcher(opener=fake_open).fetch("https://alpine.example/about")

    assert document.url == "https://alpine.example/about"
    assert document.title == "About"
    assert "Alpine" in document.text
    assert "Outdoor distributor." in document.text
    assert "ignore" not in document.text


def test_fetcher_rejects_non_http_urls():
    fetcher = WebsiteFetcher(opener=lambda url, timeout: b"")

    try:
        fetcher.fetch("file:///secret.txt")
    except ValueError as error:
        assert str(error) == "Only HTTP(S) URLs are supported"
    else:
        raise AssertionError("expected invalid URL to be rejected")
