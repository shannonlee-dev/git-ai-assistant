"""Prompt construction, output normalization, and validation."""

from __future__ import annotations

import re
from textwrap import dedent


PR_SECTIONS = ("Why", "What", "How to Test")
PR_SECTION_ALIASES = {
    "why": "Why",
    "what": "What",
    "how": "How to Test",
    "how to test": "How to Test",
    "test": "How to Test",
    "tests": "How to Test",
    "testing": "How to Test",
    "validation": "How to Test",
}


def build_prompt(mode: str, status: str, diff: str, files: list[str], max_files: int) -> list[dict[str, str]]:
    if mode not in {"commit", "pr"}:
        raise ValueError(f"Unsupported prompt mode: {mode}")

    file_list = "\n".join(f"- {name}" for name in files[:max_files]) or "- unknown"
    if mode == "commit":
        task = dedent(
            """
            Generate a Git commit message from the supplied git status and git diff.
            Return only one concise title line, with no body or bullet list.
            The title must be 72 characters or fewer.
            """
        ).strip()
    elif mode == "pr":
        task = dedent(
            """
            Generate a Pull Request draft from the supplied git status and git diff.
            Return a one-line title, then a body with exactly these Markdown sections:
            ## Why, ## What, ## How to Test. Each section must include at least one bullet.
            The PR title must be 80 characters or fewer.
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
        {"role": "system", "content": "You help developers write accurate Git metadata."},
        {"role": "user", "content": f"{task}\n\n{user}"},
    ]


def trim_line(text: str, limit: int) -> str:
    clean = " ".join(text.strip().split())
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


def _strip_label(line: str) -> str:
    return re.sub(
        r"^(#+\s*)?(-\s*)?(commit message|commit title|pr title|title)\s*[:：-]\s*",
        "",
        line.strip(),
        flags=re.IGNORECASE,
    ).strip()


def _normalize_pr_heading(line: str) -> str:
    match = re.match(r"^##\s+(.+?)\s*$", line.strip())
    if not match:
        return ""
    heading = re.sub(r"\s+", " ", match.group(1).strip().rstrip(":：")).lower()
    return PR_SECTION_ALIASES.get(heading, "")


def fallback_title(prefix: str, files: list[str]) -> str:
    target = files[0] if files else "project"
    return trim_line(f"{prefix}: update {target}", 72 if prefix != "pr" else 80)


def normalize_commit(raw: str, files: list[str]) -> str:
    title = next((_strip_label(line) for line in raw.splitlines() if line.strip()), "")
    if not title:
        title = fallback_title("chore", files)
    return trim_line(title, 72)


def normalize_pr(raw: str, files: list[str]) -> tuple[str, str]:
    lines = [line.rstrip() for line in raw.splitlines()]
    title = ""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("##"):
            continue
        title = _strip_label(stripped)
        break
    if not title:
        title = fallback_title("chore", files)
    title = trim_line(title, 80)

    section_bullets: dict[str, list[str]] = {name: [] for name in PR_SECTIONS}
    current = ""
    for line in lines:
        heading = _normalize_pr_heading(line)
        if heading:
            current = heading
            continue
        if current and line.strip().startswith("- "):
            section_bullets[current].append(line.strip())

    if not section_bullets["Why"]:
        section_bullets["Why"] = ["- Capture the reason for the current Git changes."]
    if not section_bullets["What"]:
        if files:
            section_bullets["What"] = [f"- Update {name}" for name in files[:3]]
        else:
            section_bullets["What"] = ["- Summarize the implementation changes."]
    if not section_bullets["How to Test"]:
        section_bullets["How to Test"] = ["- Run the project checks for this change."]

    body_parts: list[str] = []
    for section in PR_SECTIONS:
        body_parts.append(f"## {section}")
        body_parts.extend(section_bullets[section])
        body_parts.append("")
    return title, "\n".join(body_parts).strip()


def validate_commit(text: str) -> tuple[bool, list[str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first = lines[0] if lines else ""
    errors: list[str] = []
    if not first:
        errors.append("커밋 제목이 없습니다.")
    if len(first) > 72:
        errors.append("커밋 제목이 72자를 초과합니다.")
    if len(lines) > 1:
        errors.append("커밋 메시지는 제목 한 줄만 허용됩니다.")
    return not errors, errors


def validate_pr(title: str, body: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not title.strip():
        errors.append("PR 제목이 없습니다.")
    if len(title.strip()) > 80:
        errors.append("PR 제목이 80자를 초과합니다.")
    for section in PR_SECTIONS:
        pattern = rf"(?ms)^##\s+{re.escape(section)}\s*$.*?(?=^##\s+|\Z)"
        match = re.search(pattern, body)
        if not match:
            errors.append(f"{section} 섹션이 없습니다.")
            continue
        if not re.search(r"(?m)^-\s+\S+", match.group(0)):
            errors.append(f"{section} 섹션에 불릿이 없습니다.")
    return not errors, errors


def format_commit_output(message: str) -> str:
    return f"--- Commit Message ---\n{message}\n----------------------"


def format_pr_output(title: str, body: str) -> str:
    return f"--- PR Title ---\n{title}\n\n--- PR Body ---\n{body}"
