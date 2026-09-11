import pytest

from src.domain.lead import LeadRecord
from src.domain.task import AcquisitionCriteria
from src.infrastructure.fallback_search_provider import FallbackSearchProvider
from src.infrastructure.google_search_provider import SearchProviderError


class Primary:
    def __init__(self, result=None):
        self.result = result

    def search(self, criteria):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class Fallback:
    def __init__(self, result=None):
        self.result = result
        self.called = False

    def search(self, criteria):
        self.called = True
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class CountingFailure:
    def __init__(self):
        self.calls = 0

    def search(self, criteria):
        self.calls += 1
        raise SearchProviderError("temporary block")


def test_fallback_is_not_used_when_static_search_succeeds():
    fallback = Fallback(["static"])

    result = FallbackSearchProvider(Primary(["primary"]), fallback).search(object())

    assert result == ["primary"]
    assert fallback.called is False


def test_fallback_runs_only_after_explicit_static_provider_error():
    fallback = Fallback(["browser"])

    result = FallbackSearchProvider(
        Primary(SearchProviderError("consent")), fallback
    ).search(object())

    assert result == ["browser"]
    assert fallback.called is True


def test_fallback_preserves_a_clear_error_when_both_providers_fail():
    with pytest.raises(SearchProviderError, match="all configured search providers failed"):
        FallbackSearchProvider(
            Primary(SearchProviderError("static")),
            Fallback(SearchProviderError("captcha")),
        ).search(object())


def test_fallback_supplements_short_primary_results_until_candidate_limit():
    fallback = Fallback(
        [LeadRecord("Second", "https://second.example"), LeadRecord("Third", "third.example")]
    )
    criteria = AcquisitionCriteria(
        product="portable power station", candidate_limit=3, qualified_lead_limit=1
    )

    result = FallbackSearchProvider(
        Primary([LeadRecord("First", "https://first.example")]), fallback
    ).search(criteria)

    assert [item.website for item in result] == [
        "https://first.example",
        "https://second.example",
        "third.example",
    ]
    assert fallback.called


def test_fallback_can_stop_after_first_successful_provider():
    fallback = Fallback(["second"])

    result = FallbackSearchProvider(
        Primary(["first"]), fallback, stop_after_first_success=True
    ).search(object())

    assert result == ["first"]
    assert fallback.called is False


def test_fallback_deduplicates_same_domain_across_sources():
    fallback = Fallback([LeadRecord("Duplicate", "https://www.first.example/about")])
    criteria = AcquisitionCriteria(
        product="portable power station", candidate_limit=2, qualified_lead_limit=1
    )

    result = FallbackSearchProvider(
        Primary([LeadRecord("First", "https://first.example")]), fallback
    ).search(criteria)

    assert len(result) == 1


def test_fallback_cools_down_failed_sources_between_retries():
    primary = CountingFailure()
    fallback = CountingFailure()
    provider = FallbackSearchProvider(
        primary, fallback, failure_cooldown_seconds=60
    )

    with pytest.raises(SearchProviderError, match="all configured search providers failed"):
        provider.search(object())
    with pytest.raises(SearchProviderError, match="cooling down"):
        provider.search(object())

    assert primary.calls == 1
    assert fallback.calls == 1
