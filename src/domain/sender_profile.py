"""发件人资料：由业务人员填写，供开发信生成时使用。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SenderProfile:
    company_name: str = ""
    contact_name: str = ""
    position: str = ""

    def __post_init__(self) -> None:
        for value in (self.company_name, self.contact_name, self.position):
            if "\n" in value or "\r" in value:
                raise ValueError("sender profile fields must be single-line")

    def prompt_values(self) -> tuple[str, str, str]:
        return (
            self.company_name.strip() or "[Our Company]",
            self.contact_name.strip() or "[Your Name]",
            self.position.strip() or "[Your Position]",
        )
