import pytest

from src.domain.lead import LeadRecord
from src.domain.task import AcquisitionCriteria
from src.infrastructure.fallback_search_provider import FallbackSearchProvider
from src.infrastructure.google_search_provider import SearchChallengeError, SearchProviderError


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


class VisibleBrowser:
    return_immediately_after_results = True

    def __init__(self, result):
        self.result = result

    def search(self, criteria):
        return self.result


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


def test_fallback_does_not_switch_sources_after_search_challenge():
    fallback = Fallback(["should not run"])

    with pytest.raises(SearchChallengeError, match="captcha"):
        FallbackSearchProvider(
            Primary(SearchChallengeError("captcha requires user verification")), fallback
        ).search(object())

    assert fallback.called is False


def test_fallback_stops_when_search_round_exceeds_time_limit():
    fallback = Fallback(["should not run"])
    clock_values = iter((0, 10))

    with pytest.raises(SearchProviderError, match="time limit"):
        FallbackSearchProvider(
            Primary(SearchProviderError("temporary provider failure")),
            fallback,
            max_duration_seconds=5,
            clock=lambda: next(clock_values),
        ).search(object())

    assert fallback.called is False


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


def test_fallback_returns_visible_browser_results_without_opening_more_sources():
    next_source = Fallback(["should not run"])
    result = FallbackSearchProvider(
        VisibleBrowser([LeadRecord("Visible", "https://visible.example")]),
        next_source,
    ).search(
        AcquisitionCriteria(
            product="portable power station",
            candidate_limit=30,
            qualified_lead_limit=1,
        )
    )

    assert [item.website for item in result] == ["https://visible.example"]
    assert next_source.called is False


def test_fallback_deduplicates_same_domain_across_sources():
    fallback = Fallback([LeadRecord("Duplicate", "https://www.first.example/about")])
    criteria = AcquisitionCriteria(
        product="portable power station", candidate_limit=2, qualified_lead_limit=1
    )

    result = FallbackSearchProvider(
        Primary([LeadRecord("First", "https://first.example")]), fallback
    ).search(criteria)

    assert len(result) == 1


def test_fallback_waits_between_search_sources_when_low_frequency_is_enabled():
    waits = []
    result = FallbackSearchProvider(
        Primary(SearchProviderError("blocked")),
        Fallback(SearchProviderError("blocked")),
        Fallback(["third"]),
        provider_interval_seconds=15,
        sleep=waits.append,
    ).search(object())

    assert result == ["third"]
    assert waits == [15, 15]
