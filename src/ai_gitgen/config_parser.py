"""기존 팀 규칙의 제한된 YAML 문법을 파싱한다."""

from __future__ import annotations

from typing import Any


def parse_rules(text: str) -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = {}
    section = ""
    list_key = ""

    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue

        if not line.startswith((" ", "\t")):
            key = line.strip()
            if key.endswith(":"):
                section = key[:-1].strip()
                data.setdefault(section, {})
                list_key = ""
            continue

        if not section:
            continue

        stripped = line.strip()
        if stripped.startswith("- ") and list_key:
            data[section].setdefault(list_key, []).append(
                _parse_scalar(stripped[2:].strip())
            )
            continue

        if ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            data[section][key] = _parse_scalar(value)
            list_key = ""
        else:
            data[section][key] = []
            list_key = key

    return data


def _strip_comment(line: str) -> str:
    quote = ""
    for char_index, char in enumerate(line):
        if char in {"'", '"'}:
            quote = "" if quote == char else char
        elif char == "#" and not quote:
            return line[:char_index]
    return line


def _parse_scalar(value: str) -> Any:
    cleaned = value.strip().strip('"').strip("'")
    if cleaned.lower() in {"true", "false"}:
        return cleaned.lower() == "true"
    if cleaned.startswith("[") and cleaned.endswith("]"):
        inner = cleaned[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    try:
        return int(cleaned)
    except ValueError:
        return cleaned
