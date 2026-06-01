"""Command line interface for generating commit messages and PR drafts."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any

from .ai_client import AIClient, APIError
from .constants import (
    AI_API_BASE_URL_ENV,
    AI_API_KEY_ENV,
    CLI_PROG,
    COMMAND_COMMIT,
    COMMAND_PR,
    COMMAND_VALIDATE_OUTPUT,
    DEFAULT_API_BASE_URL,
    DEFAULT_MAX_DIFF_LINES,
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DRY_RUN_STATUS_PREVIEW_LINES,
    DRY_RUN_SUMMARY_MARKER,
    EXIT_API_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    MIN_MAX_TOKENS,
    PR_BODY_MARKER,
    PR_TITLE_MARKER,
    MARKER_SPLIT_MAX,
    PR_TITLE_CONTENT_LINE_INDEX,
    ZERO_API_CALLS,
)
from .git_tools import GitError, collect_changes
from .output import (
    AIGitgenConfig,
    build_prompt,
    format_commit_output,
    format_pr_output,
    normalize_commit,
    normalize_pr,
    validate_commit,
    validate_pr,
)
from .safety import apply_safe_mode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=CLI_PROG,
        description="Generate Git commit messages and PR drafts from git status/diff.",
        epilog=(
            "Common options for commit/pr: --model, --temperature, --max-tokens, "
            "--safe-mode, --no-safe-mode, --dry-run."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in (COMMAND_COMMIT, COMMAND_PR):
        sub = subparsers.add_parser(name)
        add_generation_options(sub)
    subparsers.add_parser(COMMAND_VALIDATE_OUTPUT)
    return parser


def add_generation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"AI model name (default: {DEFAULT_MODEL})")
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help=f"AI temperature (default: {DEFAULT_TEMPERATURE})",
    )
    parser.add_argument(
        "--max-tokens",
        type=parse_max_tokens,
        default=DEFAULT_MAX_TOKENS,
        help=f"Maximum generated tokens (minimum: {MIN_MAX_TOKENS})",
    )
    parser.add_argument("--api-base-url", default=os.getenv(AI_API_BASE_URL_ENV, DEFAULT_API_BASE_URL))
    parser.add_argument("--dry-run", action="store_true", help="Collect Git data and print prompt stats without API call")
    safety = parser.add_mutually_exclusive_group()
    safety.add_argument("--safe-mode", dest="safe_mode", action="store_true", default=True)
    safety.add_argument("--no-safe-mode", dest="safe_mode", action="store_false")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES, help="Safe-mode diff file limit")
    parser.add_argument("--max-diff-lines", type=int, default=DEFAULT_MAX_DIFF_LINES, help="Safe-mode diff line limit")


def parse_max_tokens(value: str) -> int:
    try:
        max_tokens = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if max_tokens < MIN_MAX_TOKENS:
        raise argparse.ArgumentTypeError(f"must be at least {MIN_MAX_TOKENS}")
    return max_tokens


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == COMMAND_VALIDATE_OUTPUT:
        return validate_from_stdin()
    return run_generation(args)


def run_generation(args: argparse.Namespace) -> int:
    try:
        changes = collect_changes(Path.cwd())
    except GitError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    print(f"[INFO] 현재 브랜치: {changes.branch}")
    print(f"[INFO] Git status 수집 완료: {len(changes.changed_files)}개 파일 변경 감지")
    if not changes.has_changes:
        print("[INFO] 변경 사항이 없습니다. 커밋 메시지를 생성하지 않고 종료합니다.")
        return EXIT_SUCCESS

    if not changes.has_changes:
        target = "커밋 메시지" if args.command == "commit" else "PR 초안"
        print(f"[INFO] 변경 사항이 없습니다. {target}을 생성하지 않고 종료합니다.")
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
        print(f"[INFO] AI API 호출 횟수: {ZERO_API_CALLS}")
        print(DRY_RUN_SUMMARY_MARKER)
        print("\n".join(changes.status.splitlines()[:DRY_RUN_STATUS_PREVIEW_LINES]))
        print(f"diff_lines_sent={len(safety.text.splitlines())}")
        return EXIT_SUCCESS

    api_key = os.getenv(AI_API_KEY_ENV)
    if not api_key:
        print('[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다. 예) export AI_API_KEY="YOUR_KEY"', file=sys.stderr)
        return EXIT_USAGE_ERROR

    messages = build_prompt(args.command, changes.status, safety.text, changes.changed_files, args.max_files, config)
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
        return EXIT_API_ERROR

    print(f"[INFO] AI API 호출 횟수: {client.call_count}")
    if args.command == COMMAND_COMMIT:
        message = normalize_commit(raw, changes.changed_files)
        ok, errors = validate_commit(message)
        if not ok:
            print("[ERROR] 생성된 커밋 메시지 검증 실패: " + "; ".join(errors), file=sys.stderr)
            return EXIT_API_ERROR
        print("[DONE] 커밋 메시지 생성 완료")
        print()
        print(format_commit_output(message))
        return EXIT_SUCCESS
    elif args.command == COMMAND_PR:
        title, body = normalize_pr(raw, changes.changed_files)
        ok, errors = validate_pr(title, body)
        if not ok:
            print("[ERROR] 생성된 PR 초안 검증 실패: " + "; ".join(errors), file=sys.stderr)
            return EXIT_API_ERROR
        print("[DONE] PR 초안 생성 완료")
        print()
        print(format_pr_output(title, body))
        return EXIT_SUCCESS

    return EXIT_USAGE_ERROR


def validate_from_stdin(config_path: str = DEFAULT_CONFIG_FILE) -> int:
    try:
        config = load_ai_gitgen_config(Path.cwd(), config_path)
    except ConfigError as exc:
        print_config_error(exc)
        return 2
    text = sys.stdin.read()
    if PR_BODY_MARKER in text:
        title = ""
        body = text
        if PR_TITLE_MARKER in text:
            after_title = text.split(PR_TITLE_MARKER, MARKER_SPLIT_MAX)[PR_TITLE_CONTENT_LINE_INDEX]
            title = (
                after_title.splitlines()[PR_TITLE_CONTENT_LINE_INDEX].strip()
                if len(after_title.splitlines()) > PR_TITLE_CONTENT_LINE_INDEX
                else ""
            )
        if PR_BODY_MARKER in text:
            body = text.split(PR_BODY_MARKER, MARKER_SPLIT_MAX)[PR_TITLE_CONTENT_LINE_INDEX]
        ok, errors = validate_pr(title, body)
    else:
        ok, errors = validate_commit(_extract_commit_message(text), config)
    if ok:
        print("[PASS] 출력 형식 검증 통과")
        return EXIT_SUCCESS
    print("[FAIL] 출력 형식 검증 실패: " + "; ".join(errors))
    return EXIT_API_ERROR
