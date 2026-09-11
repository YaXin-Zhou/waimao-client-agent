import json

from src.domain.task import AcquisitionCriteria
from src.infrastructure.brave_api_search_provider import BraveApiSearchProvider


class Response:
    def read(self):
        return json.dumps(
            {
                "web": {
                    "results": [
                        {
                            "title": "German Automotive Injection Molding",
                            "url": "https://manufacturer.de/injection-molding",
                            "description": "Automotive plastic components manufacturer in Germany.",
                        },
                        {
                            "title": "Singapore injection molding directory",
                            "url": "https://directory.sg/top-10-molders",
                            "description": "Directory",
                        },
                    ]
                }
            }
        ).encode()


def test_brave_api_provider_uses_key_and_country_and_filters_result_noise():
    captured = []

    def opener(request, timeout):
        captured.append(request)
        return Response()

    provider = BraveApiSearchProvider("secret", opener=opener)
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
    assert captured[0].get_header("X-subscription-token") == "secret"
    assert "country=DE" in captured[0].full_url
