"""Small OpenAI-compatible REST client using only the Python standard library."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .constants import (
    API_ERROR_KEY,
    API_ERROR_MESSAGE_KEY,
    API_CALL_INCREMENT,
    API_PAYLOAD_MAX_TOKENS_KEY,
    API_PAYLOAD_MESSAGES_KEY,
    API_PAYLOAD_MODEL_KEY,
    API_PAYLOAD_TEMPERATURE_KEY,
    API_RESPONSE_CHOICES_KEY,
    API_RESPONSE_CONTENT_KEY,
    API_RESPONSE_MESSAGE_KEY,
    DEFAULT_API_TIMEOUT,
    EMPTY_ERROR_RESPONSE,
    FIRST_API_RESPONSE_CHOICE_INDEX,
    HTTP_AUTHORIZATION_HEADER,
    HTTP_BEARER_PREFIX,
    HTTP_CONTENT_TYPE_HEADER,
    HTTP_ENCODING,
    HTTP_ERROR_ENCODING,
    HTTP_JSON_CONTENT_TYPE,
    HTTP_METHOD_POST,
    INITIAL_API_CALL_COUNT,
    MOCK_ERROR_URL_PREFIX,
    MOCK_PR_URL_PREFIX,
    MOCK_URL_PREFIX,
)


class APIError(RuntimeError):
    """Raised when the external AI API request fails."""


class AIClient:
    def __init__(self, api_key: str, base_url: str, timeout: float = DEFAULT_API_TIMEOUT) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.call_count = INITIAL_API_CALL_COUNT

    def generate(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        self.call_count += API_CALL_INCREMENT
        if self.base_url.startswith(MOCK_URL_PREFIX):
            return self._generate_mock()
        payload = {
            API_PAYLOAD_MODEL_KEY: model,
            API_PAYLOAD_MESSAGES_KEY: messages,
            API_PAYLOAD_TEMPERATURE_KEY: temperature,
            API_PAYLOAD_MAX_TOKENS_KEY: max_tokens,
        }
        request = Request(
            self.base_url,
            data=json.dumps(payload).encode(HTTP_ENCODING),
            headers={
                HTTP_AUTHORIZATION_HEADER: f"{HTTP_BEARER_PREFIX} {self.api_key}",
                HTTP_CONTENT_TYPE_HEADER: HTTP_JSON_CONTENT_TYPE,
            },
            method=HTTP_METHOD_POST,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode(HTTP_ENCODING)
        except HTTPError as exc:
            body = exc.read().decode(HTTP_ENCODING, errors=HTTP_ERROR_ENCODING)
            raise APIError(_format_error(exc.code, body)) from exc
        except URLError as exc:
            raise APIError(f"네트워크 오류: {exc.reason}") from exc
        except TimeoutError as exc:
            raise APIError("네트워크 타임아웃") from exc

        try:
            data: dict[str, Any] = json.loads(raw)
            return str(
                data[API_RESPONSE_CHOICES_KEY][FIRST_API_RESPONSE_CHOICE_INDEX][API_RESPONSE_MESSAGE_KEY][
                    API_RESPONSE_CONTENT_KEY
                ]
            ).strip()
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise APIError("AI API 응답 형식을 해석할 수 없습니다.") from exc

    def _generate_mock(self) -> str:
        if self.base_url.startswith(MOCK_ERROR_URL_PREFIX):
            raise APIError("AI API 오류(401): mock auth failed")
        if self.base_url.startswith(MOCK_PR_URL_PREFIX):
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
        message = (
            data.get(API_ERROR_KEY, {}).get(API_ERROR_MESSAGE_KEY)
            or data.get(API_ERROR_MESSAGE_KEY)
            or body
        )
    except json.JSONDecodeError:
        message = body
    message = str(message).strip() or EMPTY_ERROR_RESPONSE
    return f"AI API 오류({status_code}): {message}"
