"""Small, dependency-free CLI bridge for the internal WorkBuddy Skill."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def call(base_url: str, method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(f"local workflow API request failed: {error}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="WorkBuddy local workflow bridge")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ready")
    sub.add_parser("tasks")
    leads = sub.add_parser("leads")
    leads.add_argument("task_id")
    lead = sub.add_parser("lead")
    lead.add_argument("task_id")
    lead.add_argument("domain")
    sync = sub.add_parser("sync-mailbox")
    sync.add_argument("task_id")
    analyze = sub.add_parser("analyze-replies")
    analyze.add_argument("task_id")
    args = parser.parse_args()

    routes = {
        "ready": ("GET", "/api/ready", None),
        "tasks": ("GET", "/api/tasks", None),
        "leads": ("GET", f"/api/tasks/{args.task_id}/leads", None),
        "lead": ("GET", f"/api/tasks/{args.task_id}/leads/{args.domain}", None),
        "sync-mailbox": ("POST", f"/api/tasks/{args.task_id}/mailbox/sync", {}),
        "analyze-replies": ("POST", f"/api/tasks/{args.task_id}/reply-analyses/run", {}),
    }
    try:
        method, path, payload = routes[args.command]
        print(json.dumps(call(args.base_url, method, path, payload), ensure_ascii=False))
        return 0
    except RuntimeError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
