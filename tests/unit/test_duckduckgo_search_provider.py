from src.domain.task import AcquisitionCriteria
from src.infrastructure.duckduckgo_search_provider import DuckDuckGoSearchProvider


class Response:
    def __init__(self, html):
        self.html = html.encode()

    def read(self):
        return self.html


def test_duckduckgo_provider_resolves_redirect_and_filters_directories():
    html = """
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdirectory.example%2Ftop-10">Top 10 Plastic Companies</a>
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fplastic-company.example%2F">Plastic Company</a>
    """
    provider = DuckDuckGoSearchProvider(opener=lambda request, timeout: Response(html))
    results = provider.search(AcquisitionCriteria(product="plastic", candidate_limit=1, qualified_lead_limit=1))
    assert [item.website for item in results] == ["https://plastic-company.example/"]
