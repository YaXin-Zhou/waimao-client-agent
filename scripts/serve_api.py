"""启动本地 SQLite HTTP API。"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.infrastructure.sqlite_repositories import (
    SQLiteEmailDraftRepository,
    SQLiteLeadRepository,
    SQLiteResearchRepository,
    SQLiteTaskRepository,
)
from src.interfaces.http_api import ApiApplication


DATABASE = ROOT / "data" / "runtime" / "acquisition.db"
application = ApiApplication(
    SQLiteTaskRepository(DATABASE),
    SQLiteLeadRepository(DATABASE),
    SQLiteResearchRepository(DATABASE),
    SQLiteEmailDraftRepository(DATABASE),
)


class Handler(BaseHTTPRequestHandler):
    def _respond(self, status, payload):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        status, payload = application.handle("GET", self.path)
        self._respond(status, payload)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        status, payload = application.handle("POST", self.path, body)
        self._respond(status, payload)

    def log_message(self, *_args):
        return


if __name__ == "__main__":
    port = int(os.environ.get("WAIMAO_API_PORT", "8001"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
