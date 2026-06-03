"""Command execution flows for ai-gitgen."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from .ai_client import AIClient, APIError
from .config import ConfigError, describe_config, load_ai_gitgen_config
from .constants import (
    AI_API_KEY_ENV,
    COMMAND_COMMIT,
    COMMAND_PR,
    COMMIT_OUTPUT_HEADER,
    DEFAULT_CONFIG_FILE,
    DRY_RUN_STATUS_PREVIEW_LINES,
    DRY_RUN_SUMMARY_MARKER,
    EXIT_API_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    PR_BODY_MARKER,
    PR_TITLE_MARKER,
)
from .git_tools import GitError, collect_changes
from .prompts import build_prompt
from .responses import (
    format_commit_output,
    format_pr_output,
    normalize_commit,
    normalize_pr,
    validate_commit,
    validate_pr,
)
from .safety import apply_safe_mode


def run_generation(args: argparse.Namespace) -> int:
    try:
        changes = collect_changes(Path.cwd())
    except GitError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    print(f"[INFO] 현재 브랜치: {changes.branch}")
    print(f"[INFO] Git status 수집 완료: {len(changes.changed_files)}개 파일 변경 감지")

    if not changes.has_changes:
        target = "커밋 메시지" if args.command == COMMAND_COMMIT else "PR 초안"
        print(f"[INFO] 변경 사항이 없습니다. {target}을 생성하지 않고 종료합니다.")
        return EXIT_SUCCESS

    try:
        config = load_ai_gitgen_config(changes.root, args.config)
    except ConfigError as exc:
        print_config_error(exc)
        return EXIT_USAGE_ERROR

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
        print("[INFO] AI API 호출 횟수: 0")
        print(DRY_RUN_SUMMARY_MARKER)
        print(describe_config(config))
        print("\n".join(changes.status.splitlines()[:DRY_RUN_STATUS_PREVIEW_LINES]))
        print(f"diff_lines_sent={len(safety.text.splitlines())}")
        return EXIT_SUCCESS

    api_key = os.getenv(AI_API_KEY_ENV)
    if not api_key:
        print('[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다. 예) export AI_API_KEY="YOUR_KEY"', file=sys.stderr)
        return EXIT_USAGE_ERROR

    prompt_files = changes.changed_files[: args.max_files] if args.safe_mode else changes.changed_files
    messages = build_prompt(args.command, changes.status, safety.text, prompt_files, config)
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
        message = normalize_commit(raw, changes.changed_files, config)
        ok, errors = validate_commit(message, config)
        if not ok:
            print("[ERROR] 생성된 커밋 메시지 검증 실패: " + "; ".join(errors), file=sys.stderr)
            return EXIT_API_ERROR
        print("[DONE] 커밋 메시지 생성 완료")
        print()
        print(format_commit_output(message))
        return EXIT_SUCCESS
    if args.command == COMMAND_PR:
        title, body = normalize_pr(raw, changes.changed_files, config)
        ok, errors = validate_pr(title, body, config)
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
        return EXIT_USAGE_ERROR
    text = sys.stdin.read()
    if PR_BODY_MARKER in text:
        title = ""
        body = text
        if PR_TITLE_MARKER in text:
            after_title = text.split(PR_TITLE_MARKER, 1)[1]
            title = (
                after_title.splitlines()[1].strip()
                if len(after_title.splitlines()) > 1
                else ""
            )
        if PR_BODY_MARKER in text:
            body = text.split(PR_BODY_MARKER, 1)[1]
        ok, errors = validate_pr(title, body, config)
    else:
        ok, errors = validate_commit(_extract_commit_message(text), config)
    if ok:
        print("[PASS] 출력 형식 검증 통과")
        return EXIT_SUCCESS
    print("[FAIL] 출력 형식 검증 실패: " + "; ".join(errors))
    return EXIT_API_ERROR


def print_config_error(error: ConfigError) -> None:
    print(f"[ERROR] {DEFAULT_CONFIG_FILE} 설정 오류: {error}", file=sys.stderr)


def _extract_commit_message(text: str) -> str:
    if COMMIT_OUTPUT_HEADER not in text:
        return text
    after_header = text.split(COMMIT_OUTPUT_HEADER, 1)[1]
    lines: list[str] = []
    for line in after_header.splitlines():
        stripped = line.strip()
        if stripped.startswith("---") and stripped.endswith("---"):
            break
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)
