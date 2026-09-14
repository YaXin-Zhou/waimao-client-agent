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
        "user_message": "本次没有找到新的合格客户，请换一组条件或稍后再试。",
        "retryable": True,
    }


def test_classifies_exhausted_query_pool_as_actionable_business_message():
    assert classify_search_error(
        "Tavily query pool exhausted; no new public website results"
    ) == {
        "category": "query_pool_exhausted",
        "user_message": "当前检索条件已基本覆盖，请调整关键词或国家后再试。",
        "retryable": True,
    }


def test_aggregate_empty_results_do_not_look_like_network_failure():
    assert classify_search_error(
        "all configured search providers failed: Tavily returned no public website results; "
        "Google returned a JavaScript-only or consent page"
    ) == {
        "category": "no_verified_results",
        "user_message": "本次没有找到新的合格客户，请换一组条件或稍后再试。",
        "retryable": True,
    }


def test_classifies_network_errors_as_retryable():
    result = classify_search_error("Google search failed: proxy timeout")

    assert result["category"] == "network_error"
    assert result["retryable"] is True
