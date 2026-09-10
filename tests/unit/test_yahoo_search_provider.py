from src.domain.task import AcquisitionCriteria
from src.infrastructure.yahoo_search_provider import YahooSearchProvider


class Response:
    def __init__(self, html):
        self.html = html.encode()

    def read(self):
        return self.html


def test_yahoo_provider_parses_redirected_company_results():
    html = """
    <a class="d-ib va-top mt-38 mb-4 mxw-100p"
       href="https://r.search.yahoo.com/_/RU=https%3A%2F%2Fsupplier.example%2F/RK=1">
      Supplier <b>Injection Molding</b>
    </a>
    """
    provider = YahooSearchProvider(opener=lambda request, timeout: Response(html))
    results = provider.search(
        AcquisitionCriteria(product="injection molding", candidate_limit=1, qualified_lead_limit=1)
    )

    assert len(results) == 1
    assert results[0].website == "https://supplier.example/"
    assert "Injection Molding" in results[0].company_name


def test_yahoo_provider_filters_clear_health_noise():
    html = """
    <a class="d-ib va-top mt-38 mb-4 mxw-100p"
       href="https://r.search.yahoo.com/_/RU=https%3A%2F%2Fhealthencyclopedia.org%2Finjection/RK=1">
      Intramuscular Injection Guide
    </a>
    """
    provider = YahooSearchProvider(opener=lambda request, timeout: Response(html))

    try:
        provider.search(
            AcquisitionCriteria(product="injection molding", candidate_limit=1, qualified_lead_limit=1)
        )
    except RuntimeError as error:
        assert "no public website results" in str(error)
    else:
        raise AssertionError("health content must not be treated as a company candidate")


def test_yahoo_provider_filters_generic_travel_noise():
    html = """
    <a class="d-ib va-top mt-38 mb-4 mxw-100p"
       href="https://r.search.yahoo.com/_/RU=https%3A%2F%2Fhotel.example%2F/RK=1">
      Hatta Resorts Hotel
    </a>
    """
    provider = YahooSearchProvider(opener=lambda request, timeout: Response(html))
    try:
        provider.search(
            AcquisitionCriteria(product="CNC machining", candidate_limit=1, qualified_lead_limit=1)
        )
    except RuntimeError as error:
        assert "no public website results" in str(error)
    else:
        raise AssertionError("travel content must not be treated as a company candidate")
