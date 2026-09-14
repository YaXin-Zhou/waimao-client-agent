import json

from src.domain.task import AcquisitionCriteria
from src.infrastructure.tavily_search_provider import TavilySearchProvider


class Response:
    def read(self):
        return json.dumps(
            {
                "results": [
                    {
                        "title": "French Plastics Manufacturer",
                        "url": "https://manufacturer.fr/products",
                        "content": "Injection molded plastic parts for automotive suppliers.",
                    },
                    {
                        "title": "Industry Directory",
                        "url": "https://directory.example.com/plastics",
                        "content": "Directory listing",
                    },
                ]
            }
        ).encode()


def test_tavily_provider_posts_bounded_query_and_parses_public_sites():
    captured = []

    def opener(request, timeout):
        captured.append((request, timeout))
        return Response()

    provider = TavilySearchProvider("tvly-secret", opener=opener)
    results = provider.search(
        AcquisitionCriteria(
            product="injection molding",
            countries=("France",),
            candidate_limit=1,
            qualified_lead_limit=1,
        )
    )

    assert [item.website for item in results] == [
        "https://manufacturer.fr/products"
    ]
    request, timeout = captured[0]
    body = json.loads(request.data.decode())
    assert body["search_depth"] == "basic"
    assert body["include_answer"] is False
    assert body["include_raw_content"] is False
    assert "France" in body["query"]
    assert request.get_header("Authorization") == "Bearer tvly-secret"
    assert timeout == 20.0


def test_tavily_provider_rejects_market_reports_and_manufacturer_lists():
    assert not TavilySearchProvider._is_company_result(
        "Germany Plastic Injection Molding Machine Market Size",
        "Growth analysis report",
    )
    assert not TavilySearchProvider._is_company_result(
        "Top 10 injection molding manufacturers in Germany", ""
    )
    assert not TavilySearchProvider._is_company_result(
        "6 Applications of CNC Machining in the Automotive Industry", ""
    )
    assert not TavilySearchProvider._is_company_result(
        "Wholesale Car Part Mold Manufacturers, Suppliers", ""
    )
    assert not TavilySearchProvider._is_company_result(
        "Injection Molding Companies in Germany", "Complete sourcing guide"
    )
    assert not TavilySearchProvider._is_company_result(
        "Automotive Interior Plastics Injection Molded Plastic Parts",
        "Made-in-China.com product listing",
    )
    assert not TavilySearchProvider._is_company_result(
        "Injection Molded Automotive Parts Market Sizing", "Market overview"
    )
    assert TavilySearchProvider._is_company_result(
        "AKF plastics", "Injection moulding for automotive parts"
    )


def test_tavily_provider_keeps_company_pages_with_broad_business_terms():
    assert TavilySearchProvider._is_company_result(
        "Wholesale Plastics Ltd", "Injection molding services for automotive parts"
    )
    assert TavilySearchProvider._is_company_result(
        "Rosti Group", "Plastic injection molding and CNC machining services"
    )


def test_tavily_directory_helpers_keep_directory_pages_out_of_customer_pool():
    names = TavilySearchProvider._extract_directory_company_names(
        "TechniForm GmbH Deutschland; SCHLIESSMEYER GmbH; 77 Anbieter für Kunststoffspritzguss"
    )

    assert names == ("TechniForm GmbH", "SCHLIESSMEYER GmbH")
    assert TavilySearchProvider._directory_domain("https://www.wlw.de/de/suche/x") == "wlw.de"
    assert TavilySearchProvider._directory_domain("https://example.de/company") == "example.de"
    assert TavilySearchProvider._directory_domain("https://www.wlw.de/de/suche/x") in (
        "wlw.de", "europages.com", "europages.co.uk"
    )


def test_tavily_provider_accepts_configured_query_budget():
    provider = TavilySearchProvider(
        "secret", max_results_per_query=20, max_queries_per_round=8
    )
    assert provider._max_results == 20
    assert provider._max_queries == 8


def test_tavily_provider_excludes_domains_already_in_local_database():
    provider = TavilySearchProvider("secret")
    provider.remember_domains(["manufacturer.fr"])
    assert "manufacturer.fr" in provider._excluded_domains


def test_tavily_provider_uses_optional_model_expansion_without_changing_country():
    captured = []

    def opener(request, timeout):
        query = json.loads(request.data.decode())["query"]
        captured.append(query)
        if "plastic components" not in query:
            return type("EmptyResponse", (), {"read": lambda self: b'{"results": []}'})()
        return Response()

    class Expander:
        def expand(self, criteria):
            return ("plastic components",)

    provider = TavilySearchProvider(
        "secret",
        opener=opener,
        max_queries_per_round=24,
        keyword_expander=Expander(),
    )
    provider.search(
        AcquisitionCriteria(
            product="injection molding",
            countries=("France",),
            candidate_limit=1,
            qualified_lead_limit=1,
        )
    )

    assert any("plastic components" in query for query in captured)
    assert all("France" in query for query in captured)


def test_tavily_provider_reports_reused_query_pool_after_first_round():
    empty = type("EmptyResponse", (), {"read": lambda self: b'{"results": []}'})
    provider = TavilySearchProvider("secret", opener=lambda request, timeout: empty())

    try:
        provider.search_round(
            AcquisitionCriteria(
                product="plastic parts",
                countries=("France",),
                candidate_limit=1,
                qualified_lead_limit=1,
            ),
            round_index=1,
        )
    except Exception as error:
        assert "query pool exhausted" in str(error)
    else:
        raise AssertionError("expected query-pool exhaustion")
