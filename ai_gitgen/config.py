"""Configuration loading and validation for ai-gitgen."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import DEFAULT_CONFIG_FILE
from .types import AIGitgenConfig


class ConfigError(ValueError):
    """Raised when .ai-gitgen.yml cannot drive generation safely."""


def load_ai_gitgen_config(root: Path, config_path: str = DEFAULT_CONFIG_FILE) -> AIGitgenConfig:
    path = resolve_config_path(root, config_path)
    if not path.exists():
        raise ConfigError(f"{config_path} 파일이 필요합니다.")

    data = _parse_simple_yaml(path.read_text(encoding="utf-8"))
    config: AIGitgenConfig = {
        "commit": {
            "prefixes": _as_tuple(_config_value(data, "commit.prefixes")),
            "scope_required": _as_bool(_config_value(data, "commit.scope_required")),
            "subject_max_length": _as_int(_config_value(data, "commit.subject_max_length")),
        },
        "pr": {
            "sections": _as_tuple(_config_value(data, "pr.sections")),
            "tone": str(_config_value(data, "pr.tone")),
            "title_max_length": _as_int(_config_value(data, "pr.title_max_length")),
            "checklist": _as_tuple(_config_value(data, "pr.checklist")),
        },
    }
    validate_config(config)
    return config


def resolve_config_path(root: Path, config_path: str = DEFAULT_CONFIG_FILE) -> Path:
    path = Path(config_path)
    if path.is_absolute():
        return path

    repo_path = root / path
    if repo_path.exists():
        return repo_path

    tool_path = Path(__file__).resolve().parent.parent / path
    if config_path == DEFAULT_CONFIG_FILE and tool_path.exists():
        return tool_path

    return repo_path


def validate_config(config: AIGitgenConfig) -> None:
    commit = config["commit"]
    pr = config["pr"]
    if not commit["prefixes"]:
        raise ConfigError("commit.prefixes must include at least one prefix.")
    invalid_prefixes = [prefix for prefix in commit["prefixes"] if not prefix.islower() or " " in prefix]
    if invalid_prefixes:
        raise ConfigError("commit.prefixes must be lowercase words without spaces.")
    if commit["subject_max_length"] < 10:
        raise ConfigError("commit.subject_max_length must be at least 10.")
    if not pr["sections"]:
        raise ConfigError("pr.sections must include at least one section.")
    if pr["title_max_length"] < 10:
        raise ConfigError("pr.title_max_length must be at least 10.")
    section_kinds: set[str] = set()
    for section in pr["sections"]:
        key = " ".join(section.strip().lower().split())
        if key in {"what", "why"}:
            section_kinds.add(key)
        elif key in {"how", "how to test", "test", "tests", "testing", "validation"}:
            section_kinds.add("how")
        else:
            section_kinds.add(key)
    for required in ("what", "why", "how"):
        if required not in section_kinds:
            raise ConfigError("pr.sections must include What, Why, and How.")


def describe_config(config: AIGitgenConfig) -> str:
    commit = config["commit"]
    pr = config["pr"]
    scope_rule = "required" if commit["scope_required"] else "optional"
    lines = [
        "Team convention from .ai-gitgen.yml:",
        f"- commit prefixes: {', '.join(commit['prefixes'])}",
        f"- commit scope: {scope_rule}",
        f"- commit title max length: {commit['subject_max_length']}",
        f"- PR title max length: {pr['title_max_length']}",
        f"- PR sections: {', '.join(pr['sections'])}",
        f"- PR tone: {pr['tone']}",
    ]
    if pr["checklist"]:
        lines.append(f"- PR checklist: {', '.join(pr['checklist'])}")
    return "\n".join(lines)


def _config_value(data: dict[str, dict[str, Any]], key: str) -> Any:
    section_name, value_name = key.split(".", 1)
    section = data.get(section_name)
    if not section:
        raise ConfigError(f"{section_name} section is required.")
    value = section.get(value_name)
    if value in (None, "", []):
        raise ConfigError(f"{key} is required.")
    return value


def _as_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        items = [part.strip() for part in str(value).split(",")]
    return tuple(item for item in items if item)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    cleaned = str(value).strip().lower()
    if cleaned in {"true", "yes", "1"}:
        return True
    if cleaned in {"false", "no", "0"}:
        return False
    raise ConfigError("commit.scope_required must be true or false.")


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError("commit.subject_max_length must be an integer.") from exc


def _parse_simple_yaml(text: str) -> dict[str, dict[str, Any]]:
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
            data[section].setdefault(list_key, []).append(_parse_scalar(stripped[2:].strip()))
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
