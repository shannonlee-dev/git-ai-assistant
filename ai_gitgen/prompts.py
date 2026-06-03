"""Prompt construction for AI Git metadata generation."""

from __future__ import annotations

from textwrap import dedent

from .constants import (
    BULLET_PREFIX,
    COMMAND_COMMIT,
    COMMAND_PR,
    MARKDOWN_HEADING_PREFIX,
    PROMPT_SYSTEM_ROLE,
    PROMPT_USER_ROLE,
)
from .types import AIGitgenConfig


def build_prompt(
    mode: str,
    status: str,
    diff: str,
    files: list[str],
    config: AIGitgenConfig,
) -> list[dict[str, str]]:
    if mode not in {COMMAND_COMMIT, COMMAND_PR}:
        raise ValueError(f"Unsupported prompt mode: {mode}")

    file_list = "\n".join(f"{BULLET_PREFIX}{name}" for name in files) or f"{BULLET_PREFIX}unknown"
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
