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


def test_fetcher_includes_public_site_name_metadata_in_identity_title():
    fetcher = WebsiteFetcher(
        opener=lambda url, timeout: (
            b"<html><head><title>Home</title>"
            b"<meta property='og:site_name' content='Alpine Outdoor'></head>"
            b"<body>Company profile</body></html>"
        )
    )

    document = fetcher.fetch("https://alpine.example/")

    assert document.title == "Home - Alpine Outdoor"


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


def test_fetcher_removes_trailing_markup_punctuation_from_mailto_values():
    html = '<a href="mailto:support@alpine.example\\">support@alpine.example</a>'

    document = WebsiteFetcher(opener=lambda _url, _timeout: html.encode()).fetch(
        "https://alpine.example/contact"
    )

    assert [item.address for item in document.public_emails] == ["support@alpine.example"]


def test_fetcher_keeps_public_json_ld_descriptive_fields_as_evidence():
    html = (
        '<script type="application/ld+json">'
        '{"@type":"WebSite","name":"Alpine Energy",'
        '"description":"Portable power station supplier",'
        '"keywords":["solar generator"]}'
        '</script>'
    )

    document = WebsiteFetcher(opener=lambda _url, _timeout: html.encode()).fetch(
        "https://alpine.example"
    )

    assert "Alpine Energy" in document.text
    assert "Portable power station supplier" in document.text
    assert "solar generator" in document.text


def test_fetcher_normalizes_obfuscated_public_emails_and_keeps_context():
    fetcher = WebsiteFetcher(
        opener=lambda url, timeout: (
            b"<main>For sales use sales [at] alpine [dot] example. "
            b"For support use support(at)alpine(dot)example.</main>"
        )
    )

    document = fetcher.fetch("https://alpine.example/contact")

    assert [item.address for item in document.public_emails] == [
        "sales@alpine.example",
        "support@alpine.example",
    ]
    assert "sales [at] alpine [dot] example" in document.public_emails[0].excerpt


def test_fetcher_ignores_asset_filenames_and_placeholder_addresses():
    fetcher = WebsiteFetcher(
        opener=lambda url, timeout: (
            b"<img src='hero@2x.png'><span>name@domain.com</span>"
            b"<span>contoso@example.com</span>"
            b"<a href='mailto:support@alpine.example'>Support</a>"
        )
    )

    document = fetcher.fetch("https://alpine.example/")

    assert [item.address for item in document.public_emails] == [
        "support@alpine.example"
    ]


def test_fetcher_deduplicates_mailto_and_visible_email_forms():
    fetcher = WebsiteFetcher(
        opener=lambda url, timeout: (
            b"<a href='mailto:contact@alpine.example'>contact@alpine.example</a>"
        )
    )

    document = fetcher.fetch("https://alpine.example/")

    assert [item.address for item in document.public_emails] == [
        "contact@alpine.example"
    ]


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
        "https://alpine.example/contact",
        "https://alpine.example/about",
    ]
    assert documents[1].public_emails[0].address == "sales@alpine.example"


def test_fetcher_can_follow_bounded_relevant_external_sources_when_enabled():
    pages = {
        "https://alpine.example/": (
            b"<title>Alpine Outdoor</title>"
            b"<a href='https://group.example/contact'>Alpine group contact</a>"
        ),
        "https://group.example/contact": b"<title>Alpine Group</title>Alpine sales@group.example",
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


def test_fetcher_fills_same_domain_budget_before_following_external_sources():
    pages = {
        "https://alpine.example/": (
            b"<title>Alpine Outdoor</title>"
            b"<a href='/products'>Products</a>"
            b"<a href='https://group.example/contact'>Alpine group contact</a>"
        ),
        "https://alpine.example/products": b"Alpine portable power station products",
        "https://group.example/contact": b"Alpine Group sales@group.example",
    }

    fetcher = WebsiteFetcher(opener=lambda url, timeout: pages[url])

    documents = fetcher.fetch_contact_pages(
        "https://alpine.example/",
        max_pages=2,
        allow_external_sources=True,
        max_external_pages=1,
    )

    assert [document.url for document in documents] == [
        "https://alpine.example/",
        "https://alpine.example/products",
    ]


def test_fetcher_rejects_explicit_external_link_without_identity_match():
    pages = {
        "https://alpine.example/": (
            b"<title>Alpine Outdoor</title>"
            b"<a href='https://unrelated.example/contact'>Contact</a>"
        ),
        "https://unrelated.example/contact": (
            b"<title>Unrelated Group</title>sales@unrelated.example"
        ),
    }

    fetcher = WebsiteFetcher(opener=lambda url, timeout: pages[url])

    documents = fetcher.fetch_contact_pages(
        "https://alpine.example/", max_pages=3, allow_external_sources=True, max_external_pages=1
    )

    assert [document.url for document in documents] == ["https://alpine.example/"]


def test_fetch_contact_pages_skips_current_page_link_without_stopping_crawl():
    pages = {
        "https://alpine.example/": (
            b"<a href='https://alpine.example/'>Home</a>"
            b"<a href='/products'>Products</a>"
        ),
        "https://alpine.example/products": b"Products",
    }

    documents = WebsiteFetcher(opener=lambda url, timeout: pages[url]).fetch_contact_pages(
        "https://alpine.example/", max_pages=2
    )

    assert [document.url for document in documents] == [
        "https://alpine.example/",
        "https://alpine.example/products",
    ]


def test_fetch_contact_pages_treats_www_variant_as_same_domain():
    pages = {
        "https://alpine.example/": b"<a href='https://www.alpine.example/products'>Products</a>",
        "https://www.alpine.example/products": b"Products",
    }

    documents = WebsiteFetcher(opener=lambda url, timeout: pages[url]).fetch_contact_pages(
        "https://alpine.example/", max_pages=2
    )

    assert [document.url for document in documents] == [
        "https://alpine.example/",
        "https://www.alpine.example/products",
    ]


def test_fetch_contact_pages_deduplicates_tracking_variants_of_one_page():
    pages = {
        "https://alpine.example/": (
            b"<a href='/contact?utm_source=nav'>Contact</a>"
            b"<a href='/contact?ref=footer'>Contact again</a>"
            b"<a href='/products'>Products</a>"
        ),
        "https://alpine.example/contact?utm_source=nav": b"Contact sales@alpine.example",
        "https://alpine.example/products": b"Portable power station",
    }
    fetched = []

    def opener(url, _timeout):
        fetched.append(url)
        return pages[url].encode() if isinstance(pages[url], str) else pages[url]

    documents = WebsiteFetcher(opener=opener).fetch_contact_pages(
        "https://alpine.example/", max_pages=3
    )

    assert [document.url for document in documents] == [
        "https://alpine.example/",
        "https://alpine.example/contact?utm_source=nav",
        "https://alpine.example/products",
    ]
    assert fetched.count("https://alpine.example/contact?utm_source=nav") == 1


def test_fetch_contact_pages_prioritizes_product_evidence_links():
    pages = {
        "https://alpine.example/": (
            b"<a href='/about'>About</a><a href='/products'>Products</a>"
        ),
        "https://alpine.example/about": b"Company",
        "https://alpine.example/products": b"Portable power stations",
    }

    documents = WebsiteFetcher(opener=lambda url, timeout: pages[url]).fetch_contact_pages(
        "https://alpine.example/", max_pages=2
    )

    assert [document.url for document in documents] == [
        "https://alpine.example/",
        "https://alpine.example/products",
    ]


def test_fetch_contact_pages_keeps_contact_pages_in_a_product_heavy_site():
    pages = {
        "https://alpine.example/": (
            b"<a href='/products/one'>Product one</a>"
            b"<a href='/products/two'>Product two</a>"
            b"<a href='/products/three'>Product three</a>"
            b"<a href='/contact'>Contact</a>"
        ),
        "https://alpine.example/products/one": b"Portable power station one",
        "https://alpine.example/products/two": b"Portable power station two",
        "https://alpine.example/products/three": b"Portable power station three",
        "https://alpine.example/contact": b"sales@alpine.example",
    }

    documents = WebsiteFetcher(opener=lambda url, timeout: pages[url]).fetch_contact_pages(
        "https://alpine.example/", max_pages=3, priority_terms=("portable power station",)
    )

    assert [document.url for document in documents] == [
        "https://alpine.example/",
        "https://alpine.example/contact",
        "https://alpine.example/products/one",
    ]
    assert documents[1].public_emails[0].address == "sales@alpine.example"


def test_fetch_contact_pages_uses_same_domain_sitemap_when_navigation_is_empty():
    pages = {
        "https://alpine.example/": b"<html><body>JavaScript navigation</body></html>",
        "https://alpine.example/sitemap.xml": (
            b"<urlset><url><loc>https://alpine.example/about</loc></url>"
            b"<url><loc>https://alpine.example/portable-power-stations</loc></url></urlset>"
        ),
        "https://alpine.example/about": b"Company",
        "https://alpine.example/portable-power-stations": b"Portable power stations",
    }

    documents = WebsiteFetcher(opener=lambda url, timeout: pages[url]).fetch_contact_pages(
        "https://alpine.example/", max_pages=2, priority_terms=("portable power station",)
    )

    assert [document.url for document in documents] == [
        "https://alpine.example/",
        "https://alpine.example/portable-power-stations",
    ]


def test_fetch_contact_pages_reads_bounded_sitemap_indexes():
    pages = {
        "https://alpine.example/": b"<html><body>JavaScript navigation</body></html>",
        "https://alpine.example/sitemap.xml": b"<sitemapindex></sitemapindex>",
        "https://alpine.example/sitemap_index.xml": (
            b"<sitemapindex><loc>https://alpine.example/products.xml</loc></sitemapindex>"
        ),
        "https://alpine.example/products.xml": (
            b"<urlset><loc>https://alpine.example/contact</loc></urlset>"
        ),
        "https://alpine.example/contact": b"Contact sales@alpine.example",
    }

    documents = WebsiteFetcher(opener=lambda url, timeout: pages[url]).fetch_contact_pages(
        "https://alpine.example/", max_pages=2
    )

    assert [document.url for document in documents] == [
        "https://alpine.example/",
        "https://alpine.example/contact",
    ]
    assert documents[1].public_emails[0].address == "sales@alpine.example"


def test_fetch_contact_pages_probes_bounded_conventional_paths_for_script_navigation():
    pages = {
        "https://alpine.example/": b"<script>renderNavigation()</script>",
        "https://alpine.example/contact": b"Contact sales@alpine.example",
        "https://alpine.example/contact-us": b"Contact us",
        "https://alpine.example/imprint": b"Legal information",
        "https://alpine.example/impressum": b"Impressum",
        "https://alpine.example/about": b"Company overview",
        "https://alpine.example/company": b"Company",
        "https://alpine.example/products": b"Portable power stations",
    }

    documents = WebsiteFetcher(opener=lambda url, timeout: pages[url]).fetch_contact_pages(
        "https://alpine.example/", max_pages=2
    )

    assert [document.url for document in documents] == [
        "https://alpine.example/",
        "https://alpine.example/contact",
    ]
    assert documents[1].public_emails[0].address == "sales@alpine.example"
