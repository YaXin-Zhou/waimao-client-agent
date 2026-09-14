"""确定性地把搜索失败转换为可展示的健康状态。"""

from __future__ import annotations


def classify_search_error(error: str) -> dict[str, object]:
    """Return a stable user message while preserving the raw error separately."""
    message = str(error).strip()
    lowered = message.lower()
    # An aggregate fallback error may contain a search-engine challenge even
    # when the actionable result is simply that no new usable websites were
    # found. Prefer the clearer customer-facing message in that case.
    if "no public website results" in lowered:
        return {
            "category": "no_verified_results",
            "user_message": "本次没有找到新的合格客户，请换一组条件或稍后再试。",
            "retryable": True,
        }
    if any(
        marker in lowered
        for marker in ("consent", "captcha", "unusual-traffic", "javascript-only")
    ):
        return {
            "category": "access_restricted",
            "user_message": "搜索来源暂时受限，请稍后重试。",
            "retryable": True,
        }
    if any(marker in lowered for marker in ("timeout", "timed out", "network", "connection")):
        return {
            "category": "network_error",
            "user_message": "搜索网络暂时不稳定，请稍后重试。",
            "retryable": True,
        }
    return {
        "category": "search_error",
        "user_message": "搜索未完成，请稍后重试。",
        "retryable": True,
    }
