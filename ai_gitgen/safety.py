"""Safe-mode masking and diff limiting."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .constants import (
    ADDITIONAL_SECRET_PATTERNS_START_INDEX,
    AWS_ACCESS_KEY_PATTERN,
    EMAIL_PATTERN,
    GIT_DIFF_FILE_PREFIX,
    INITIAL_COUNT,
    MASKED_TOKEN,
    OPENAI_SECRET_PATTERN,
    SECRET_ASSIGNMENT_PATTERN,
    SECRET_ASSIGNMENT_PATTERN_INDEX,
    SECRET_NAME_GROUP,
    SECRET_SEPARATOR_GROUP,
)


SECRET_PATTERNS = [
    re.compile(SECRET_ASSIGNMENT_PATTERN),
    re.compile(OPENAI_SECRET_PATTERN),
    re.compile(EMAIL_PATTERN),
    re.compile(AWS_ACCESS_KEY_PATTERN),
]


@dataclass(frozen=True)
class SafetyResult:
    text: str
    masked_count: int
    omitted_lines: int
    omitted_files: int


def mask_sensitive_text(text: str) -> tuple[str, int]:
    masked = text
    total = INITIAL_COUNT

    def replace_secret_assignment(match: re.Match[str]) -> str:
        nonlocal total
        total += 1
        return f"{match.group(SECRET_NAME_GROUP)}{match.group(SECRET_SEPARATOR_GROUP)}{MASKED_TOKEN}"

    masked = SECRET_PATTERNS[SECRET_ASSIGNMENT_PATTERN_INDEX].sub(replace_secret_assignment, masked)
    for pattern in SECRET_PATTERNS[ADDITIONAL_SECRET_PATTERNS_START_INDEX:]:
        masked, count = pattern.subn(MASKED_TOKEN, masked)
        total += count
    return masked, total


def limit_diff(text: str, max_files: int, max_lines: int) -> tuple[str, int, int]:
    lines = text.splitlines()
    kept: list[str] = []
    seen_files = INITIAL_COUNT
    omitted_files = INITIAL_COUNT
    omitted_lines = INITIAL_COUNT
    include_current_file = True

    for line in lines:
        if line.startswith(GIT_DIFF_FILE_PREFIX):
            seen_files += 1
            include_current_file = seen_files <= max_files
            if not include_current_file:
                omitted_files += COUNT_INCREMENT
                continue
        if not include_current_file:
            omitted_lines += COUNT_INCREMENT
            continue
        if len(kept) < max_lines:
            kept.append(line)
        else:
            omitted_lines += COUNT_INCREMENT

    return "\n".join(kept), omitted_lines, omitted_files


def apply_safe_mode(text: str, enabled: bool, max_files: int, max_lines: int) -> SafetyResult:
    if not enabled:
        return SafetyResult(
            text=text,
            masked_count=INITIAL_COUNT,
            omitted_lines=INITIAL_COUNT,
            omitted_files=INITIAL_COUNT,
        )
    limited, omitted_lines, omitted_files = limit_diff(text, max_files, max_lines)
    masked, masked_count = mask_sensitive_text(limited)
    return SafetyResult(
        text=masked,
        masked_count=masked_count,
        omitted_lines=omitted_lines,
        omitted_files=omitted_files,
    )
