"""Prompt construction, output normalization, and validation."""

from __future__ import annotations

import re
from textwrap import dedent

from .constants import (
    BULLET_PREFIX,
    COMMIT_OUTPUT_FOOTER,
    COMMIT_OUTPUT_HEADER,
    COMMIT_TITLE_LIMIT,
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
    MAX_FALLBACK_WHAT_FILES,
    MAX_COMMIT_MESSAGE_LINES,
    PR_BULLET_PATTERN,
    PR_BODY_MARKER,
    PR_HEADING_TEXT_GROUP,
    PR_HEADING_PATTERN,
    PR_SECTION_ALIASES,
    PR_SECTION_HOW_TO_TEST,
    PR_SECTION_PATTERN_TEMPLATE,
    PR_SECTION_WHAT,
    PR_SECTION_WHY,
    PR_SECTIONS,
    PR_TITLE_LIMIT,
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


def build_prompt(mode: str, status: str, diff: str, files: list[str], max_files: int) -> list[dict[str, str]]:
    if mode not in {PROMPT_MODE_COMMIT, PROMPT_MODE_PR}:
        raise ValueError(f"Unsupported prompt mode: {mode}")

    file_list = "\n".join(f"- {name}" for name in files[:max_files]) or "- unknown"
    if mode == COMMAND_COMMIT:
        task = dedent(
            f"""
            ## Role
            You generate Git commit metadata from staged changes.

            ## Source Of Truth
            Use only the supplied changed files, git status, git diff, and team convention.

            ## Output Contract
            Your entire response is the commit title artifact.
            It has exactly one non-empty line and this shape:
            <commit-title>

            ## Team Convention
            - title limit: {COMMIT_TITLE_LIMIT} characters

            ## Acceptance Gate
            Before responding, verify the artifact is one line, matches the output contract,
            fits the title limit, and summarizes the most important staged change.
            """
        ).strip()
    elif mode == COMMAND_PR:
        task = dedent(
            f"""
            ## Role
            You generate Pull Request metadata from staged changes.

            ## Source Of Truth
            Use only the supplied changed files, git status, git diff, and team convention.

            ## Output Contract
            Your entire response is the PR artifact.
            It has a one-line title followed by the required Markdown body:
            <pr-title>

            ## {PR_SECTION_WHY}
            - <why-bullet>

            ## {PR_SECTION_WHAT}
            - <what-bullet>

            ## {PR_SECTION_HOW_TO_TEST}
            - <test-bullet>

            ## Team Convention
            - required sections: ## {PR_SECTION_WHY}, ## {PR_SECTION_WHAT}, ## {PR_SECTION_HOW_TO_TEST}
            - title limit: {PR_TITLE_LIMIT} characters

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
        line.strip(),
        flags=re.IGNORECASE,
    ).strip()


def _normalize_pr_heading(line: str) -> str:
    match = re.match(PR_HEADING_PATTERN, line.strip())
    if not match:
        return ""
    heading = re.sub(
        WHITESPACE_PATTERN,
        " ",
        match.group(PR_HEADING_TEXT_GROUP).strip().rstrip(HEADING_SUFFIX_CHARS),
    ).lower()
    return PR_SECTION_ALIASES.get(heading, "")


def fallback_title(prefix: str, files: list[str], limit: int) -> str:
    target = files[FIRST_LINE_INDEX] if files else DEFAULT_FALLBACK_TARGET
    return trim_line(f"{prefix}: update {target}", limit)


def normalize_commit(raw: str, files: list[str]) -> str:
    title = next((_strip_label(line) for line in raw.splitlines() if line.strip()), "")
    if not title:
        title = fallback_title(FALLBACK_COMMIT_PREFIX, files, COMMIT_TITLE_LIMIT)
    return trim_line(title, COMMIT_TITLE_LIMIT)


def normalize_pr(raw: str, files: list[str]) -> tuple[str, str]:
    lines = [line.rstrip() for line in raw.splitlines()]
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

    section_bullets: dict[str, list[str]] = {name: [] for name in PR_SECTIONS}
    current = ""
    for line in lines:
        heading = _normalize_pr_heading(line)
        if heading:
            current = heading
            continue
        if current and line.strip().startswith(BULLET_PREFIX):
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
    return title, "\n".join(body_parts).strip()


def validate_commit(text: str) -> tuple[bool, list[str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first = lines[FIRST_LINE_INDEX] if lines else ""
    errors: list[str] = []
    if not first:
        errors.append("커밋 제목이 없습니다.")
    if len(first) > COMMIT_TITLE_LIMIT:
        errors.append(f"커밋 제목이 {COMMIT_TITLE_LIMIT}자를 초과합니다.")
    if len(lines) > MAX_COMMIT_MESSAGE_LINES:
        errors.append("커밋 메시지는 제목 한 줄만 허용됩니다.")
    return not errors, errors


def validate_pr(title: str, body: str) -> tuple[bool, list[str]]:
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
    return not errors, errors


def format_commit_output(message: str) -> str:
    return f"{COMMIT_OUTPUT_HEADER}\n{message}\n{COMMIT_OUTPUT_FOOTER}"


def format_pr_output(title: str, body: str) -> str:
    return f"{PR_TITLE_MARKER}\n{title}\n\n{PR_BODY_MARKER}\n{body}"
