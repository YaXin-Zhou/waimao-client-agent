"""Launch the packaged local API and frontend in the default browser."""

from __future__ import annotations

import os
import socket
import shutil
import sys
import threading
import webbrowser
from functools import partial
from http.client import HTTPConnection
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", ROOT))
(ROOT / "data" / "runtime").mkdir(parents=True, exist_ok=True)
(ROOT / "data" / "exports").mkdir(parents=True, exist_ok=True)
if getattr(sys, "frozen", False):
    config_dir = ROOT / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    env_file = config_dir / ".env"
    env_example = RESOURCE_ROOT / "config" / ".env.example"
    if not env_file.exists() and env_example.exists():
        shutil.copyfile(env_example, env_file)
import scripts.serve_api as serve_api


HOST = os.environ.get("WAIMAO_API_HOST", "127.0.0.1")


def available_port(preferred: int) -> int:
    for port in range(preferred, preferred + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((HOST, port))
                return port
            except OSError:
                continue
    raise OSError(f"no available local port near {preferred}")


API_PORT = available_port(int(os.environ.get("WAIMAO_API_PORT", "8002")))
WEB_PORT = available_port(int(os.environ.get("WAIMAO_WEB_PORT", "5174")))
if API_PORT == WEB_PORT:
    WEB_PORT = available_port(WEB_PORT + 1)


class AppHandler(SimpleHTTPRequestHandler):
    """Serve the built frontend and proxy relative API requests locally."""

    def _proxy_api(self) -> None:
        parsed = urlsplit(self.path)
        body = None
        if self.command in {"POST", "PATCH"}:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else None
        connection = HTTPConnection(HOST, API_PORT, timeout=30)
        try:
            connection.request(
                self.command,
                parsed.path + (f"?{parsed.query}" if parsed.query else ""),
                body=body,
                headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
            )
            response = connection.getresponse()
            payload = response.read()
            self.send_response(response.status)
            self.send_header("Content-Type", response.getheader("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        finally:
            connection.close()

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self._proxy_api()
        else:
            super().do_GET()

    def do_POST(self) -> None:
        self._proxy_api()

    def do_PATCH(self) -> None:
        self._proxy_api()


def main() -> None:
    api_server = ThreadingHTTPServer((HOST, API_PORT), serve_api.Handler)
    web_handler = partial(AppHandler, directory=str(RESOURCE_ROOT / "dist"))
    web_server = ThreadingHTTPServer((HOST, WEB_PORT), web_handler)
    threading.Thread(target=api_server.serve_forever, daemon=True).start()
    threading.Thread(target=web_server.serve_forever, daemon=True).start()
    webbrowser.open(f"http://{HOST}:{WEB_PORT}/")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        web_server.shutdown()
        api_server.shutdown()


if __name__ == "__main__":
    main()
