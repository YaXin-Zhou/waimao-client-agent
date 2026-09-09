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
        site_name = self._extract_meta_site_name(html)
        if site_name and site_name.casefold() not in title.casefold():
            title = " - ".join(value for value in (title, site_name) if value)
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
        home_host = self._host_key(home.url)
        same_domain_links = [
            link for link in home.links if self._host_key(link) == home_host
        ]
        external_links = [
            link for link in home.links if self._host_key(link) != home_host
        ]
        for link in self._order_same_domain_links(same_domain_links, priority_terms):
            if len(documents) >= max_pages:
                break
            page_key = self._page_key(link)
            if page_key in seen:
                continue
            seen.add(page_key)
            try:
                document = self.fetch(link)
            except Exception:
                continue
            documents.append(document)
        if len(documents) < max_pages:
            self._append_sitemap_pages(
                documents,
                seen,
                home.url,
                max_pages,
                priority_terms,
            )
        self._append_fallback_pages(documents, seen, home.url, max_pages)
        if allow_external_sources:
            external_count = 0
            for link in sorted(
                external_links,
                key=lambda item: self._link_priority(item, priority_terms),
                reverse=True,
            ):
                if len(documents) >= max_pages or external_count >= max_external_pages:
                    break
                page_key = self._page_key(link)
                if page_key in seen:
                    continue
                external_count += 1
                seen.add(page_key)
                try:
                    document = self.fetch(link)
                except Exception:
                    continue
                if not self._external_matches_identity(home, link, document):
                    continue
                documents.append(document)
        return tuple(documents)

    @classmethod
    def _order_same_domain_links(
        cls, links: list[str], priority_terms: tuple[str, ...]
    ) -> tuple[str, ...]:
        """Reserve crawl budget for both contact and product evidence when available."""
        ranked = sorted(
            dict.fromkeys(links),
            key=lambda item: cls._link_priority(item, priority_terms),
            reverse=True,
        )
        selected: list[str] = []
        for predicate in (
            cls._is_contact_path,
            lambda item: cls._is_product_path(item)
            or cls._link_priority(item, priority_terms) >= 60,
        ):
            match = next((item for item in ranked if predicate(item)), None)
            if match and match not in selected:
                selected.append(match)
        selected.extend(item for item in ranked if item not in selected)
        return tuple(selected)

    @staticmethod
    def _is_contact_path(url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(term in path for term in ("contact", "imprint", "impressum", "legal"))

    @staticmethod
    def _is_product_path(url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(
            term in path
            for term in ("product", "power-station", "generator", "solution")
        )

    def _append_fallback_pages(
        self,
        documents: list[SourceDocument],
        seen: set[str],
        home_url: str,
        max_pages: int,
    ) -> None:
        """Fill unused crawl budget with conventional contact/company paths."""
        for link in self._fallback_page_urls(home_url):
            if len(documents) >= max_pages:
                return
            page_key = self._page_key(link)
            if page_key in seen:
                continue
            seen.add(page_key)
            try:
                documents.append(self.fetch(link))
            except Exception:
                continue

    @staticmethod
    def _fallback_page_urls(home_url: str) -> tuple[str, ...]:
        """Probe a small set of conventional pages when navigation is script-rendered."""
        parsed = urlparse(home_url)
        if not parsed.hostname:
            return ()
        paths = (
            "/contact",
            "/contact-us",
            "/imprint",
            "/impressum",
            "/about",
            "/company",
            "/products",
        )
        return tuple(
            parsed._replace(path=path, params="", query="", fragment="").geturl()
            for path in paths
        )

    def _append_sitemap_pages(
        self,
        documents: list[SourceDocument],
        seen: set[str],
        home_url: str,
        max_pages: int,
        priority_terms: tuple[str, ...],
    ) -> None:
        """Use bounded same-domain sitemaps only when navigation is insufficient."""
        home_host = self._host_key(home_url)
        sitemap_queue = [
            urljoin(home_url, "/sitemap.xml"),
            urljoin(home_url, "/sitemap_index.xml"),
        ]
        visited_sitemaps: set[str] = set()
        page_urls: list[str] = []
        # Sitemap indexes commonly point to several child sitemaps.  Read only
        # a small same-domain set so a large site cannot turn this bounded crawl
        # into an unbounded download.
        while sitemap_queue and len(visited_sitemaps) < 4:
            sitemap_url = sitemap_queue.pop(0)
            sitemap_key = self._page_key(sitemap_url)
            if sitemap_key in visited_sitemaps or self._host_key(sitemap_url) != home_host:
                continue
            visited_sitemaps.add(sitemap_key)
            try:
                sitemap = self.fetch(sitemap_url)
            except Exception:
                continue
            for link in self._extract_sitemap_urls(sitemap.text):
                if self._host_key(link) != home_host:
                    continue
                if self._is_sitemap_url(link):
                    if self._page_key(link) not in visited_sitemaps:
                        sitemap_queue.append(link)
                else:
                    page_urls.append(link)
        sitemap_urls = sorted(
            dict.fromkeys(page_urls),
            key=lambda item: self._link_priority(item, priority_terms),
            reverse=True,
        )
        for link in sitemap_urls:
            if len(documents) >= max_pages:
                return
            page_key = self._page_key(link)
            if page_key in seen or self._host_key(link) != home_host:
                continue
            seen.add(page_key)
            try:
                documents.append(self.fetch(link))
            except Exception:
                continue

    @staticmethod
    def _page_key(url: str) -> str:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().removeprefix("www.")
        return parsed._replace(netloc=hostname).geturl().rstrip("/")

    @staticmethod
    def _host_key(url: str) -> str:
        return (urlparse(url).hostname or "").lower().removeprefix("www.")

    @staticmethod
    def _is_sitemap_url(url: str) -> bool:
        return urlparse(url).path.lower().endswith((".xml", ".xml.gz"))

    @classmethod
    def _external_matches_identity(
        cls, home: SourceDocument, external_url: str, document: SourceDocument
    ) -> bool:
        """Require a small identity overlap before accepting an explicitly linked external page."""
        identity = cls._identity_tokens(home.title or home.url)
        if not identity:
            return False
        external_text = " ".join(
            (external_url, document.title, document.text[:1200])
        )
        return bool(identity & cls._identity_tokens(external_text))

    @staticmethod
    def _identity_tokens(value: str) -> set[str]:
        ignored = {
            "about",
            "contact",
            "company",
            "com",
            "home",
            "official",
            "products",
            "product",
            "solutions",
            "www",
        }
        return {
            token
            for token in re.findall(r"[a-z0-9]+", value.lower())
            if len(token) >= 4 and token not in ignored
        }

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
        # Keep contact/company pages competitive with product pages.  A bounded
        # crawl that only follows product URLs can otherwise miss the public
        # mailbox needed by the next stage of the workflow.
        if any(term in path for term in ("contact", "imprint", "impressum", "legal")):
            return 50
        if any(term in path for term in ("company", "about", "history")):
            return 20
        if any(term in path for term in ("product", "power-station", "generator", "solution")):
            return 40
        return 0

    @staticmethod
    def _extract_sitemap_urls(text: str) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                match.rstrip("/.,;)")
                for match in re.findall(r"https?://[^\s<>\"']+", text)
            )
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
    def _extract_meta_site_name(html: str) -> str:
        """Read the standard public site-name metadata for identity evidence."""
        for tag in re.findall(r"<meta\b[^>]*>", html, flags=re.IGNORECASE):
            attributes = {
                key.lower(): unescape(value).strip()
                for key, value in re.findall(
                    r"([:\w-]+)\s*=\s*[\"'](.*?)[\"']", tag, flags=re.IGNORECASE
                )
            }
            property_name = attributes.get("property", "").casefold()
            name = attributes.get("name", "").casefold()
            if property_name == "og:site_name" or name == "application-name":
                return " ".join(attributes.get("content", "").split())
        return ""

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
        candidates.extend(
            re.findall(
                r"[A-Z0-9._%+-]+\s*(?:\[at\]|\(at\)|\s+at\s+)\s*"
                r"[A-Z0-9.-]+\s*(?:\[dot\]|\(dot\)|\s+dot\s+)\s*[A-Z]{2,}",
                visible,
                flags=re.IGNORECASE,
            )
        )
        result: list[PublicEmail] = []
        seen: set[str] = set()
        for address in candidates:
            raw_address = address.strip()
            normalized = re.sub(
                r"\s*(?:\[at\]|\(at\)|\s+at\s+)\s*",
                "@",
                raw_address,
                flags=re.IGNORECASE,
            )
            normalized = re.sub(
                r"\s*(?:\[dot\]|\(dot\)|\s+dot\s+)\s*",
                ".",
                normalized,
                flags=re.IGNORECASE,
            ).lower()
            if (
                normalized in seen
                or normalized.startswith(("noreply@", "no-reply@"))
                or not is_plausible_email(normalized)
            ):
                continue
            position = visible.lower().find(normalized)
            if position < 0:
                position = visible.lower().find(raw_address.lower())
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
