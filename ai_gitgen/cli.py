"""Command line interface for generating commit messages and PR drafts."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from .ai_client import AIClient, APIError
from .git_tools import GitError, collect_changes
from .output import (
    build_prompt,
    format_commit_output,
    format_pr_output,
    normalize_commit,
    normalize_pr,
    validate_commit,
    validate_pr,
)
from .safety import apply_safe_mode


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_API_BASE_URL = "https://api.openai.com/v1/chat/completions"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Generate Git commit messages and PR drafts from git status/diff.",
        epilog=(
            "Common options for commit/pr: --model, --temperature, --max-tokens, "
            "--safe-mode, --no-safe-mode, --dry-run."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("commit", "pr"):
        sub = subparsers.add_parser(name)
        add_generation_options(sub)
    subparsers.add_parser("validate-output")
    return parser


def add_generation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"AI model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--temperature", type=float, default=0.2, help="AI temperature (default: 0.2)")
    parser.add_argument("--max-tokens", type=int, default=700, help="Maximum generated tokens")
    parser.add_argument("--api-base-url", default=os.getenv("AI_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--dry-run", action="store_true", help="Collect Git data and print prompt stats without API call")
    safety = parser.add_mutually_exclusive_group()
    safety.add_argument("--safe-mode", dest="safe_mode", action="store_true", default=True)
    safety.add_argument("--no-safe-mode", dest="safe_mode", action="store_false")
    parser.add_argument("--max-files", type=int, default=10, help="Safe-mode diff file limit")
    parser.add_argument("--max-diff-lines", type=int, default=200, help="Safe-mode diff line limit")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate-output":
        return validate_from_stdin()
    return run_generation(args)


def run_generation(args: argparse.Namespace) -> int:
    try:
        changes = collect_changes(Path.cwd())
    except GitError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    print(f"[INFO] 현재 브랜치: {changes.branch}")
    print(f"[INFO] Git status 수집 완료: {len(changes.changed_files)}개 파일 변경 감지")
    if not changes.has_changes:
        print("[INFO] 변경 사항이 없습니다. 커밋 메시지를 생성하지 않고 종료합니다.")
        return 0

    safety = apply_safe_mode(changes.diff, args.safe_mode, args.max_files, args.max_diff_lines)
    print(f"[INFO] Git diff 수집 완료: {changes.diff_line_count}줄")
    if args.safe_mode:
        print(
            "[INFO] safe-mode 적용: "
            f"마스킹 {safety.masked_count}건, 생략 파일 {safety.omitted_files}개, 생략 줄 {safety.omitted_lines}줄"
        )
    else:
        print("[WARN] safe-mode 비활성화: diff 원문이 API 요청에 포함될 수 있습니다.")

    if args.dry_run:
        print("[INFO] dry-run 모드: AI API를 호출하지 않습니다.")
        print(f"[INFO] AI API 호출 횟수: 0")
        print("--- Dry Run Summary ---")
        print("\n".join(changes.status.splitlines()[:20]))
        print(f"diff_lines_sent={len(safety.text.splitlines())}")
        return 0

    api_key = os.getenv("AI_API_KEY")
    if not api_key:
        print('[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다. 예) export AI_API_KEY="YOUR_KEY"', file=sys.stderr)
        return 2

    messages = build_prompt(args.command, changes.status, safety.text, changes.changed_files, args.max_files)
    client = AIClient(api_key=api_key, base_url=args.api_base_url)
    print("[INFO] AI API 요청 중...")
    try:
        raw = client.generate(
            messages=messages,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    except APIError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        print(f"[INFO] AI API 호출 횟수: {client.call_count}")
        return 1

    print(f"[INFO] AI API 호출 횟수: {client.call_count}")
    if args.command == "commit":
        message = normalize_commit(raw, changes.changed_files)
        ok, errors = validate_commit(message)
        if not ok:
            print("[ERROR] 생성된 커밋 메시지 검증 실패: " + "; ".join(errors), file=sys.stderr)
            return 1
        print("[DONE] 커밋 메시지 생성 완료")
        print()
        print(format_commit_output(message))
        return 0
    elif args.command == "pr":
        title, body = normalize_pr(raw, changes.changed_files)
        ok, errors = validate_pr(title, body)
        if not ok:
            print("[ERROR] 생성된 PR 초안 검증 실패: " + "; ".join(errors), file=sys.stderr)
            return 1
        print("[DONE] PR 초안 생성 완료")
        print()
        print(format_pr_output(title, body))
        return 0

    return 2


def validate_from_stdin() -> int:
    text = sys.stdin.read()
    if "--- PR Body ---" in text:
        title = ""
        body = text
        if "--- PR Title ---" in text:
            after_title = text.split("--- PR Title ---", 1)[1]
            title = after_title.splitlines()[1].strip() if len(after_title.splitlines()) > 1 else ""
        if "--- PR Body ---" in text:
            body = text.split("--- PR Body ---", 1)[1]
        ok, errors = validate_pr(title, body)
    else:
        ok, errors = validate_commit(text)
    if ok:
        print("[PASS] 출력 형식 검증 통과")
        return 0
    print("[FAIL] 출력 형식 검증 실패: " + "; ".join(errors))
    return 1
