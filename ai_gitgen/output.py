"""Prompt construction, output normalization, and validation."""

from __future__ import annotations

import re
from textwrap import dedent
from typing import Any

from .constants import (
    BULLET_PREFIX,
    COMMIT_OUTPUT_FOOTER,
    COMMIT_OUTPUT_HEADER,
    COMMAND_COMMIT,
    COMMAND_PR,
    DEFAULT_FALLBACK_TARGET,
    DEFAULT_HOW_TO_TEST_BULLET,
    DEFAULT_WHAT_BULLET,
    DEFAULT_WHY_BULLET,
    FALLBACK_COMMIT_PREFIX,
    FALLBACK_PR_PREFIX,
    FIRST_LINE_INDEX,
    FULL_MATCH_GROUP,
    HEADING_SUFFIX_CHARS,
    MARKDOWN_HEADING_PREFIX,
    MAX_COMMIT_MESSAGE_LINES,
    MAX_FALLBACK_WHAT_FILES,
    PR_BODY_MARKER,
    PR_BULLET_PATTERN,
    PR_HEADING_PATTERN,
    PR_HEADING_TEXT_GROUP,
    PR_TITLE_MARKER,
    PROMPT_MODE_COMMIT,
    PROMPT_MODE_PR,
    PROMPT_SYSTEM_ROLE,
    PROMPT_USER_ROLE,
    STRIP_LABEL_PATTERN,
    TITLE_ELLIPSIS,
    TITLE_ELLIPSIS_WIDTH,
    WHITESPACE_PATTERN,
)

AIGitgenConfig = dict[str, Any]


def build_prompt(
    mode: str,
    status: str,
    diff: str,
    files: list[str],
    max_files: int,
    config: AIGitgenConfig,
) -> list[dict[str, str]]:
    if mode not in {PROMPT_MODE_COMMIT, PROMPT_MODE_PR}:
        raise ValueError(f"Unsupported prompt mode: {mode}")

    file_list = "\n".join(f"{BULLET_PREFIX}{name}" for name in files[:max_files]) or f"{BULLET_PREFIX}unknown"
    if mode == COMMAND_COMMIT:
        commit = config["commit"]
        scope_rule = "A scope is required." if commit["scope_required"] else "Do not add a scope unless necessary."
        scope_schema = "(<scope>)" if commit["scope_required"] else "[(<scope>)]"
        schema = dedent(
            f"""
            ```md
            <one-of: {", ".join(commit["prefixes"])}>{scope_schema}: <subject>
            ```
            """
        ).strip()
        task = dedent(
            f"""
            Generate a Git commit message from the supplied git status and git diff.
            Return only one concise title line, with no body or bullet list.
            The title must be {commit["subject_max_length"]} characters or fewer.
            Use Conventional Commits with one of these prefixes: {", ".join(commit["prefixes"])}.
            {scope_rule}
            Use this exact output schema:
            {schema}
            """
        ).strip()
    elif mode == COMMAND_PR:
        pr = config["pr"]
        sections = ", ".join(f"{MARKDOWN_HEADING_PREFIX} {section}" for section in pr["sections"])
        checklist = ""
        if pr["checklist"]:
            checklist = f"Include a final {MARKDOWN_HEADING_PREFIX} Checklist section with these unchecked items: " + ", ".join(
                pr["checklist"]
            )
        schema_sections = "\n\n".join(
            f"{MARKDOWN_HEADING_PREFIX} {section}\n{BULLET_PREFIX}<{section.lower()}-bullet>"
            for section in pr["sections"]
        )
        checklist_schema = ""
        if pr["checklist"]:
            checklist_schema = "\n\n## Checklist\n" + "\n".join(f"- [ ] {item}" for item in pr["checklist"])
        schema = dedent(
            f"""
            ```md
            <pr-title>

            {schema_sections}{checklist_schema}
            ```
            """
        ).strip()
        task = dedent(
            f"""
            Generate a Pull Request draft from the supplied git status and git diff.
            Return a one-line title, then a body with these Markdown sections:
            {sections}. Each required section must include at least one bullet.
            The PR title must be {pr["title_max_length"]} characters or fewer.
            Match this team tone: {pr["tone"]}.
            {checklist}
            Use this exact output schema:
            {schema}
            """
        ).strip()

    user = dedent(
        f"""
        Changed files:
        {file_list}

        git status --short:
        {status}

        git diff:
        {diff}
        """
    ).strip()
    return [
        {"role": PROMPT_SYSTEM_ROLE, "content": "You help developers write accurate Git metadata."},
        {"role": PROMPT_USER_ROLE, "content": f"{task}\n\n{user}"},
    ]


def trim_line(text: str, limit: int) -> str:
    clean = " ".join(text.strip().split())
    return clean if len(clean) <= limit else clean[: limit - TITLE_ELLIPSIS_WIDTH].rstrip() + TITLE_ELLIPSIS


def _strip_label(line: str) -> str:
    return re.sub(
        STRIP_LABEL_PATTERN,
        "",
        line.strip(),
        flags=re.IGNORECASE,
    ).strip()


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


def _normalize_pr_heading(line: str, sections: tuple[str, ...]) -> str:
    match = re.match(PR_HEADING_PATTERN, line.strip())
    if not match:
        return ""
    heading = match.group(PR_HEADING_TEXT_GROUP)
    heading_key = _section_key(heading)
    exact = next((name for name in sections if _section_key(name) == heading_key), "")
    if exact:
        return exact
    heading_kind = _section_kind(heading)
    if not heading_kind:
        return ""
    return next((name for name in sections if _section_kind(name) == heading_kind), "")


def fallback_title(prefix: str, files: list[str], limit: int = 72) -> str:
    target = files[FIRST_LINE_INDEX] if files else DEFAULT_FALLBACK_TARGET
    return trim_line(f"{prefix}: update {target}", limit)


def _commit_title_matches_config(title: str, config: AIGitgenConfig) -> bool:
    commit = config["commit"]
    prefix_pattern = "|".join(re.escape(prefix) for prefix in commit["prefixes"])
    scope_part = r"\([^)]+\)" if commit["scope_required"] else r"(\([^)]+\))?"
    return bool(re.match(rf"^({prefix_pattern}){scope_part}: .+", title))


def _default_commit_prefix(config: AIGitgenConfig) -> str:
    prefixes = config["commit"]["prefixes"]
    return FALLBACK_COMMIT_PREFIX if FALLBACK_COMMIT_PREFIX in prefixes else prefixes[FIRST_LINE_INDEX]


def normalize_commit(
    raw: str,
    files: list[str],
    config: AIGitgenConfig,
) -> str:
    commit = config["commit"]
    title = next((_strip_label(line) for line in raw.splitlines() if line.strip()), "")
    if not title:
        prefix = _default_commit_prefix(config)
        title = fallback_title(prefix, files, commit["subject_max_length"])
    title = trim_line(title, commit["subject_max_length"])
    if _commit_title_matches_config(title, config):
        return title
    prefix = _default_commit_prefix(config)
    scope = "(general)" if commit["scope_required"] else ""
    clean_title = re.sub(r"^[a-z]+(\([^)]+\))?:\s+", "", title, flags=re.IGNORECASE)
    return trim_line(f"{prefix}{scope}: {clean_title}", commit["subject_max_length"])


def normalize_pr(
    raw: str,
    files: list[str],
    config: AIGitgenConfig,
) -> tuple[str, str]:
    pr = config["pr"]
    sections = pr["sections"]
    lines = [line.rstrip() for line in raw.splitlines()]
    title = ""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(MARKDOWN_HEADING_PREFIX):
            continue
        title = _strip_label(stripped)
        break
    if not title:
        title = fallback_title(FALLBACK_PR_PREFIX, files, pr["title_max_length"])
    title = trim_line(title, pr["title_max_length"])

    section_bullets: dict[str, list[str]] = {name: [] for name in sections}
    current = ""
    for line in lines:
        heading = _normalize_pr_heading(line, sections)
        if heading:
            current = heading
            continue
        if current and line.strip().startswith(BULLET_PREFIX):
            section_bullets[current].append(line.strip())

    for section in sections:
        if section_bullets[section]:
            continue
        section_kind = _section_kind(section)
        if section_kind == "why":
            section_bullets[section] = [DEFAULT_WHY_BULLET]
        elif section_kind == "what" and files:
            section_bullets[section] = [f"{BULLET_PREFIX}Update {name}" for name in files[:MAX_FALLBACK_WHAT_FILES]]
        elif section_kind == "test":
            section_bullets[section] = [DEFAULT_HOW_TO_TEST_BULLET]
        else:
            section_bullets[section] = [DEFAULT_WHAT_BULLET]

    body_parts: list[str] = []
    for section in sections:
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
    first = lines[FIRST_LINE_INDEX] if lines else ""
    errors: list[str] = []
    if not first:
        errors.append("커밋 제목이 없습니다.")
    if len(first) > commit["subject_max_length"]:
        errors.append(f"커밋 제목이 {commit['subject_max_length']}자를 초과합니다.")
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
    if len(title.strip()) > pr["title_max_length"]:
        errors.append(f"PR 제목이 {pr['title_max_length']}자를 초과합니다.")
    for section in pr["sections"]:
        pattern = rf"(?ms)^{MARKDOWN_HEADING_PREFIX}\s+{re.escape(section)}\s*$.*?(?=^{MARKDOWN_HEADING_PREFIX}\s+|\Z)"
        match = re.search(pattern, body)
        if not match:
            errors.append(f"{section} 섹션이 없습니다.")
            continue
        if not re.search(PR_BULLET_PATTERN, match.group(FULL_MATCH_GROUP)):
            errors.append(f"{section} 섹션에 불릿이 없습니다.")
    for item in pr["checklist"]:
        if not re.search(rf"(?m)^-\s+\[[ xX]\]\s+{re.escape(item)}\s*$", body):
            errors.append(f"Checklist 항목이 없습니다: {item}")
    return not errors, errors


def format_commit_output(message: str) -> str:
    return f"{COMMIT_OUTPUT_HEADER}\n{message}\n{COMMIT_OUTPUT_FOOTER}"


def format_pr_output(title: str, body: str) -> str:
    return f"{PR_TITLE_MARKER}\n{title}\n\n{PR_BODY_MARKER}\n{body}"
