"""팀 규칙의 명시적인 데이터 계약."""

from __future__ import annotations

from typing import TypedDict


class CommitConfig(TypedDict):
    prefixes: tuple[str, ...]
    scope_required: bool
    subject_max_length: int


class PullRequestConfig(TypedDict):
    sections: tuple[str, ...]
    tone: str
    title_max_length: int
    checklist: tuple[str, ...]


class AIGitgenConfig(TypedDict):
    commit: CommitConfig
    pr: PullRequestConfig
