"""浏览器搜索结果适配器。

浏览器控制器负责打开 Google、执行搜索和读取可见结果；本适配器只负责把
读取到的结构化结果转换为 SearchProvider 的 LeadRecord。这样浏览器工具可替换，
领域层不感知 UI 自动化细节。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.application.search_queries import build_search_queries
from src.domain.lead import LeadRecord
from src.domain.task import AcquisitionCriteria


@dataclass(frozen=True)
class BrowserSearchResult:
    title: str
    website: str
    excerpt: str = ""
    source_url: str = ""


class BrowserSearchProvider:
    """将浏览器控制器返回的搜索结果转换为原始潜客记录。"""

    def __init__(self, search_page: Callable[[str, int], list[BrowserSearchResult]]):
        self._search_page = search_page

    def search(self, criteria: AcquisitionCriteria) -> list[LeadRecord]:
        records: list[LeadRecord] = []
        seen: set[str] = set()
        for query in build_search_queries(criteria):
            for result in self._search_page(query, criteria.daily_limit):
                website = result.website.strip()
                if not website or website in seen:
                    continue
                seen.add(website)
                records.append(
                    LeadRecord(
                        company_name=result.title.strip() or "Unknown",
                        website=website,
                        source_url=result.source_url.strip() or website,
                        source_excerpt=result.excerpt.strip(),
                    )
                )
                if len(records) >= criteria.daily_limit:
                    return records
        return records
