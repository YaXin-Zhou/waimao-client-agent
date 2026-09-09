import pytest

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
    with pytest.raises(SearchProviderError, match="browser fallback failed"):
        FallbackSearchProvider(
            Primary(SearchProviderError("static")),
            Fallback(SearchProviderError("captcha")),
        ).search(object())
