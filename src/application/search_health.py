"""确定性地把搜索失败转换为可展示的健康状态。"""

from __future__ import annotations


def classify_search_error(error: str) -> dict[str, object]:
    """Return a stable user message while preserving the raw error separately."""
    message = str(error).strip()
    lowered = message.lower()
    if any(
        marker in lowered
        for marker in ("consent", "captcha", "unusual-traffic", "javascript-only")
    ):
        return {
            "category": "access_restricted",
            "user_message": "搜索来源暂时受限，请稍后重试。",
            "retryable": True,
        }
    if "no public website results" in lowered:
        return {
            "category": "no_verified_results",
            "user_message": "当前条件暂未找到可验证的公司官网，可调整条件后重试。",
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
