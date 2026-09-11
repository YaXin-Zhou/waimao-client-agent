import base64

from src.domain.task import AcquisitionCriteria
from src.infrastructure.bing_search_provider import BingSearchProvider


class Response:
    def __init__(self, html):
        self.html = html.encode()

    def read(self):
        return self.html


def test_bing_provider_parses_public_result_links_and_keeps_source():
    html = """
    <ol>
      <li class="b_algo"><h2><a href="https://supplier.example/">Portable Power Station Supplier</a></h2></li>
      <li class="b_algo"><h2><a href="https://www.bing.com/images">Bing image</a></h2></li>
    </ol>
    """
    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, timeout))
        return Response(html)

    provider = BingSearchProvider(opener=opener)
    results = provider.search(
        AcquisitionCriteria(
            product="portable power station", candidate_limit=1, qualified_lead_limit=1
        )
    )

    assert len(results) == 1
    assert results[0].website == "https://supplier.example/"
    assert results[0].source_excerpt == "Portable Power Station Supplier"
    assert calls[0][0].startswith("https://www.bing.com/search?")


def test_bing_provider_resolves_encoded_redirect_without_clicking():
    token = "a1" + base64.urlsafe_b64encode(b"https://supplier.example/").decode()

    assert BingSearchProvider._resolve_result_url(
        f"https://www.bing.com/ck/a?u={token}"
    ) == "https://supplier.example/"


def test_bing_provider_excludes_non_company_result_hosts():
    html = """
    <ol>
      <li class="b_algo"><h2><a href="https://en.wikipedia.org/wiki/Injection_molding">Wikipedia</a></h2></li>
      <li class="b_algo"><h2><a href="https://real-company.example/">Portable Power Station Manufacturer</a></h2></li>
    </ol>
    """

    provider = BingSearchProvider(opener=lambda request, timeout: Response(html))
    results = provider.search(
        AcquisitionCriteria(
            product="portable power station", candidate_limit=1, qualified_lead_limit=1
        )
    )

    assert [result.website for result in results] == ["https://real-company.example/"]


def test_bing_provider_deduplicates_company_pages_by_normalized_domain():
    html = """
    <ol>
      <li class="b_algo"><h2><a href="https://supplier.example/">Portable Power Station Supplier home</a></h2></li>
      <li class="b_algo"><h2><a href="https://supplier.example/contact">
        Portable Power Station Supplier contact</a></h2></li>
      <li class="b_algo"><h2><a href="https://another.example/">Another Portable Power Station company</a></h2></li>
    </ol>
    """

    provider = BingSearchProvider(opener=lambda request, timeout: Response(html))
    results = provider.search(
        AcquisitionCriteria(
            product="portable power station", candidate_limit=2, qualified_lead_limit=2
        )
    )

    assert [result.website for result in results] == [
        "https://supplier.example/",
        "https://another.example/",
    ]


def test_bing_provider_excludes_dictionary_information_pages():
    html = """
    <ol>
      <li class="b_algo"><h2><a href="https://dictionary.cambridge.org/dictionary/english/contract">
        CONTRACT | English meaning</a></h2></li>
      <li class="b_algo"><h2><a href="https://real-company.example/">Contract Manufacturing Company</a></h2></li>
    </ol>
    """

    provider = BingSearchProvider(opener=lambda request, timeout: Response(html))
    results = provider.search(
        AcquisitionCriteria(
            product="contract manufacturing", candidate_limit=1, qualified_lead_limit=1
        )
    )

    assert [result.website for result in results] == ["https://real-company.example/"]


def test_bing_provider_excludes_unrelated_game_results():
    html = """
    <ol>
      <li class="b_algo"><h2><a href="https://www.roblox.com/">Roblox</a></h2></li>
      <li class="b_algo"><h2><a href="https://real-company.example/">Real Injection Molding manufacturer</a></h2></li>
    </ol>
    """
    provider = BingSearchProvider(opener=lambda request, timeout: Response(html))
    results = provider.search(
        AcquisitionCriteria(product="injection molding", candidate_limit=1, qualified_lead_limit=1)
    )
    assert [result.website for result in results] == ["https://real-company.example/"]


def test_bing_provider_excludes_nonprofit_content_with_product_word():
    html = """
    <ol>
      <li class="b_algo"><h2><a href="https://wwf.example/">WWF plastic campaign</a></h2></li>
      <li class="b_algo"><h2><a href="https://real-company.example/">Plastic Injection Molding Automotive Company</a></h2></li>
    </ol>
    """
    provider = BingSearchProvider(opener=lambda request, timeout: Response(html))
    results = provider.search(
        AcquisitionCriteria(product="plastic injection molding", candidate_limit=1, qualified_lead_limit=1)
    )
    assert [result.website for result in results] == ["https://real-company.example/"]


def test_bing_provider_keeps_brand_only_company_result_for_later_evidence_check():
    html = """
    <ol>
      <li class="b_algo"><h2><a href="https://plastic.example/">Plastic</a></h2></li>
      <li class="b_algo"><h2><a href="https://plastic-company.example/">Plastic Company</a></h2></li>
    </ol>
    """
    provider = BingSearchProvider(opener=lambda request, timeout: Response(html))
    results = provider.search(
        AcquisitionCriteria(product="plastic", candidate_limit=1, qualified_lead_limit=1)
    )
    assert [result.website for result in results] == ["https://plastic.example/"]


def test_bing_provider_excludes_generic_travel_and_calculation_results():
    html = """
    <ol>
      <li class="b_algo"><h2><a href="https://hotel.example/">Hatta Resorts Hotel</a></h2></li>
      <li class="b_algo"><h2><a href="https://calculator.example/">50 is what percent of 200?</a></h2></li>
      <li class="b_algo"><h2><a href="https://real-company.example/">CNC Machining Precision Components</a></h2></li>
    </ol>
    """
    provider = BingSearchProvider(opener=lambda request, timeout: Response(html))
    results = provider.search(
        AcquisitionCriteria(product="CNC machining", candidate_limit=1, qualified_lead_limit=1)
    )
    assert [result.website for result in results] == ["https://real-company.example/"]


def test_bing_provider_rejects_an_obvious_country_path_mismatch():
    html = """
    <ol>
      <li class="b_algo"><h2><a href="https://example.com/injection-molding-companies-singapore/">Singapore list</a></h2></li>
      <li class="b_algo"><h2><a href="https://example.de/injection-molding/">German company</a></h2></li>
    </ol>
    """
    provider = BingSearchProvider(opener=lambda request, timeout: Response(html))
    results = provider.search(
        AcquisitionCriteria(
            product="injection molding",
            countries=("Germany",),
            candidate_limit=1,
            qualified_lead_limit=1,
        )
    )
    assert [result.website for result in results] == ["https://example.de/injection-molding/"]
