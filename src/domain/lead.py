"""潜客公司、客户档案清洗和可配置评分规则。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from email.utils import parseaddr
from enum import StrEnum
from urllib.parse import urlparse


@dataclass(frozen=True)
class LeadRecord:
    """来自搜索或官网的原始潜客记录。"""

    company_name: str
    website: str = ""
    email: str = ""
    country: str = ""
    source_url: str = ""
    source_excerpt: str = ""


class LeadStatus(StrEnum):
    NEW = "new"
    CLEANING = "cleaning"
    AWAITING_SCORE = "awaiting_score"
    AWAITING_REVIEW = "awaiting_review"
    SELECTED = "selected"
    CONTACTED = "contacted"
    REPLIED = "replied"
    FOLLOWING_UP = "following_up"
    CONVERTED = "converted"
    PAUSED = "paused"
    INVALID = "invalid"


@dataclass(frozen=True)
class CleanLead:
    """清洗后的客户档案核心视图。"""

    company_name: str
    domain: str
    emails: tuple[str, ...]
    country: str
    quality: str
    flags: tuple[str, ...] = ()
    sources: tuple[tuple[str, str], ...] = ()
    status: LeadStatus = LeadStatus.NEW

    def transition_to(self, target: "LeadStatus") -> "CleanLead":
        allowed = {
            LeadStatus.NEW: {LeadStatus.CLEANING, LeadStatus.AWAITING_SCORE},
            LeadStatus.CLEANING: {LeadStatus.AWAITING_SCORE, LeadStatus.INVALID},
            LeadStatus.AWAITING_SCORE: {
                LeadStatus.AWAITING_REVIEW,
                LeadStatus.SELECTED,
                LeadStatus.INVALID,
            },
            LeadStatus.AWAITING_REVIEW: {LeadStatus.SELECTED, LeadStatus.INVALID},
            LeadStatus.SELECTED: {LeadStatus.CONTACTED, LeadStatus.PAUSED, LeadStatus.INVALID},
            LeadStatus.CONTACTED: {LeadStatus.REPLIED, LeadStatus.FOLLOWING_UP, LeadStatus.PAUSED},
            LeadStatus.REPLIED: {LeadStatus.FOLLOWING_UP, LeadStatus.CONVERTED, LeadStatus.PAUSED},
            LeadStatus.FOLLOWING_UP: {LeadStatus.REPLIED, LeadStatus.CONVERTED, LeadStatus.PAUSED},
            LeadStatus.CONVERTED: set(),
            LeadStatus.PAUSED: {LeadStatus.SELECTED, LeadStatus.CONTACTED, LeadStatus.FOLLOWING_UP},
            LeadStatus.INVALID: set(),
        }
        if target not in allowed[self.status]:
            raise ValueError(f"Invalid lead transition: {self.status} -> {target}")
        return replace(self, status=target)


@dataclass(frozen=True)
class LeadScore:
    total: int
    priority: str
    breakdown: dict[str, int]


_COUNTRY_NAMES = {"DE": "Germany", "CN": "China", "US": "United States", "GB": "United Kingdom"}
_PLACEHOLDER_EMAIL_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "domain.com",
    "contoso.com",
    "test.com",
}
_NON_EMAIL_FILE_TLDS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "avif", "ico"}


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _normalize_domain(website: str) -> str:
    raw = website.strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or "").lower().removeprefix("www.")


def _normalize_email(email: str) -> str:
    raw = email.strip().lower()
    for token in ("(at)", "[at]", " at "):
        raw = raw.replace(token, "@")
    for token in ("(dot)", "[dot]", " dot "):
        raw = raw.replace(token, ".")
    address = parseaddr(raw)[1]
    return address if is_plausible_email(address) else ""


def is_plausible_email(email: str) -> bool:
    """Reject obvious asset filenames and placeholder addresses before persistence."""
    address = parseaddr(email.strip().lower())[1]
    if "@" not in address:
        return False
    local, domain = address.rsplit("@", 1)
    if not local or "." not in domain:
        return False
    if domain in _PLACEHOLDER_EMAIL_DOMAINS:
        return False
    if domain.rsplit(".", 1)[-1] in _NON_EMAIL_FILE_TLDS:
        return False
    return True


def _normalize_country(country: str) -> str:
    value = _normalize_text(country)
    return _COUNTRY_NAMES.get(value.upper(), value)


def clean_leads(records: list[LeadRecord]) -> list[CleanLead]:
    """规范化并按域名合并潜客记录，保留确定性顺序和质量标记。"""
    groups: dict[str, list[LeadRecord]] = {}
    for record in records:
        domain = _normalize_domain(record.website)
        key = domain or _normalize_text(record.company_name).lower()
        groups.setdefault(key, []).append(record)

    result: list[CleanLead] = []
    for group in groups.values():
        names = [
            _normalize_text(item.company_name)
            for item in group
            if _normalize_text(item.company_name)
        ]
        company_name = max(names, key=len, default="Unknown")
        domain = next(
            (_normalize_domain(item.website) for item in group if _normalize_domain(item.website)),
            "",
        )
        email_values = [_normalize_email(item.email) for item in group]
        emails = tuple(dict.fromkeys(value for value in email_values if value))
        country_values = [_normalize_country(item.country) for item in group]
        countries = tuple(dict.fromkeys(value for value in country_values if value))
        sources = tuple(
            dict.fromkeys(
                (item.source_url.strip(), item.source_excerpt.strip())
                for item in group
                if item.source_url.strip()
            )
        )
        flags: list[str] = []
        if not domain:
            flags.append("missing_website")
        if not emails:
            flags.append("invalid_email")
        if domain and any(
            email.rsplit("@", 1)[-1] != domain for email in emails if "@" in email
        ):
            flags.append("email_domain_mismatch")
        if len(countries) > 1:
            flags.append("conflicting_country")
        country = countries[0] if countries else ""
        quality = "complete" if domain and emails and len(countries) <= 1 else "needs_review"
        result.append(
            CleanLead(company_name, domain, emails, country, quality, tuple(flags), sources)
        )
    return result


def score_lead(lead: CleanLead, weights: dict[str, int], signals: dict[str, int]) -> LeadScore:
    """按调用方提供的权重和信号计算评分，评分项不写死在领域规则中。"""
    breakdown = {
        key: max(0, min(int(signals.get(key, 0)), int(weight)))
        for key, weight in weights.items()
    }
    total = sum(breakdown.values())
    priority = "A" if total >= 80 else "B" if total >= 60 else "C" if total >= 40 else "D"
    return LeadScore(total=total, priority=priority, breakdown=breakdown)
