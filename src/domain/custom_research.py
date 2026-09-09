"""客户可配置的业务目录、背调字段和有证据的字段结果。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class ResearchFieldType(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"


_KEY = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def _clean_items(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.strip() for item in values if item.strip()))


@dataclass(frozen=True)
class BusinessOffering:
    """客户可以自由维护的业务/产品，不把任何行业写死在代码中。"""

    name: str
    key: str
    description: str = ""
    keywords: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("business offering name is required")
        if not _KEY.fullmatch(self.key.strip()):
            raise ValueError("business offering key must be snake_case and 2-64 chars")
        if not _clean_items(self.keywords):
            raise ValueError("business offering keywords are required")

    def to_dict(self) -> dict:
        return {
            "name": self.name.strip(),
            "key": self.key.strip(),
            "description": self.description.strip(),
            "keywords": list(_clean_items(self.keywords)),
        }


@dataclass(frozen=True)
class ResearchFieldDefinition:
    """单个可配置背调字段；关键词只是发现线索，不是事实本身。"""

    name: str
    key: str
    description: str = ""
    keywords: tuple[str, ...] = ()
    field_type: ResearchFieldType = ResearchFieldType.TEXT
    required: bool = False
    evidence_required: bool = True
    human_review: bool = True
    options: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("research field name is required")
        if not _KEY.fullmatch(self.key.strip()):
            raise ValueError("research field key must be snake_case and 2-64 chars")
        if not isinstance(self.field_type, ResearchFieldType):
            object.__setattr__(self, "field_type", ResearchFieldType(self.field_type))
        if self.field_type is ResearchFieldType.SELECT and not _clean_items(self.options):
            raise ValueError("select research fields require options")

    def to_dict(self) -> dict:
        return {
            "name": self.name.strip(),
            "key": self.key.strip(),
            "description": self.description.strip(),
            "keywords": list(_clean_items(self.keywords)),
            "type": self.field_type.value,
            "required": self.required,
            "evidence_required": self.evidence_required,
            "human_review": self.human_review,
            "options": list(_clean_items(self.options)),
        }


@dataclass(frozen=True)
class ResearchFieldValue:
    """字段值及其来源状态，防止把模型猜测伪装成真实资料。"""

    value: str = ""
    status: str = "unknown"
    confidence: float = 0.0
    sources: tuple[str, ...] = ()
    checked_at: str = ""

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("custom field confidence must be between 0 and 1")
        if self.status not in {"verified", "reported", "unknown", "conflicting"}:
            raise ValueError("invalid custom field status")

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "status": self.status,
            "confidence": self.confidence,
            "sources": list(dict.fromkeys(self.sources)),
            "checked_at": self.checked_at,
        }


def validate_unique_keys(items: tuple[BusinessOffering | ResearchFieldDefinition, ...]) -> None:
    keys = [item.key.strip() for item in items]
    if len(keys) != len(set(keys)):
        raise ValueError("custom configuration keys must be unique")
