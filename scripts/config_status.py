"""输出本地集成配置状态，不打印任何密钥或账号值。"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / ".env"


def read_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def configured(values: dict[str, str], fields: tuple[str, ...]) -> bool:
    return all(values.get(field, "").strip() for field in fields)


def main() -> int:
    values = read_values(CONFIG)
    result = {
        "config_file_present": CONFIG.exists(),
        "deepseek_configured": configured(values, ("DEEPSEEK_API_KEY",)),
        "ali_imap_configured": configured(
            values, ("ALI_IMAP_HOST", "ALI_IMAP_USERNAME", "ALI_IMAP_PASSWORD")
        ),
        "ali_smtp_configured": configured(
            values, ("ALI_SMTP_HOST", "ALI_SMTP_USERNAME", "ALI_SMTP_PASSWORD")
        ),
        "warning": "Only booleans are shown; credentials are intentionally omitted.",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
