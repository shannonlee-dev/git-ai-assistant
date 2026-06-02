"""Git command helpers used by the CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


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
        ["git", *args],
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise GitError(detail)
    return result.stdout


def discover_git_root(cwd: Path) -> Path:
    output = _run_git(["rev-parse", "--show-toplevel"], cwd)
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
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return files


def collect_changes(cwd: Path) -> GitChangeSet:
    root = ensure_project_root(cwd) #실패하면 enure_project_root에서 GitError 발생
    status = _run_git(["status", "--short"], root).rstrip()
    branch = _run_git(["branch", "--show-current"], root).strip() or "detached"
    staged = _run_git(["diff", "--cached", "--no-ext-diff", "--"], root).rstrip()
    return GitChangeSet(
        root=root,
        branch=branch,
        status=status,
        diff=staged,
        changed_files=parse_changed_files(status),
    )
