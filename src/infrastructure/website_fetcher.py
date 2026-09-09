"""官网内容采集适配器，输出可追溯的来源文档。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


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
        )

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
        candidates = re.findall(
            r"(?:mailto:)?([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
            unescape(html),
            flags=re.IGNORECASE,
        )
        visible = WebsiteFetcher._to_text(html)
        result: list[PublicEmail] = []
        seen: set[str] = set()
        for address in candidates:
            normalized = address.strip().lower()
            if normalized in seen or normalized.startswith(("example@", "noreply@", "no-reply@")):
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
