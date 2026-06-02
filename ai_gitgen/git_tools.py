"""Git command helpers used by the CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .constants import (
    DETACHED_BRANCH_NAME,
    GIT_BRANCH_CURRENT_ARGS,
    GIT_EXECUTABLE,
    GIT_RENAME_SEPARATOR,
    GIT_RENAME_SPLIT_MAX,
    GIT_RENAME_TARGET_INDEX,
    GIT_REV_PARSE_ROOT_ARGS,
    GIT_STAGED_DIFF_ARGS,
    GIT_STATUS_SHORT_ARGS,
    PROCESS_SUCCESS_RETURN_CODE,
    SHORT_STATUS_PATH_OFFSET,
)


class GitError(RuntimeError):
    """Raised when the current directory cannot be used as a Git project root."""


@dataclass(frozen=True)
class GitChangeSet:
    root: Path
    branch: str
    status: str
    diff: str
    changed_files: list[str]

    @property
    def has_changes(self) -> bool:
        return bool(self.status.strip())

    @property
    def diff_line_count(self) -> int:
        return len(self.diff.splitlines())


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        [GIT_EXECUTABLE, *args],
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != PROCESS_SUCCESS_RETURN_CODE:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise GitError(detail)
    return result.stdout


def discover_git_root(cwd: Path) -> Path:
    output = _run_git(list(GIT_REV_PARSE_ROOT_ARGS), cwd)
    return Path(output.strip()).resolve()


def ensure_project_root(cwd: Path) -> Path:
    root = discover_git_root(cwd)
    if cwd.resolve() != root:
        raise GitError(
            f"Git 프로젝트 루트에서 실행해야 합니다. 현재: {cwd.resolve()} / 루트: {root}"
        )
    return root


def parse_changed_files(status: str) -> list[str]:
    files: list[str] = []
    for line in status.splitlines():
        if not line.strip():
            continue
        path = (
            line[SHORT_STATUS_PATH_OFFSET:].strip()
            if len(line) > SHORT_STATUS_PATH_OFFSET
            else line.strip()
        )
        if GIT_RENAME_SEPARATOR in path:
            path = path.split(GIT_RENAME_SEPARATOR, GIT_RENAME_SPLIT_MAX)[GIT_RENAME_TARGET_INDEX]
        files.append(path)
    return files


def filter_staged_status(status: str) -> str:
    lines: list[str] = []
    for line in status.splitlines():
        if not line or line[0] in {" ", "?"}:
            continue
        path = (
            line[SHORT_STATUS_PATH_OFFSET:].strip()
            if len(line) > SHORT_STATUS_PATH_OFFSET
            else line.strip()
        )
        lines.append(f"{line[0]}  {path}")
    return "\n".join(lines)


def collect_changes(cwd: Path) -> GitChangeSet:
    root = ensure_project_root(cwd) #실패하면 enure_project_root에서 GitError 발생
    status = filter_staged_status(_run_git(list(GIT_STATUS_SHORT_ARGS), root).rstrip())
    branch = _run_git(list(GIT_BRANCH_CURRENT_ARGS), root).strip() or DETACHED_BRANCH_NAME
    staged = _run_git(list(GIT_STAGED_DIFF_ARGS), root).rstrip()
    return GitChangeSet(
        root=root,
        branch=branch,
        status=status,
        diff=staged,
        changed_files=parse_changed_files(status),
    )
