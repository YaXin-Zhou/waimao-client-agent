from src.domain.task import AcquisitionCriteria
from src.infrastructure.brave_search_provider import BraveSearchProvider
from src.infrastructure.duckduckgo_search_provider import DuckDuckGoSearchProvider
from src.infrastructure.mojeek_search_provider import MojeekSearchProvider


class Response:
    def __init__(self, html: str):
        self._body = html.encode()

    def read(self):
        return self._body


def criteria():
    return AcquisitionCriteria(product="injection molding", candidate_limit=1,
                               qualified_lead_limit=1)


def test_brave_html_provider_extracts_a_public_company_url():
    provider = BraveSearchProvider(
        opener=lambda request, timeout: Response(
            '<a href="https://supplier.example/">Injection Molding Supplier</a>'
        )
    )
    result = provider.search(criteria())
    assert result[0].website == "https://supplier.example/"


def test_duckduckgo_provider_resolves_redirect_and_extracts_result():
    provider = DuckDuckGoSearchProvider(
        opener=lambda request, timeout: Response(
            '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fsupplier.example%2F">'
            "Injection Molding Supplier</a>"
        )
    )
    result = provider.search(criteria())
    assert result[0].website == "https://supplier.example/"


def test_mojeek_provider_extracts_result_from_result_container():
    provider = MojeekSearchProvider(
        opener=lambda request, timeout: Response(
            '<li class="results-standard"><a href="https://supplier.example/">'
            "Injection Molding Supplier</a></li>"
        )
    )
    result = provider.search(criteria())
    assert result[0].website == "https://supplier.example/"
