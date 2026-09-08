"""DeepSeek 文本模型适配器。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib import request


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    timeout_seconds: float = 60

    @classmethod
    def from_env_file(cls, path: str | Path) -> "DeepSeekConfig":
        values: dict[str, str] = {}
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        api_key = values.get("DEEPSEEK_API_KEY", "")
        if not api_key or api_key == "replace-with-your-api-key":
            raise ValueError("DEEPSEEK_API_KEY is not configured")
        return cls(
            api_key=api_key,
            base_url=values.get("DEEPSEEK_BASE_URL", cls.base_url).rstrip("/"),
            model=values.get("DEEPSEEK_MODEL", cls.model),
            timeout_seconds=float(values.get("DEEPSEEK_TIMEOUT_SECONDS", cls.timeout_seconds)),
        )


class DeepSeekProvider:
    def __init__(
        self,
        config: DeepSeekConfig,
        request: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ):
        self._config = config
        self._request = request or self._send_request

    def generate_json(self, prompt: str) -> dict[str, Any]:
        response = self._request(
            {
                "model": self._config.model,
                "messages": [{"role": "user", "content": prompt}],
                "thinking": {"type": "disabled"},
                "response_format": {"type": "json_object"},
                "stream": False,
            }
        )
        try:
            content = response["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("DeepSeek returned an invalid JSON response") from exc
        if not isinstance(result, dict):
            raise ValueError("DeepSeek JSON response must be an object")
        return result

    def _send_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            f"{self._config.base_url}/chat/completions",
            data=encoded,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(http_request, timeout=self._config.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
