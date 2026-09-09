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
      <li class="b_algo"><h2><a href="https://supplier.example/">Supplier</a></h2></li>
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
    assert "Bing result for" in results[0].source_excerpt
    assert calls[0][0].startswith("https://www.bing.com/search?")


def test_bing_provider_resolves_encoded_redirect_without_clicking():
    token = "a1" + base64.urlsafe_b64encode(b"https://supplier.example/").decode()

    assert BingSearchProvider._resolve_result_url(
        f"https://www.bing.com/ck/a?u={token}"
    ) == "https://supplier.example/"
