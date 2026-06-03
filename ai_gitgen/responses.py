"""AI response normalization, validation, and display formatting."""

from __future__ import annotations

import re

from .constants import (
    BULLET_PREFIX,
    COMMIT_OUTPUT_FOOTER,
    COMMIT_OUTPUT_HEADER,
    DEFAULT_FALLBACK_TARGET,
    DEFAULT_HOW_TO_TEST_BULLET,
    DEFAULT_WHAT_BULLET,
    DEFAULT_WHY_BULLET,
    FALLBACK_COMMIT_PREFIX,
    FALLBACK_PR_PREFIX,
    HEADING_SUFFIX_CHARS,
    MARKDOWN_HEADING_PREFIX,
    MAX_COMMIT_MESSAGE_LINES,
    MAX_FALLBACK_WHAT_FILES,
    PR_BODY_MARKER,
    PR_BULLET_PATTERN,
    PR_HEADING_PATTERN,
    PR_TITLE_MARKER,
    STRIP_LABEL_PATTERN,
    TITLE_ELLIPSIS,
    WHITESPACE_PATTERN,
)
from .types import AIGitgenConfig


def _trim_line(text: str, limit: int) -> str:
    clean = " ".join(text.strip().split())
    return clean if len(clean) <= limit else clean[: limit - len(TITLE_ELLIPSIS)].rstrip() + TITLE_ELLIPSIS

def _strip_label(line: str) -> str:  #쓸데없는 문장 삭제.
    return re.sub(
        STRIP_LABEL_PATTERN,
        "",
        re.sub(r"^[-*]\s+", "", line.strip()),
        flags=re.IGNORECASE,
    ).strip()


def _content_lines(raw: str) -> list[str]:
    lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        lines.append(stripped)
    return lines


def _section_key(text: str) -> str:
    return re.sub(WHITESPACE_PATTERN, " ", text.strip().rstrip(HEADING_SUFFIX_CHARS)).lower()


def _section_kind(section: str) -> str:
    key = _section_key(section)
    if "test" in key or "validat" in key:
        return "test"
    if key in {"what", "why"}:
        return key
    if key in {"how", "how to test"}:
        return "test"
    return ""


def fallback_title(prefix: str, files: list[str], limit: int = 72) -> str:
    target = files[0] if files else DEFAULT_FALLBACK_TARGET
    return _trim_line(f"{prefix}: update {target}", limit)


def _commit_title_matches_config(title: str, config: AIGitgenConfig) -> bool:
    commit = config["commit"]
    prefix_pattern = "|".join(re.escape(prefix) for prefix in commit["prefixes"])
    scope_part = r"\([^)]+\)" if commit["scope_required"] else r"(\([^)]+\))?"
    return bool(re.match(rf"^({prefix_pattern}){scope_part}: .+", title))


def _default_commit_prefix(config: AIGitgenConfig) -> str:
    prefixes = config["commit"]["prefixes"]
    return FALLBACK_COMMIT_PREFIX if FALLBACK_COMMIT_PREFIX in prefixes else prefixes[0]


def normalize_commit(
    raw: str,
    files: list[str],
    config: AIGitgenConfig,
) -> str:
    commit = config["commit"]
    candidates = [_strip_label(line) for line in _content_lines(raw)]
    candidates = [line for line in candidates if line and not line.startswith(MARKDOWN_HEADING_PREFIX)]
    title = next((line for line in candidates if _commit_title_matches_config(line, config)), "")
    if not title:
        title = candidates[0] if candidates else ""
    if not title:
        prefix = _default_commit_prefix(config)
        title = fallback_title(prefix, files, commit["subject_max_length"])
    title = _trim_line(title, commit["subject_max_length"])
    if _commit_title_matches_config(title, config):
        return title
    prefix = _default_commit_prefix(config)
    scope = "(general)" if commit["scope_required"] else ""
    clean_title = re.sub(r"^[a-z]+(\([^)]+\))?:\s+", "", title, flags=re.IGNORECASE)
    return _trim_line(f"{prefix}{scope}: {clean_title}", commit["subject_max_length"])


def normalize_pr(
    raw: str,
    files: list[str],
    config: AIGitgenConfig,
) -> tuple[str, str]:
    pr = config["pr"]
    sections = pr["sections"]
    lines = _content_lines(raw)
    title = ""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(MARKDOWN_HEADING_PREFIX):
            continue
        title = _strip_label(stripped)
        break
    if not title:
        title = fallback_title(FALLBACK_PR_PREFIX, files, pr["title_max_length"])
    title = _trim_line(title, pr["title_max_length"])

    section_bullets: dict[str, list[str]] = {name: [] for name in sections}
    section_positions = {_section_key(section): index for index, section in enumerate(sections)}
    next_section_index = 0
    current = ""
    for line in lines:
        heading_match = re.match(PR_HEADING_PATTERN, line.strip())
        if heading_match:
            heading_text = heading_match.group(1)
            if _section_key(heading_text) == "checklist":
                current = ""
                continue

            heading_key = _section_key(heading_text)
            heading = next((name for name in sections if _section_key(name) == heading_key), "")
            if not heading:
                heading_kind = _section_kind(heading_text)
                if heading_kind:
                    heading = next((name for name in sections if _section_kind(name) == heading_kind), "")
            if heading:
                current = heading
                next_section_index = max(next_section_index, section_positions[_section_key(heading)] + 1)
                continue
            if next_section_index < len(sections):
                current = sections[next_section_index]
                next_section_index += 1
                continue
            current = ""
            continue
        if (
            current
            and line.strip().startswith(BULLET_PREFIX)
            and not re.match(r"^-\s+\[[ xX]\]\s+", line.strip())
        ):
            section_bullets[current].append(line.strip())

    if not section_bullets[PR_SECTION_WHY]:
        section_bullets[PR_SECTION_WHY] = [DEFAULT_WHY_BULLET]
    if not section_bullets[PR_SECTION_WHAT]:
        if files:
            section_bullets[PR_SECTION_WHAT] = [
                f"{BULLET_PREFIX}Update {name}" for name in files[:MAX_FALLBACK_WHAT_FILES]
            ]
        else:
            section_bullets[PR_SECTION_WHAT] = [DEFAULT_WHAT_BULLET]
    if not section_bullets[PR_SECTION_HOW_TO_TEST]:
        section_bullets[PR_SECTION_HOW_TO_TEST] = [DEFAULT_HOW_TO_TEST_BULLET]

    body_parts: list[str] = []
    for section in PR_SECTIONS:
        body_parts.append(f"{MARKDOWN_HEADING_PREFIX} {section}")
        body_parts.extend(section_bullets[section])
        body_parts.append("")
    if pr["checklist"]:
        body_parts.append(f"{MARKDOWN_HEADING_PREFIX} Checklist")
        body_parts.extend(f"{BULLET_PREFIX}[ ] {item}" for item in pr["checklist"])
        body_parts.append("")
    return title, "\n".join(body_parts).strip()


def validate_commit(
    text: str,
    config: AIGitgenConfig,
) -> tuple[bool, list[str]]:
    commit = config["commit"]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first = lines[0] if lines else ""
    errors: list[str] = []
    if not first:
        errors.append("커밋 제목이 없습니다.")
    if len(first) > COMMIT_TITLE_LIMIT:
        errors.append(f"커밋 제목이 {COMMIT_TITLE_LIMIT}자를 초과합니다.")
    if len(lines) > MAX_COMMIT_MESSAGE_LINES:
        errors.append("커밋 메시지는 제목 한 줄만 허용됩니다.")
    if first and not _commit_title_matches_config(first, config):
        errors.append("커밋 제목이 팀 Conventional Commit 규칙과 일치하지 않습니다.")
    return not errors, errors


def validate_pr(
    title: str,
    body: str,
    config: AIGitgenConfig,
) -> tuple[bool, list[str]]:
    pr = config["pr"]
    errors: list[str] = []
    if not title.strip():
        errors.append("PR 제목이 없습니다.")
    if len(title.strip()) > PR_TITLE_LIMIT:
        errors.append(f"PR 제목이 {PR_TITLE_LIMIT}자를 초과합니다.")
    for section in PR_SECTIONS:
        pattern = PR_SECTION_PATTERN_TEMPLATE.format(section=re.escape(section))
        match = re.search(pattern, body)
        if not match:
            errors.append(f"{section} 섹션이 없습니다.")
            continue
        if not re.search(PR_BULLET_PATTERN, match.group(0)):
            errors.append(f"{section} 섹션에 불릿이 없습니다.")
    for item in pr["checklist"]:
        if not re.search(rf"(?m)^-\s+\[[ xX]\]\s+{re.escape(item)}\s*$", body):
            errors.append(f"Checklist 항목이 없습니다: {item}")
    return not errors, errors


def format_commit_output(message: str) -> str:
    return f"{COMMIT_OUTPUT_HEADER}\n{message}\n{COMMIT_OUTPUT_FOOTER}"


def format_pr_output(title: str, body: str) -> str:
    return f"{PR_TITLE_MARKER}\n{title}\n\n{PR_BODY_MARKER}\n{body}"
