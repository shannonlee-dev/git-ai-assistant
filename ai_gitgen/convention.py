"""Team convention loading for generated Git metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_FILE = ".ai-gitgen.yml"


@dataclass(frozen=True)
class CommitConvention:
    prefixes: tuple[str, ...] = ("feat", "fix", "docs", "test", "chore")
    scope_required: bool = False
    subject_max_length: int = 72


@dataclass(frozen=True)
class BranchConvention:
    patterns: tuple[str, ...] = ("feature/<name>-<topic>",)


@dataclass(frozen=True)
class PRConvention:
    sections: tuple[str, ...] = ("What", "Why", "How")
    tone: str = "concise, factual, and review-focused"
    issue_reference: str = "Include Closes #<issue_number> or Fixes #<issue_number>."
    checklist: tuple[str, ...] = (
        "Latest main reflected before merge",
        "Conflicts resolved",
        "Validation or test result recorded",
        "Review comments resolved",
    )


@dataclass(frozen=True)
class TeamConvention:
    commit: CommitConvention = CommitConvention()
    branch: BranchConvention = BranchConvention()
    pr: PRConvention = PRConvention()


def load_convention(root: Path, config_path: str | None = None) -> TeamConvention:
    path = Path(config_path) if config_path else root / DEFAULT_CONFIG_FILE
    if not path.is_absolute():
        path = root / path
    if not path.exists():
        return TeamConvention()

    data = _parse_simple_yaml(path.read_text(encoding="utf-8"))
    commit_data = data.get("commit", {})
    branch_data = data.get("branch", {})
    pr_data = data.get("pr", {})
    return TeamConvention(
        commit=CommitConvention(
            prefixes=_as_tuple(commit_data.get("prefixes"), CommitConvention.prefixes),
            scope_required=bool(commit_data.get("scope_required", CommitConvention.scope_required)),
            subject_max_length=int(commit_data.get("subject_max_length", CommitConvention.subject_max_length)),
        ),
        branch=BranchConvention(
            patterns=_as_tuple(branch_data.get("patterns"), BranchConvention.patterns),
        ),
        pr=PRConvention(
            sections=_as_tuple(pr_data.get("sections"), PRConvention.sections),
            tone=str(pr_data.get("tone", PRConvention.tone)),
            issue_reference=str(pr_data.get("issue_reference", PRConvention.issue_reference)),
            checklist=_as_tuple(pr_data.get("checklist"), PRConvention.checklist),
        ),
    )


def describe_convention(convention: TeamConvention) -> str:
    scope_rule = "required" if convention.commit.scope_required else "optional"
    lines = [
        "Team convention:",
        f"- commit prefixes: {', '.join(convention.commit.prefixes)}",
        f"- commit scope: {scope_rule}",
        f"- commit title max length: {convention.commit.subject_max_length}",
        f"- branch patterns: {', '.join(convention.branch.patterns)}",
        f"- PR sections: {', '.join(convention.pr.sections)}",
        f"- PR tone: {convention.pr.tone}",
        f"- PR issue reference: {convention.pr.issue_reference}",
    ]
    if convention.pr.checklist:
        lines.append(f"- PR checklist: {', '.join(convention.pr.checklist)}")
    return "\n".join(lines)


def _as_tuple(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    if isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        items = [part.strip() for part in str(value).split(",")]
    return tuple(item for item in items if item) or default


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
    for index, char in enumerate(line):
        if char in {"'", '"'}:
            quote = "" if quote == char else char
        elif char == "#" and not quote:
            return line[:index]
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
