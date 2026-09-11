"""Google HTML 搜索适配器。

该适配器只采集搜索结果中的公开链接和页面标题，不猜测邮箱，也不承担
清洗、评分或背调职责。浏览器/其他搜索服务可以在同一 SearchProvider 边界替换它。
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Callable
from urllib.parse import parse_qs, quote_plus, urlsplit
from urllib.request import Request, urlopen

from src.application.search_queries import build_search_queries_for_round
from src.domain.lead import LeadRecord, canonical_website_domain
from src.domain.task import AcquisitionCriteria, effective_candidate_limit


class SearchProviderError(RuntimeError):
    """搜索服务不可用、返回异常页面或无法解析时抛出。"""


class _GoogleResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._href = ""
        self._text: list[str] = []
        self.results: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag != "a" or self._href:
            return
        href = dict(attrs).get("href", "")
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._href:
            return
        title = " ".join("".join(self._text).split())
        if title:
            self.results.append((self._href, title))
        self._href = ""
        self._text = []


class GoogleSearchProvider:
    _COUNTRY_MARKERS = {
        "china": ("china", ".cn"),
        "中国": ("china", ".cn"),
        "singapore": ("singapore", ".sg"),
        "新加坡": ("singapore", ".sg"),
        "germany": ("germany", ".de"),
        "德国": ("germany", ".de"),
        "france": ("france", ".fr"),
        "法国": ("france", ".fr"),
        "italy": ("italy", ".it"),
        "意大利": ("italy", ".it"),
        "india": ("india",),
        "印度": ("india",),
        "united states": ("united-states", ".us"),
        "美国": ("united-states", ".us"),
    }

    @classmethod
    def _has_obvious_country_mismatch(cls, criteria, url: str) -> bool:
        configured = {str(value).strip().casefold() for value in criteria.countries}
        if not configured:
            return False
        allowed_markers = set()
        for country in configured:
            allowed_markers.update(cls._COUNTRY_MARKERS.get(country, (country,)))
        parsed = urlsplit(url)
        location = f"{parsed.hostname or ''}{parsed.path}".casefold()
        for country, markers in cls._COUNTRY_MARKERS.items():
            if country in configured:
                continue
            if any(marker in location for marker in markers) and not any(
                marker in location for marker in allowed_markers
            ):
                return True
        return False

    @classmethod
    def _has_country_signal(cls, criteria, text: str) -> bool:
        """Require a visible target-country signal when country is configured."""
        configured = tuple(str(value).strip().casefold() for value in criteria.countries)
        if not configured:
            return True
        haystack = str(text).casefold()
        return any(
            any(marker in haystack for marker in cls._COUNTRY_MARKERS.get(country, (country,)))
            for country in configured
        )

    """通过 Google 的公开 HTML 结果页获取有限数量候选官网。"""

    _NON_COMPANY_RESULT_HOSTS = frozenset(
        {
            "linkedin.com",
            "indeed.com",
            "ziprecruiter.com",
            "naukri.com",
            "jobsdb.com",
            "experteer.com",
            "bebee.com",
            "facebook.com",
            "instagram.com",
            "youtube.com",
            "zoominfo.com",
            "exactdata.com",
            "wikipedia.org",
            "britannica.com",
            "merriam-webster.com",
            "dictionary.cambridge.org",
            "npr.org",
            "reddit.com",
            "quora.com",
            "pinterest.com",
            "amazon.com",
            "alibaba.com",
            "aliexpress.com",
            "thomasnet.com",
            "europages.com",
            "europages.co.uk",
            "ensun.io",
            "producthunt.com",
            "supplierscentral.com",
            "ariba.com",
            "walmart.com",
            "homedepot.com",
            "sciencedirect.com",
            "scienceinsights.org",
            "nationalgeographic.org",
            "ourworldindata.org",
            "investopedia.com",
            "techtarget.com",
            "baike.baidu.com",
            "wallstreetmojo.com",
            "globalsources.com",
            "tradekey.com",
            "trademo.com",
            "tradeford.com",
            "kompass.com",
            "seair.co.in",
            "accio.com",
            "nasdaq.com",
            "bsd405.org",
            "international.bsd405.org",
            "ibm.com",
            "translate.goog",
            "microsoft.com",
            "office.com",
            "live.com",
            # AI/productivity and general directory pages are frequent false
            # positives for broad B2B product queries.
            "openai.com",
            "chatgpt.com",
            "crunchbase.com",
            "glassdoor.com",
            "mapquest.com",
            "github.com",
            "gitlab.com",
            "zhihu.com",
            "csdn.net",
            "stackoverflow.com",
            "medium.com",
            "cellphones.com.vn",
            "gamer.com.tw",
            "bilibili.com",
            "weibo.com",
            "baidu.com",
            "daum.net",
            # Software/project and generic industry-information sites that
            # frequently rank for broad product terms but are not buyers.
            "portableapps.com",
            "portapps.io",
            "sourceforge.net",
            "themanufacturer.com",
            "manufacturer.com",
            # Non-commercial environmental organizations are not prospects
            # for manufacturing outreach, even when their pages mention
            # plastics or injection-related topics.
            "wwf.org",
            "wwf.sg",
            "wwf.panda.org",
        }
    )

    def __init__(
        self,
        opener: Callable[..., object] = urlopen,
        timeout: float = 15.0,
        max_results_per_query: int = 10,
        max_pages_per_query: int = 1,
        host: str = "www.google.com.hk",
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_results_per_query <= 0:
            raise ValueError("max_results_per_query must be positive")
        if max_pages_per_query <= 0:
            raise ValueError("max_pages_per_query must be positive")
        if not host.strip() or "/" in host:
            raise ValueError("Google search host must be a hostname")
        self._opener = opener
        self._timeout = timeout
        self._max_results = max_results_per_query
        self._max_pages = max_pages_per_query
        self._host = host.strip()

    def search(self, criteria: AcquisitionCriteria) -> list[LeadRecord]:
        return self.search_round(criteria, 0)

    def search_round(
        self, criteria: AcquisitionCriteria, round_index: int = 0
    ) -> list[LeadRecord]:
        results: list[LeadRecord] = []
        seen_domains: set[str] = set()
        candidate_limit = effective_candidate_limit(criteria)
        queries = build_search_queries_for_round(criteria, round_index)
        intent_suffixes = ("", "contact", "supplier", "manufacturer", "factory", "distributor", "purchasing", "procurement")
        suffix = intent_suffixes[round_index % len(intent_suffixes)]
        if suffix:
            queries = tuple(f"{query} {suffix}" for query in queries)
        for query in queries:
            # Search engines treat deep pagination as automated scraping very
            # quickly.  Broad query variants are more useful than repeatedly
            # turning pages for one variant, and discovery is accumulated over
            # multiple runs during the day.  Keep the per-query request budget
            # explicit so one click cannot cause dozens of Google requests.
            page_count = min(
                self._max_pages,
                max(1, (candidate_limit + self._max_results - 1) // self._max_results),
            )
            for page_start in range(0, page_count * self._max_results, self._max_results):
                request = Request(
                    f"https://{self._host}/search?q={quote_plus(query)}"
                    f"&num={self._max_results}&start={page_start}",
                    headers={"User-Agent": "Mozilla/5.0 (compatible; ClientResearch/1.0)"},
                )
                search_url = request.full_url
                try:
                    response = self._opener(request, timeout=self._timeout)
                    html = response.read().decode("utf-8", errors="replace")
                except Exception as error:  # network/HTTP errors must not become empty results
                    raise SearchProviderError(
                        f"Google search failed for query: {query}"
                    ) from error
                parser = _GoogleResultParser()
                parser.feed(html)
                if self._requires_browser(html) and not any(
                    self._is_candidate(self._result_url(href)) for href, _title in parser.results
                ):
                    raise SearchProviderError(
                        "Google returned a JavaScript-only or consent page; use the browser adapter"
                    )
                added_on_page = 0
                for href, title in parser.results:
                    url = self._result_url(href)
                    domain = canonical_website_domain(url)
                    if (
                        not self._is_candidate(url, title)
                        or not domain
                        or domain in seen_domains
                    ):
                        continue
                    seen_domains.add(domain)
                    results.append(
                        LeadRecord(
                            company_name=title,
                            website=url,
                            source_url=search_url,
                            source_excerpt=title,
                        )
                    )
                    added_on_page += 1
                    if len(results) >= candidate_limit:
                        return results
                if added_on_page == 0:
                    # A page may contain only filtered directories, duplicates,
                    # or non-company results. Keep the bounded pagination so a
                    # noisy page cannot hide valid candidates on the next one.
                    continue
        return results

    @staticmethod
    def _result_url(href: str) -> str:
        parsed = urlsplit(href)
        if parsed.path == "/url":
            return parse_qs(parsed.query).get("q", [""])[0]
        return href

    @staticmethod
    def _is_candidate(url: str, title: str = "") -> bool:
        parsed = urlsplit(url)
        hostname = parsed.hostname or ""
        normalized_host = hostname.lower().removeprefix("www.")
        # Regional search hosts such as google.co.jp are not customer sites.
        is_google = normalized_host.startswith("google.") or ".google." in normalized_host
        normalized_path = parsed.path.lower()
        is_non_company_result = any(
            normalized_host == host or normalized_host.endswith(f".{host}")
            for host in GoogleSearchProvider._NON_COMPANY_RESULT_HOSTS
        )
        is_non_company_path = any(
            f"/{segment}/" in f"{normalized_path}/"
            or normalized_path.endswith(f"/{segment}")
            for segment in (
                "article",
                "articles",
                "blog",
                "education",
                "glossary",
                "learn",
                "news",
                "resources",
                "wiki",
                "definition",
                "terms",
                "calendar",
                "students",
                "faculty",
                "campus",
                "courses",
            )
        )
        is_explanatory_path = any(
            normalized_path.startswith(f"/{prefix}")
            for prefix in ("/how-", "/what-is-", "/why-")
        )
        is_nested_explanatory_path = any(
            marker in normalized_path
            for marker in ("/how-", "/what-is-", "/why-")
        )
        normalized_title = title.casefold()
        is_non_company_title = any(
            marker in normalized_title
            for marker in (
                "school",
                "elementary",
                "university",
                "college",
                "academy",
                "student",
                "district",
                "buyers list",
                "import data",
                "market data",
                "financial technology",
                "top suppliers",
                "top plastic mold makers",
                "portableapps",
                "sourceforge",
                "the manufacturer",
                "manufacturer.com",
            )
        )
        is_explanatory_title = any(
            marker in normalized_title
            for marker in (
                "what is",
                "how to",
                "how is",
                "definition",
                "guide",
                "tutorial",
                "explained",
                "wikipedia",
            )
        )
        is_public_institution = hostname.endswith((".gov", ".edu")) or ".gov." in hostname
        return (
            parsed.scheme in {"http", "https"}
            and bool(hostname)
            and not is_google
            and not is_non_company_result
            and not is_non_company_path
            and not is_explanatory_path
            and not is_nested_explanatory_path
            and not is_public_institution
            and not is_explanatory_title
            and not is_non_company_title
        )

    @staticmethod
    def _requires_browser(html: str) -> bool:
        markers = ("/httpservice/retry/enablejs", "enable javascript", "consent.google")
        lowered = html.lower()
        return any(marker in lowered for marker in markers)
