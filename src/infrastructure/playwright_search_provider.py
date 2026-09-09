"""无界面浏览器搜索适配器。

该适配器只使用浏览器加载并读取公开可见结果，不点击广告、不绕过验证码，
也不从域名猜测邮箱。遇到 Consent、验证码或异常流量页面时明确失败。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlsplit

from src.application.search_queries import build_search_queries
from src.domain.lead import LeadRecord
from src.domain.task import AcquisitionCriteria
from src.infrastructure.google_search_provider import GoogleSearchProvider, SearchProviderError


class PlaywrightSearchProvider:
    """通过本机 Chrome 的无界面页面读取 Google 可见结果。"""

    def __init__(
        self,
        host: str = "www.google.com.hk",
        timeout: float = 30.0,
        max_results_per_query: int = 10,
        executable_path: str = "",
        headless: bool = True,
        proxy: str = "",
    ) -> None:
        if not host.strip() or "/" in host:
            raise ValueError("Google search host must be a hostname")
        if timeout <= 0 or max_results_per_query <= 0:
            raise ValueError("browser search timeout and page size must be positive")
        self._host = host.strip()
        self._timeout_ms = int(timeout * 1000)
        self._max_results = max_results_per_query
        self._executable_path = executable_path.strip() or self._find_chrome()
        self._headless = headless
        self._proxy = proxy.strip()

    def search(self, criteria: AcquisitionCriteria) -> list[LeadRecord]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise SearchProviderError("Playwright is not installed for browser fallback") from error

        candidate_limit = criteria.candidate_limit or criteria.daily_limit
        records: list[LeadRecord] = []
        seen_urls: set[str] = set()
        with sync_playwright() as playwright:
            launch_options: dict[str, Any] = {"headless": self._headless}
            if self._executable_path:
                launch_options["executable_path"] = self._executable_path
            if self._proxy:
                launch_options["proxy"] = {"server": self._proxy}
            try:
                browser = playwright.chromium.launch(**launch_options)
            except Exception as error:
                raise SearchProviderError("Unable to launch the configured browser") from error
            try:
                page = browser.new_page()
                for query in build_search_queries(criteria):
                    for page_start in range(0, candidate_limit, self._max_results):
                        url = (
                            f"https://{self._host}/search?q={quote_plus(query)}"
                            f"&num={self._max_results}&start={page_start}"
                        )
                        try:
                            page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                            page.wait_for_timeout(350)
                            if self._is_blocked(page.url, page.locator("body").inner_text()):
                                raise SearchProviderError(
                                    "Google browser search stopped at Consent/captcha/"
                                    "unusual-traffic page"
                                )
                            rows = page.locator("a").evaluate_all(
                                """els => els.map(a => ({
                                    href: a.href || '',
                                    text: (a.innerText || a.textContent || '').trim(),
                                    excerpt: (a.parentElement?.innerText || '').trim()
                                })).filter(item => item.href && item.text)"""
                            )
                        except SearchProviderError:
                            raise
                        except Exception as error:
                            raise SearchProviderError("Browser Google search failed") from error
                        added_on_page = 0
                        for row in rows:
                            result_url = self._resolve_result_url(page, row.get("href", ""))
                            if not GoogleSearchProvider._is_candidate(result_url):
                                continue
                            if result_url in seen_urls:
                                continue
                            seen_urls.add(result_url)
                            records.append(
                                LeadRecord(
                                    company_name=str(row.get("text", "")).strip(),
                                    website=result_url,
                                    source_url=url,
                                    source_excerpt=str(row.get("excerpt", "")).strip(),
                                )
                            )
                            added_on_page += 1
                            if len(records) >= candidate_limit:
                                return records
                        if added_on_page == 0:
                            break
                if not records:
                    raise SearchProviderError(
                        "Browser Google search returned no public website results"
                    )
                return records
            finally:
                browser.close()

    @staticmethod
    def _is_blocked(current_url: str, body_text: str) -> bool:
        lowered = f"{current_url} {body_text}".lower()
        markers = (
            "/sorry/",
            "consent.google",
            "before you continue",
            "unusual traffic",
            "detected unusual traffic",
            "enable javascript",
        )
        return any(marker in lowered for marker in markers)

    @staticmethod
    def _find_chrome() -> str:
        candidates = (
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        )
        return next((str(path) for path in candidates if path.exists()), "")

    @staticmethod
    def _resolve_result_url(page, href: str) -> str:
        """Resolve Google redirect links with a request, never by clicking them."""
        parsed = urlsplit(href)
        if parsed.hostname and (
            parsed.hostname.endswith("google.com")
            or parsed.hostname.endswith("google.com.hk")
        ):
            try:
                response = page.request.get(href, timeout=10_000, max_redirects=5)
                return response.url
            except Exception:
                return ""
        return href
