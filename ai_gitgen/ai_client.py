"""Small OpenAI-compatible REST client using only the Python standard library."""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .constants import (
    API_ERROR_KEY,
    API_ERROR_MESSAGE_KEY,
    API_PAYLOAD_MAX_TOKENS_KEY,
    API_PAYLOAD_MESSAGES_KEY,
    API_PAYLOAD_MODEL_KEY,
    API_PAYLOAD_TEMPERATURE_KEY,
    API_RESPONSE_CHOICES_KEY,
    API_RESPONSE_CONTENT_KEY,
    API_RESPONSE_MESSAGE_KEY,
    DEFAULT_API_TIMEOUT,
    EMPTY_ERROR_RESPONSE,
    HTTP_AUTHORIZATION_HEADER,
    HTTP_BEARER_PREFIX,
    HTTP_CONTENT_TYPE_HEADER,
    HTTP_ENCODING,
    HTTP_ERROR_ENCODING,
    HTTP_JSON_CONTENT_TYPE,
    HTTP_METHOD_POST,
    HTTP_RETRY_AFTER_HEADER,
    HTTP_STATUS_HINTS,
    MOCK_ERROR_URL_PREFIX,
    MOCK_PR_URL_PREFIX,
    MOCK_URL_PREFIX,
)


class APIError(RuntimeError):
    """Raised when the external AI API request fails."""


HTTP_STATUS_HINTS = {
    400: "요청 형식이 잘못되었습니다. 모델명, temperature, max_tokens 같은 요청 값을 확인하세요.",
    401: "인증에 실패했습니다. AI_API_KEY 값이 올바른지 확인하세요.",
    403: "API 키 권한, 프로젝트 권한, 결제 설정 또는 모델 접근 권한을 확인하세요.",
    404: "API URL 또는 모델명을 찾을 수 없습니다. --api-base-url과 --model 값을 확인하세요.",
    408: "요청 시간이 초과되었습니다. 잠시 후 다시 시도하세요.",
    409: "요청 처리 중 충돌이 발생했습니다. 잠시 후 다시 시도하세요.",
    413: "요청이 너무 큽니다. --max-files 또는 --max-diff-lines 값을 줄여 diff 크기를 낮추세요.",
    415: "요청 Content-Type을 API가 허용하지 않습니다.",
    422: "요청 파라미터를 처리할 수 없습니다. 모델명과 생성 옵션을 확인하세요.",
    429: "요청 제한 또는 할당량을 초과했습니다. 잠시 후 다시 시도하거나 API 쿼터를 확인하세요.",
    500: "AI 제공자 서버 오류입니다. 잠시 후 다시 시도하세요.",
    502: "AI 제공자 게이트웨이 오류입니다. 잠시 후 다시 시도하세요.",
    503: "AI 서비스가 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도하세요.",
    504: "AI 제공자 응답 시간이 초과되었습니다. 잠시 후 다시 시도하세요.",
}

RETRY_AFTER_HEADER = "Retry-After"
ERROR_DETAIL_KEY = "detail"
ERROR_DESCRIPTION_KEY = "error_description"
ERROR_CODE_KEY = "code"
ERROR_STATUS_KEY = "status"


class AIClient:
    def __init__(self, api_key: str, base_url: str, timeout: float = DEFAULT_API_TIMEOUT) -> None:
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
            body = _read_http_error_body(exc)
            raise APIError(_format_error(exc.code, body, exc.headers)) from exc
        except URLError as exc:
            raise APIError(_format_network_error(exc.reason)) from exc
        except TimeoutError as exc:
            raise APIError("네트워크 타임아웃") from exc

        try:
            data: dict[str, Any] = json.loads(raw)
            return str(
                data[API_RESPONSE_CHOICES_KEY][0][API_RESPONSE_MESSAGE_KEY][
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

## What
- Update demo.txt.

## Why
- Improve review context.

## How
- Run the CLI.
"""
        return "feat: add generated summary"


def _read_http_error_body(exc: HTTPError) -> str:
    try:
        return exc.read().decode(HTTP_ENCODING, errors=HTTP_ERROR_ENCODING)
    except OSError:
        return ""


def _format_network_error(reason: Any) -> str:
    if isinstance(reason, TimeoutError):
        return "네트워크 타임아웃"
    return f"네트워크 오류: {reason}. 인터넷 연결, API URL, 프록시 설정을 확인하세요."


def _format_error(status_code: int, body: str, headers: Mapping[str, str] | None = None) -> str:
    message = _extract_error_message(body)
    message = str(message).strip() or EMPTY_ERROR_RESPONSE
    parts = [f"AI API 오류({status_code}): {message}"]
    hint = HTTP_STATUS_HINTS.get(status_code)
    if hint:
        parts.append(f"안내: {hint}")
    retry_after = _get_header(headers, RETRY_AFTER_HEADER)
    if retry_after:
        parts.append(f"{RETRY_AFTER_HEADER}: {retry_after}")
    return " | ".join(parts)


def _get_header(headers: Mapping[str, str] | None, name: str) -> str:
    if not headers:
        return ""
    for key, value in headers.items():
        if key.lower() == name.lower():
            return str(value)
    return ""


def _extract_error_message(body: str) -> str:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return body

    if isinstance(data, dict):
        message = _extract_message_from_mapping(data)
        return message or json.dumps(data, ensure_ascii=False)
    if isinstance(data, list):
        messages = [
            _extract_message_from_mapping(item) if isinstance(item, dict) else str(item)
            for item in data
        ]
        return "; ".join(message for message in messages if message) or json.dumps(data, ensure_ascii=False)
    return str(data)


def _extract_message_from_mapping(data: dict[str, Any]) -> str:
    error = data.get(API_ERROR_KEY)
    if isinstance(error, dict):
        nested_message = _extract_message_from_mapping(error)
        if nested_message:
            return nested_message
    for key in (
        API_ERROR_MESSAGE_KEY,
        ERROR_DETAIL_KEY,
        ERROR_DESCRIPTION_KEY,
        ERROR_CODE_KEY,
        ERROR_STATUS_KEY,
    ):
        message = data.get(key)
        if message:
            return str(message)
    return ""
