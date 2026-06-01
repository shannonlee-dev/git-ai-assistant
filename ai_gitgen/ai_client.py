"""Small OpenAI-compatible REST client using only the Python standard library."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class APIError(RuntimeError):
    """Raised when the external AI API request fails."""


class AIClient:
    def __init__(self, api_key: str, base_url: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.call_count = 0

    def generate(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        self.call_count += 1
        if self.base_url.startswith("mock://"):
            return self._generate_mock()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        request = Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise APIError(_format_error(exc.code, body)) from exc
        except URLError as exc:
            raise APIError(f"네트워크 오류: {exc.reason}") from exc
        except TimeoutError as exc:
            raise APIError("네트워크 타임아웃") from exc

        try:
            data: dict[str, Any] = json.loads(raw)
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise APIError("AI API 응답 형식을 해석할 수 없습니다.") from exc

    def _generate_mock(self) -> str:
        if self.base_url.startswith("mock://error"):
            raise APIError("AI API 오류(401): mock auth failed")
        if self.base_url.startswith("mock://pr"):
            return """feat: add PR summary

## Why
- Improve review context.

## What
- Update demo.txt.

## How to Test
- Run the CLI.
"""
        return "feat: add generated summary"


def _format_error(status_code: int, body: str) -> str:
    try:
        data = json.loads(body)
        message = data.get("error", {}).get("message") or data.get("message") or body
    except json.JSONDecodeError:
        message = body
    message = str(message).strip() or "empty error response"
    return f"AI API 오류({status_code}): {message}"
