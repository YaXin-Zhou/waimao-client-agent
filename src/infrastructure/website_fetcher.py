"""官网内容采集适配器，输出可追溯的来源文档。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from typing import Callable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from src.domain.lead import is_plausible_email


@dataclass(frozen=True)
class PublicEmail:
    address: str
    source_url: str
    excerpt: str


@dataclass(frozen=True)
class SourceDocument:
    url: str
    title: str
    text: str
    public_emails: tuple[PublicEmail, ...] = ()
    links: tuple[str, ...] = ()


class WebsiteFetcher:
    def __init__(
        self,
        opener: Callable[[str, int], bytes] | None = None,
        timeout: int = 15,
    ):
        self._opener = opener or self._open
        self._timeout = timeout

    def fetch(self, url: str) -> SourceDocument:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only HTTP(S) URLs are supported")
        raw_html = self._opener(url, self._timeout)
        html = raw_html.decode("utf-8", errors="replace")
        title = self._extract_tag(html, "title")
        text = self._to_text(html)
        return SourceDocument(
            url=url,
            title=title,
            text=text,
            public_emails=self._extract_public_emails(html, url),
            links=self._extract_links(html, url),
        )

    def fetch_contact_pages(
        self,
        url: str,
        max_pages: int = 5,
        allow_external_sources: bool = False,
        max_external_pages: int = 3,
        priority_terms: tuple[str, ...] = (),
    ) -> tuple[SourceDocument, ...]:
        """抓取有限的相关页面；外站只跟随官网明确链接且有独立上限。"""
        if max_pages <= 0:
            raise ValueError("max_pages must be positive")
        if max_external_pages < 0:
            raise ValueError("max_external_pages must not be negative")
        home = self.fetch(url)
        documents = [home]
        seen = {self._page_key(home.url)}
        external_count = 0
        for link in sorted(
            home.links,
            key=lambda item: self._link_priority(item, priority_terms),
            reverse=True,
        ):
            if len(documents) >= max_pages:
                break
            page_key = self._page_key(link)
            if page_key in seen:
                continue
            parsed_link = urlparse(link)
            link_host = (parsed_link.hostname or "").lower().removeprefix("www.")
            home_host = (urlparse(home.url).hostname or "").lower().removeprefix("www.")
            same_domain = link_host == home_host
            if not same_domain:
                if not allow_external_sources or external_count >= max_external_pages:
                    continue
                external_count += 1
            seen.add(page_key)
            try:
                documents.append(self.fetch(link))
            except Exception:
                continue
        return tuple(documents)

    @staticmethod
    def _page_key(url: str) -> str:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().removeprefix("www.")
        return parsed._replace(netloc=hostname).geturl().rstrip("/")

    @staticmethod
    def _link_priority(url: str, priority_terms: tuple[str, ...] = ()) -> int:
        """Prioritize product/contact evidence while preserving link order within a tier."""
        path = urlparse(url).path.lower()
        path_tokens = {token.rstrip("s") for token in re.findall(r"[a-z0-9]+", path)}
        for term in priority_terms:
            term_tokens = {
                token.rstrip("s") for token in re.findall(r"[a-z0-9]+", term.lower())
            }
            if term_tokens and term_tokens <= path_tokens:
                return 60
        if any(term in path for term in ("product", "power-station", "generator", "solution")):
            return 30
        if any(term in path for term in ("contact", "imprint", "impressum", "legal")):
            return 20
        if any(term in path for term in ("company", "about", "history")):
            return 10
        return 0

    @staticmethod
    def _open(url: str, timeout: int) -> bytes:
        request = Request(url, headers={"User-Agent": "waimao-client-agent/0.1"})
        with urlopen(request, timeout=timeout) as response:
            return response.read()

    @staticmethod
    def _extract_tag(html: str, tag: str) -> str:
        match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html, flags=re.IGNORECASE | re.DOTALL)
        return " ".join(unescape(match.group(1)).split()) if match else ""

    @staticmethod
    def _to_text(html: str) -> str:
        without_noise = re.sub(
            r"<(script|style|noscript)[^>]*>.*?</\1>",
            " ",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        without_tags = re.sub(r"<[^>]+>", " ", without_noise)
        return " ".join(unescape(without_tags).split())

    @staticmethod
    def _extract_public_emails(html: str, source_url: str) -> tuple[PublicEmail, ...]:
        decoded_html = unescape(html)
        visible = WebsiteFetcher._to_text(html)
        candidates = re.findall(
            r"(?:mailto:)?([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
            visible,
            flags=re.IGNORECASE,
        )
        candidates.extend(
            re.findall(
                r"mailto:([^\"'\s>?]+)",
                decoded_html,
                flags=re.IGNORECASE,
            )
        )
        result: list[PublicEmail] = []
        seen: set[str] = set()
        for address in candidates:
            normalized = address.strip().lower()
            if (
                normalized in seen
                or normalized.startswith(("noreply@", "no-reply@"))
                or not is_plausible_email(normalized)
            ):
                continue
            position = visible.lower().find(normalized)
            excerpt = (
                visible[max(0, position - 80) : position + len(normalized) + 80]
                if position >= 0
                else normalized
            )
            result.append(PublicEmail(normalized, source_url, excerpt))
            seen.add(normalized)
        return tuple(result)

    @staticmethod
    def _extract_links(html: str, base_url: str) -> tuple[str, ...]:
        base = urlparse(base_url)
        if not base.hostname:
            return ()
        matches = re.findall(
            r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        keywords = (
            "contact",
            "about",
            "imprint",
            "impressum",
            "legal",
            "company",
            "support",
            "purchase",
            "sourcing",
            "product",
            "solution",
            "catalog",
            "generator",
            "power",
            "equipment",
        )
        links: list[str] = []
        for href, anchor in matches:
            candidate = urljoin(base_url, unescape(href).strip()).split("#", 1)[0]
            parsed = urlparse(candidate)
            if parsed.scheme not in {"http", "https"}:
                continue
            haystack = f"{parsed.path} {unescape(anchor)}".lower()
            if not any(keyword in haystack for keyword in keywords):
                continue
            if candidate not in links:
                links.append(candidate)
        return tuple(links)
