"""创建 SQLite 运行数据备份；只复制，不删除或覆盖已有备份。"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path


def backup(database: Path, destination: Path) -> Path:
    if not database.is_file():
        raise FileNotFoundError(f"database not found: {database}")
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = destination / f"acquisition-{stamp}.db"
    if target.exists():
        raise FileExistsError(f"backup already exists: {target}")
    shutil.copy2(database, target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup the local acquisition SQLite database")
    parser.add_argument("--database", type=Path, default=Path("data/runtime/acquisition.db"))
    parser.add_argument("--destination", type=Path, default=Path("data/backups"))
    args = parser.parse_args()
    print(backup(args.database, args.destination))


if __name__ == "__main__":
    main()
