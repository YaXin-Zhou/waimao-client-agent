"""无界面浏览器搜索适配器。

该适配器只使用浏览器加载并读取公开可见结果，不点击广告、不绕过验证码，
也不从域名猜测邮箱。遇到 Consent、验证码或异常流量页面时明确失败。
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import time
from typing import Any
from urllib.parse import quote_plus, urlsplit

from src.application.search_queries import build_search_queries
from src.domain.lead import LeadRecord, canonical_website_domain
from src.domain.task import AcquisitionCriteria, effective_candidate_limit
from src.infrastructure.google_search_provider import (
    GoogleSearchProvider,
    SearchChallengeError,
    SearchProviderError,
)


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
        headful_on_challenge: bool = True,
        challenge_timeout: float = 180.0,
    ) -> None:
        if not host.strip() or "/" in host:
            raise ValueError("Google search host must be a hostname")
        if timeout <= 0 or max_results_per_query <= 0:
            raise ValueError("browser search timeout and page size must be positive")
        if challenge_timeout <= 0:
            raise ValueError("challenge timeout must be positive")
        self._host = host.strip()
        self._timeout_ms = int(timeout * 1000)
        self._max_results = max_results_per_query
        self._executable_path = executable_path.strip() or self._find_chrome()
        self._headless = headless
        self._proxy = proxy.strip()
        self._headful_on_challenge = headful_on_challenge
        self._challenge_timeout_ms = int(challenge_timeout * 1000)

    def search(self, criteria: AcquisitionCriteria) -> list[LeadRecord]:
        return self.search_round(criteria, 0)

    def search_round(
        self, criteria: AcquisitionCriteria, round_index: int = 0
    ) -> list[LeadRecord]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise SearchProviderError("Playwright is not installed for browser fallback") from error

        candidate_limit = effective_candidate_limit(criteria)
        # Browser handoff is deliberately bounded to two result pages per
        # query. Users can run another low-frequency pass to accumulate more
        # leads; one click should not keep a visible browser busy for minutes.
        browser_candidate_limit = min(candidate_limit, self._max_results * 2)
        records: list[LeadRecord] = []
        seen_domains: set[str] = set()
        with sync_playwright() as playwright:
            try:
                browser = self._launch_browser(playwright, self._headless)
            except Exception as error:
                raise SearchProviderError("Unable to launch the configured browser") from error
            try:
                context = browser.new_context()
                page = context.new_page()
                self._activate_challenge_window(page)
                queries = build_search_queries(criteria)
                intent_suffixes = ("", "contact", "supplier", "manufacturer", "factory", "distributor", "purchasing", "procurement")
                suffix = intent_suffixes[round_index % len(intent_suffixes)]
                if suffix:
                    queries = tuple(f"{query} {suffix}" for query in queries)
                for query in queries:
                    for page_start in range(0, browser_candidate_limit, self._max_results):
                        url = (
                            f"https://{self._host}/search?q={quote_plus(query)}"
                            f"&num={self._max_results}&start={page_start}"
                        )
                        try:
                            page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                            page.wait_for_timeout(350)
                            if self._is_blocked(page.url, page.locator("body").inner_text()):
                                if not self._headful_on_challenge:
                                    raise SearchChallengeError(
                                        "Google browser search stopped at Consent/captcha/"
                                        "unusual-traffic page"
                                    )
                                # Preserve cookies/local storage when handing the
                                # challenge from the hidden browser to the visible
                                # browser.  Recreating a blank browser here makes a
                                # completed human verification invisible to the
                                # search session that follows.
                                storage_state = context.storage_state()
                                browser.close()
                                browser = self._launch_browser(playwright, headless=False)
                                context = browser.new_context(storage_state=storage_state)
                                page = context.new_page()
                                self._activate_challenge_window(page)
                                page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                                self._activate_challenge_window(page)
                                self._wait_for_user_verification(page)
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
                            if not GoogleSearchProvider._is_candidate(
                                result_url, str(row.get("text", ""))
                            ):
                                continue
                            domain = canonical_website_domain(result_url)
                            if not domain or domain in seen_domains:
                                continue
                            seen_domains.add(domain)
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
        )
        return any(marker in lowered for marker in markers)

    def _launch_browser(self, playwright, headless: bool):
        launch_options: dict[str, Any] = {"headless": headless}
        if not headless:
            # Force a separate, visible window so the user can complete a
            # provider challenge instead of it opening behind an existing
            # browser session.
            launch_options["args"] = [
                "--new-window",
                "--start-maximized",
                "--disable-backgrounding-occluded-windows",
                "--disable-features=CalculateNativeWinOcclusion",
            ]
            # Playwright adds this default for its managed browser process.
            # Remove it for the human verification handoff, otherwise the
            # challenge page can exist without a window the user can see.
            launch_options["ignore_default_args"] = ["--no-startup-window"]
        if self._executable_path:
            launch_options["executable_path"] = self._executable_path
        if self._proxy:
            launch_options["proxy"] = {"server": self._proxy}
        try:
            return playwright.chromium.launch(**launch_options)
        except Exception as error:
            raise SearchProviderError("Unable to launch the configured browser") from error

    def _activate_challenge_window(self, page) -> None:
        try:
            page.bring_to_front()
        except Exception:
            # Some lightweight test doubles and browser implementations do
            # not expose tab activation; visibility still comes from the
            # headful launch options.
            pass
        if os.name != "nt":
            return
        try:
            user32 = ctypes.windll.user32
            # Window titles normally contain the provider brand ("Google")
            # rather than the full host ("google.com"). Match both forms so
            # the verification window is actually brought to the foreground.
            host_parts = self._host.lower().split(".")
            targets = {self._host.lower(), host_parts[0] if host_parts else self._host.lower()}
            enum_windows = user32.EnumWindows
            enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def visit(hwnd, _lparam):
                if not user32.IsWindowVisible(hwnd):
                    return True
                buffer = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, buffer, len(buffer))
                title = buffer.value.lower()
                if any(target in title for target in targets):
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    return False
                return True

            enum_windows(enum_windows_proc(visit), 0)
        except Exception:
            # Window activation is a best-effort Windows UX enhancement; the
            # visible Playwright launch remains the functional fallback.
            pass

    def _wait_for_user_verification(self, page) -> None:
        """Wait for the user to finish a visible verification page.

        The page remains visible only for this bounded handoff. No CAPTCHA is
        solved by the application and the search continues only after the
        challenge markers disappear.
        """
        deadline = time.monotonic() + self._challenge_timeout_ms / 1000
        while time.monotonic() < deadline:
            try:
                body_text = page.locator("body").inner_text()
                if (
                    not self._is_blocked(page.url, body_text)
                    or self._has_search_results(page)
                ):
                    return
            except Exception:
                pass
            page.wait_for_timeout(1000)
        raise SearchChallengeError(
            "Google browser search verification was not completed in time"
        )

    @staticmethod
    def _has_search_results(page) -> bool:
        """Accept a verified page even if a stale challenge phrase remains."""
        try:
            return page.locator(
                "#search h3, #rso h3, a h3, a[href^='/url?q='], "
                "a[href^='https://www.google.com/url?q=']"
            ).count() > 0
        except Exception:
            return False

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
