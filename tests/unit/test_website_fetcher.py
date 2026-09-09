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


def test_fetcher_extracts_public_mailto_and_visible_emails_with_context():
    fetcher = WebsiteFetcher(
        opener=lambda url, timeout: (
            b"<main>Contact us at sales@alpine.example. "
            b"<a href='mailto:info@alpine.example'>Email sales</a> "
            b"<a href='mailto:info@alpine.example'>Duplicate</a> "
            b"<span>noreply@example.com</span></main>"
        )
    )

    document = fetcher.fetch("https://alpine.example/contact")

    assert [item.address for item in document.public_emails] == [
        "sales@alpine.example",
        "info@alpine.example",
    ]
    assert all(
        item.source_url == "https://alpine.example/contact" for item in document.public_emails
    )
    assert all("@alpine.example" in item.excerpt for item in document.public_emails)


def test_fetcher_follows_bounded_same_domain_contact_pages():
    pages = {
        "https://alpine.example/": (
            b"<a href='/about'>About</a><a href='/contact'>Contact</a>"
            b"<a href='https://outside.example/contact'>Outside</a>"
        ),
        "https://alpine.example/about": b"<title>About</title>Company overview",
        "https://alpine.example/contact": b"Contact sales@alpine.example",
    }

    fetcher = WebsiteFetcher(opener=lambda url, timeout: pages[url])

    documents = fetcher.fetch_contact_pages("https://alpine.example/", max_pages=3)

    assert [document.url for document in documents] == [
        "https://alpine.example/",
        "https://alpine.example/about",
        "https://alpine.example/contact",
    ]
    assert documents[-1].public_emails[0].address == "sales@alpine.example"


def test_fetcher_can_follow_bounded_relevant_external_sources_when_enabled():
    pages = {
        "https://alpine.example/": b"<a href='https://group.example/contact'>Group contact</a>",
        "https://group.example/contact": b"Group sales@group.example",
    }

    fetcher = WebsiteFetcher(opener=lambda url, timeout: pages[url])

    documents = fetcher.fetch_contact_pages(
        "https://alpine.example/",
        max_pages=3,
        allow_external_sources=True,
        max_external_pages=1,
    )

    assert [document.url for document in documents] == [
        "https://alpine.example/",
        "https://group.example/contact",
    ]
