from src.domain.task import AcquisitionCriteria
from src.infrastructure.brave_search_provider import BraveSearchProvider


class Response:
    def __init__(self, html):
        self.html = html.encode()

    def read(self):
        return self.html


def test_brave_provider_keeps_company_site_and_rejects_directory_and_wrong_country():
    html = """
    <a href="https://directory.example/top-10-molders">Top 10 molders</a>
    <a href="https://supplier.sg/injection-molding">Singapore molder</a>
    <a href="https://manufacturer.de/injection-molding">German Injection Molding</a>
    """
    provider = BraveSearchProvider(opener=lambda request, timeout: Response(html))
    results = provider.search(
        AcquisitionCriteria(
            product="injection molding",
            countries=("Germany",),
            candidate_limit=1,
            qualified_lead_limit=1,
        )
    )
    assert [item.website for item in results] == [
        "https://manufacturer.de/injection-molding"
    ]
