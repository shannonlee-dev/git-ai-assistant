"""Prompt construction, output normalization, and validation."""

from __future__ import annotations

import re
from textwrap import dedent
from typing import Any

from .constants import (
    BULLET_PREFIX,
    COMMIT_OUTPUT_FOOTER,
    COMMIT_OUTPUT_HEADER,
    COMMIT_TITLE_LIMIT,
    COMMAND_COMMIT,
    COMMAND_PR,
    DEFAULT_FALLBACK_TARGET,
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


def build_prompt(mode: str, status: str, diff: str, files: list[str], max_files: int) -> list[dict[str, str]]:
    if mode not in {PROMPT_MODE_COMMIT, PROMPT_MODE_PR}:
        raise ValueError(f"Unsupported prompt mode: {mode}")

    file_list = "\n".join(f"- {name}" for name in files[:max_files]) or "- unknown"
    if mode == COMMAND_COMMIT:
        commit = config["commit"]
        scope_rule = "A scope is required." if commit["scope_required"] else "Do not add a scope unless necessary."
        scope_schema = "(<scope>)" if commit["scope_required"] else "[(<scope>)]"
        output_contract = f'<one-of: {", ".join(commit["prefixes"])}>{scope_schema}: <subject>'
        task = dedent(
            f"""
            ## Role
            You generate Git commit metadata from staged changes.

            ## Source Of Truth
            Use only the supplied changed files, git status, git diff, and team convention.

            ## Output Contract
            Your entire response is the commit title artifact.
            It has exactly one non-empty line and this shape:
            {output_contract}

            ## Team Convention
            - prefixes: {", ".join(commit["prefixes"])}
            - scope rule: {scope_rule}
            - title limit: {commit["subject_max_length"]} characters

            ## Acceptance Gate
            Before responding, verify the artifact is one line, matches the output contract,
            fits the title limit, and summarizes the most important staged change.
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
        output_contract = f"<pr-title>\n\n{schema_sections}{checklist_schema}"
        task = dedent(
            f"""
            ## Role
            You generate Pull Request metadata from staged changes.

            ## Source Of Truth
            Use only the supplied changed files, git status, git diff, and team convention.

            ## Output Contract
            Your entire response is the PR artifact.
            It has a one-line title followed by the required Markdown body:
            {output_contract}

            ## Team Convention
            - required sections: {sections}
            - title limit: {pr["title_max_length"]} characters
            - tone: {pr["tone"]}
            {checklist}

            ## Acceptance Gate
            Before responding, verify the title fits the limit, every required section exists,
            every required section has at least one bullet, and the artifact summarizes the
            most important staged changes.
            """
        ).strip()

    user = dedent(
        f"""
        ## Changed Files
        {file_list}

        ## Git Status Short
        {status}

        ## Git Diff
        {diff}
        """
    ).strip()
    return [
        {
            "role": PROMPT_SYSTEM_ROLE,
            "content": (
                "You produce only the requested Git metadata artifact. "
                "Follow the output contract exactly and use the acceptance gate before responding."
            ),
        },
        {"role": PROMPT_USER_ROLE, "content": f"{task}\n\n{user}"},
    ]


def trim_line(text: str, limit: int) -> str:
    clean = " ".join(text.strip().split())
    return clean if len(clean) <= limit else clean[: limit - TITLE_ELLIPSIS_WIDTH].rstrip() + TITLE_ELLIPSIS


def _strip_label(line: str) -> str:
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


def _is_checklist_bullet(line: str) -> bool:
    return bool(re.match(r"^-\s+\[[ xX]\]\s+", line.strip()))


def _heading_text(line: str) -> str:
    match = re.match(PR_HEADING_PATTERN, line.strip())
    return match.group(PR_HEADING_TEXT_GROUP) if match else ""


def _normalize_pr_heading(line: str, sections: tuple[str, ...]) -> str:
    heading_key = _section_key(_heading_text(line))
    return next((name for name in sections if _section_key(name) == heading_key), "")


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
    candidates = [_strip_label(line) for line in _content_lines(raw)]
    candidates = [line for line in candidates if line and not line.startswith(MARKDOWN_HEADING_PREFIX)]
    title = next((line for line in candidates if _commit_title_matches_config(line, config)), "")
    if not title:
        title = candidates[FIRST_LINE_INDEX] if candidates else ""
    if not title:
        title = fallback_title(FALLBACK_COMMIT_PREFIX, files, COMMIT_TITLE_LIMIT)
    return trim_line(title, COMMIT_TITLE_LIMIT)


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
        title = fallback_title(FALLBACK_PR_PREFIX, files, PR_TITLE_LIMIT)
    title = trim_line(title, PR_TITLE_LIMIT)

    section_bullets: dict[str, list[str]] = {name: [] for name in sections}
    section_positions = {_section_key(section): index for index, section in enumerate(sections)}
    next_section_index = 0
    current = ""
    for line in lines:
        heading_text = _heading_text(line)
        if heading_text:
            if _section_key(heading_text) == "checklist":
                current = ""
                continue
            heading = _normalize_pr_heading(line, sections)
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
        if current and line.strip().startswith(BULLET_PREFIX) and not _is_checklist_bullet(line):
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
    first = lines[FIRST_LINE_INDEX] if lines else ""
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
