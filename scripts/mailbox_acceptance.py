"""执行专用阿里邮箱的只读验收链路；本脚本永远不调用 SMTP。"""

from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def call(base_url: str, method: str, path: str) -> dict:
    request = Request(f"{base_url.rstrip('/')}{path}", method=method)
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(f"{method} {path} failed: {error}") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"{method} {path} returned a non-object response")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    try:
        status = call(args.base_url, "GET", "/api/mailbox/status")
        if not status.get("configured"):
            raise RuntimeError("Ali IMAP is not configured; add a dedicated test mailbox first")
        connection = call(args.base_url, "POST", "/api/mailbox/test")
        sync = call(args.base_url, "POST", f"/api/tasks/{args.task_id}/mailbox/sync")
        threads = call(args.base_url, "GET", f"/api/tasks/{args.task_id}/mail-threads")
        analyses = call(args.base_url, "POST", f"/api/tasks/{args.task_id}/reply-analyses/run")
        follow_ups = call(args.base_url, "GET", f"/api/tasks/{args.task_id}/follow-up-tasks")
    except RuntimeError as error:
        print(json.dumps({"accepted": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({
        "accepted": True,
        "read_only": connection.get("read_only", False),
        "mail_read": connection.get("mail_read", True),
        "fetched": sync.get("fetched", 0),
        "inserted": sync.get("inserted", 0),
        "thread_count": len(threads.get("threads", [])),
        "analysis_count": len(analyses.get("items", [])),
        "follow_up_count": len(follow_ups.get("items", [])),
        "sending_performed": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
