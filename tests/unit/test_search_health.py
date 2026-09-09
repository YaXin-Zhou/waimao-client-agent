from src.application.search_health import classify_search_error


def test_classifies_access_restriction_as_retryable_without_exposing_details():
    result = classify_search_error(
        "all providers failed: Google consent page; browser unusual-traffic page"
    )

    assert result == {
        "category": "access_restricted",
        "user_message": "搜索来源暂时受限，请稍后重试。",
        "retryable": True,
    }


def test_classifies_empty_provider_results_separately():
    assert classify_search_error("Bing search returned no public website results") == {
        "category": "no_verified_results",
        "user_message": "当前条件暂未找到可验证的公司官网，可调整条件后重试。",
        "retryable": True,
    }


def test_classifies_network_errors_as_retryable():
    result = classify_search_error("Google search failed: proxy timeout")

    assert result["category"] == "network_error"
    assert result["retryable"] is True
