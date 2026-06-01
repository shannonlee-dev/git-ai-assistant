"""Prompt construction, output normalization, and validation."""

from __future__ import annotations

import re
from textwrap import dedent

from .convention import TeamConvention

DEFAULT_CONVENTION = TeamConvention()
PR_SECTION_ALIASES = {
    "why": "why",
    "what": "what",
    "how": "test",
    "how to test": "test",
    "test": "test",
    "tests": "test",
    "testing": "test",
    "validation": "test",
}


def build_prompt(
    mode: str,
    status: str,
    diff: str,
    files: list[str],
    max_files: int,
    convention: TeamConvention = DEFAULT_CONVENTION,
) -> list[dict[str, str]]:
    if mode not in {"commit", "pr"}:
        raise ValueError(f"Unsupported prompt mode: {mode}")

    file_list = "\n".join(f"- {name}" for name in files[:max_files]) or "- unknown"
    if mode == "commit":
        scope_rule = "A scope is required." if convention.commit.scope_required else "Do not add a scope unless necessary."
        task = dedent(
            f"""
            Generate a Git commit message from the supplied git status and git diff.
            Return only one concise title line, with no body or bullet list.
            The title must be {convention.commit.subject_max_length} characters or fewer.
            Use Conventional Commits with one of these prefixes: {", ".join(convention.commit.prefixes)}.
            {scope_rule}
            """
        ).strip()
    elif mode == "pr":
        sections = ", ".join(f"## {section}" for section in convention.pr.sections)
        branch_patterns = ", ".join(convention.branch.patterns)
        checklist = ""
        if convention.pr.checklist:
            checklist = "Include a final ## Checklist section with these unchecked items: " + ", ".join(
                convention.pr.checklist
            )
        task = dedent(
            f"""
            Generate a Pull Request draft from the supplied git status and git diff.
            Return a one-line title, then a body with exactly these Markdown sections:
            {sections}. Each section must include at least one bullet.
            The PR title must be 80 characters or fewer.
            Match this team tone: {convention.pr.tone}.
            Team branch naming convention: {branch_patterns}.
            {convention.pr.issue_reference}
            {checklist}
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


def _section_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().rstrip(":：")).lower()


def _section_kind(section: str) -> str:
    key = _section_key(section)
    if key in {"why", "what"}:
        return key
    if key in {"how", "how to test"} or "test" in key or "validat" in key:
        return "test"
    return PR_SECTION_ALIASES.get(key, "")


def _normalize_pr_heading(line: str, sections: tuple[str, ...]) -> str:
    match = re.match(r"^##\s+(.+?)\s*$", line.strip())
    if not match:
        return ""
    heading = match.group(1)
    heading_key = _section_key(heading)
    exact = next((name for name in sections if _section_key(name) == heading_key), "")
    if exact:
        return exact
    heading_kind = _section_kind(heading)
    if not heading_kind:
        return ""
    return next((name for name in sections if _section_kind(name) == heading_kind), "")


def fallback_title(prefix: str, files: list[str], limit: int = 72) -> str:
    target = files[0] if files else "project"
    return trim_line(f"{prefix}: update {target}", limit)


def normalize_commit(
    raw: str,
    files: list[str],
    convention: TeamConvention = DEFAULT_CONVENTION,
) -> str:
    title = next((_strip_label(line) for line in raw.splitlines() if line.strip()), "")
    if not title:
        prefix = "chore" if "chore" in convention.commit.prefixes else convention.commit.prefixes[0]
        title = fallback_title(prefix, files, convention.commit.subject_max_length)
    return trim_line(title, convention.commit.subject_max_length)


def normalize_pr(
    raw: str,
    files: list[str],
    convention: TeamConvention = DEFAULT_CONVENTION,
) -> tuple[str, str]:
    sections = convention.pr.sections
    lines = [line.rstrip() for line in raw.splitlines()]
    title = ""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("##"):
            continue
        title = _strip_label(stripped)
        break
    if not title:
        title = fallback_title("chore", files, 80)
    title = trim_line(title, 80)

    section_bullets: dict[str, list[str]] = {name: [] for name in sections}
    current = ""
    for line in lines:
        heading = _normalize_pr_heading(line, sections)
        if heading:
            current = heading
            continue
        if current and line.strip().startswith("- "):
            section_bullets[current].append(line.strip())

    for section in sections:
        if section_bullets[section]:
            continue
        section_kind = _section_kind(section)
        if section_kind == "why":
            section_bullets[section] = ["- Capture the reason for the current Git changes."]
        elif section_kind == "what" and files:
            section_bullets[section] = [f"- Update {name}" for name in files[:3]]
        elif section_kind == "test":
            section_bullets[section] = ["- Run the project checks for this change."]
        else:
            section_bullets[section] = ["- Summarize the relevant change."]

    body_parts: list[str] = []
    for section in sections:
        body_parts.append(f"## {section}")
        body_parts.extend(section_bullets[section])
        body_parts.append("")
    if convention.pr.issue_reference and not re.search(r"\b(Closes|Fixes)\s+#(\d+|<issue_number>)", raw):
        body_parts.append(convention.pr.issue_reference)
        body_parts.append("")
    if convention.pr.checklist:
        body_parts.append("## Checklist")
        body_parts.extend(f"- [ ] {item}" for item in convention.pr.checklist)
        body_parts.append("")
    return title, "\n".join(body_parts).strip()


def validate_commit(
    text: str,
    convention: TeamConvention = DEFAULT_CONVENTION,
) -> tuple[bool, list[str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first = lines[0] if lines else ""
    errors: list[str] = []
    if not first:
        errors.append("커밋 제목이 없습니다.")
    if len(first) > convention.commit.subject_max_length:
        errors.append(f"커밋 제목이 {convention.commit.subject_max_length}자를 초과합니다.")
    if len(lines) > 1:
        errors.append("커밋 메시지는 제목 한 줄만 허용됩니다.")
    if first:
        prefix_pattern = "|".join(re.escape(prefix) for prefix in convention.commit.prefixes)
        scope_part = r"\([^)]+\)" if convention.commit.scope_required else r"(\([^)]+\))?"
        if not re.match(rf"^({prefix_pattern}){scope_part}: .+", first):
            errors.append("커밋 제목이 팀 Conventional Commit 규칙과 일치하지 않습니다.")
    return not errors, errors


def validate_pr(
    title: str,
    body: str,
    convention: TeamConvention = DEFAULT_CONVENTION,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not title.strip():
        errors.append("PR 제목이 없습니다.")
    if len(title.strip()) > 80:
        errors.append("PR 제목이 80자를 초과합니다.")
    for section in convention.pr.sections:
        pattern = rf"(?ms)^##\s+{re.escape(section)}\s*$.*?(?=^##\s+|\Z)"
        match = re.search(pattern, body)
        if not match:
            errors.append(f"{section} 섹션이 없습니다.")
            continue
        if not re.search(r"(?m)^-\s+\S+", match.group(0)):
            errors.append(f"{section} 섹션에 불릿이 없습니다.")
    if convention.pr.issue_reference and not re.search(r"\b(Closes|Fixes)\s+#(\d+|<issue_number>)", body):
        errors.append("PR 본문에 Closes 또는 Fixes 이슈 참조가 없습니다.")
    for item in convention.pr.checklist:
        if not re.search(rf"(?m)^-\s+\[[ xX]\]\s+{re.escape(item)}\s*$", body):
            errors.append(f"Checklist 항목이 없습니다: {item}")
    return not errors, errors


def format_commit_output(message: str) -> str:
    return f"--- Commit Message ---\n{message}\n----------------------"


def format_pr_output(title: str, body: str) -> str:
    return f"--- PR Title ---\n{title}\n\n--- PR Body ---\n{body}"
