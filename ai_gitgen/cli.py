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
    AI_MODEL_ENV,
    CLI_PROG,
    COMMAND_COMMIT,
    COMMAND_PR,
    COMMAND_VALIDATE_OUTPUT,
    COMMIT_OUTPUT_HEADER,
    DEFAULT_API_BASE_URL,
    DEFAULT_CONFIG_FILE,
    DEFAULT_MAX_DIFF_LINES,
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_SAFE_MODE,
    DEFAULT_TEMPERATURE,
    DRY_RUN_STATUS_PREVIEW_LINES,
    DRY_RUN_SUMMARY_MARKER,
    EXIT_API_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    MIN_MAX_TOKENS,
    PR_BODY_MARKER,
    PR_TITLE_MARKER,
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


class ConfigError(ValueError):
    """Raised when .ai-gitgen.yml cannot drive generation safely."""


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
    validate = subparsers.add_parser(COMMAND_VALIDATE_OUTPUT)
    validate.add_argument("--config", default=DEFAULT_CONFIG_FILE, help="Team convention YML file")
    return parser


def add_generation_options(parser: argparse.ArgumentParser) -> None:
    default_model = os.getenv(AI_MODEL_ENV, DEFAULT_MODEL)
    parser.add_argument("--model", default=default_model, help=f"AI model name (default: {default_model})")
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
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE, help="Team convention YML file")
    parser.add_argument("--dry-run", action="store_true", help="Collect Git data and print prompt stats without API call")
    safety = parser.add_mutually_exclusive_group()
    safety.add_argument("--safe-mode", dest="safe_mode", action="store_true", default=DEFAULT_SAFE_MODE)
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
        return validate_from_stdin(args.config)
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


def print_config_error(error: ConfigError) -> None:
    print(f"[ERROR] {DEFAULT_CONFIG_FILE} 설정 오류: {error}", file=sys.stderr)


def load_ai_gitgen_config(root: Path, config_path: str = DEFAULT_CONFIG_FILE) -> AIGitgenConfig:
    path = resolve_config_path(root, config_path)
    if not path.exists():
        raise ConfigError(f"{config_path} 파일이 필요합니다.")

    data = _parse_simple_yaml(path.read_text(encoding="utf-8"))
    config: AIGitgenConfig = {
        "commit": {
            "prefixes": _as_tuple(_config_value(data, "commit.prefixes")),
            "scope_required": _as_bool(_config_value(data, "commit.scope_required")),
            "subject_max_length": _as_int(_config_value(data, "commit.subject_max_length")),
        },
        "pr": {
            "sections": _as_tuple(_config_value(data, "pr.sections")),
            "tone": str(_config_value(data, "pr.tone")),
            "title_max_length": _as_int(_config_value(data, "pr.title_max_length")),
            "checklist": _as_tuple(_config_value(data, "pr.checklist")),
        },
    }
    validate_config(config)
    return config


def resolve_config_path(root: Path, config_path: str = DEFAULT_CONFIG_FILE) -> Path:
    path = Path(config_path)
    if path.is_absolute():
        return path

    repo_path = root / path
    if repo_path.exists():
        return repo_path

    tool_path = Path(__file__).resolve().parent.parent / path
    if config_path == DEFAULT_CONFIG_FILE and tool_path.exists():
        return tool_path

    return repo_path


def validate_config(config: AIGitgenConfig) -> None:
    commit = config["commit"]
    pr = config["pr"]
    if not commit["prefixes"]:
        raise ConfigError("commit.prefixes must include at least one prefix.")
    invalid_prefixes = [prefix for prefix in commit["prefixes"] if not prefix.islower() or " " in prefix]
    if invalid_prefixes:
        raise ConfigError("commit.prefixes must be lowercase words without spaces.")
    if commit["subject_max_length"] < 10:
        raise ConfigError("commit.subject_max_length must be at least 10.")
    if not pr["sections"]:
        raise ConfigError("pr.sections must include at least one section.")
    if pr["title_max_length"] < 10:
        raise ConfigError("pr.title_max_length must be at least 10.")
    section_kinds = {_section_key(section) for section in pr["sections"]}
    for required in ("what", "why", "how"):
        if required not in section_kinds:
            raise ConfigError("pr.sections must include What, Why, and How.")


def describe_config(config: AIGitgenConfig) -> str:
    commit = config["commit"]
    pr = config["pr"]
    scope_rule = "required" if commit["scope_required"] else "optional"
    lines = [
        "Team convention from .ai-gitgen.yml:",
        f"- commit prefixes: {', '.join(commit['prefixes'])}",
        f"- commit scope: {scope_rule}",
        f"- commit title max length: {commit['subject_max_length']}",
        f"- PR title max length: {pr['title_max_length']}",
        f"- PR sections: {', '.join(pr['sections'])}",
        f"- PR tone: {pr['tone']}",
    ]
    if pr["checklist"]:
        lines.append(f"- PR checklist: {', '.join(pr['checklist'])}")
    return "\n".join(lines)


def _config_value(data: dict[str, dict[str, Any]], key: str) -> Any:
    section_name, value_name = key.split(".", 1)
    section = data.get(section_name)
    if not section:
        raise ConfigError(f"{section_name} section is required.")
    value = section.get(value_name)
    if value in (None, "", []):
        raise ConfigError(f"{key} is required.")
    return value


def _as_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        items = [part.strip() for part in str(value).split(",")]
    return tuple(item for item in items if item)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    cleaned = str(value).strip().lower()
    if cleaned in {"true", "yes", "1"}:
        return True
    if cleaned in {"false", "no", "0"}:
        return False
    raise ConfigError("commit.scope_required must be true or false.")


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError("commit.subject_max_length must be an integer.") from exc


def _parse_simple_yaml(text: str) -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = {}
    section = ""
    list_key = ""

    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue

        if not line.startswith((" ", "\t")):
            key = line.strip()
            if key.endswith(":"):
                section = key[:-1].strip()
                data.setdefault(section, {})
                list_key = ""
            continue

        if not section:
            continue

        stripped = line.strip()
        if stripped.startswith("- ") and list_key:
            data[section].setdefault(list_key, []).append(_parse_scalar(stripped[2:].strip()))
            continue

        if ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            data[section][key] = _parse_scalar(value)
            list_key = ""
        else:
            data[section][key] = []
            list_key = key

    return data


def _strip_comment(line: str) -> str:
    quote = ""
    for char_index, char in enumerate(line):
        if char in {"'", '"'}:
            quote = "" if quote == char else char
        elif char == "#" and not quote:
            return line[:char_index]
    return line


def _parse_scalar(value: str) -> Any:
    cleaned = value.strip().strip('"').strip("'")
    if cleaned.lower() in {"true", "false"}:
        return cleaned.lower() == "true"
    if cleaned.startswith("[") and cleaned.endswith("]"):
        inner = cleaned[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    try:
        return int(cleaned)
    except ValueError:
        return cleaned


def _section_key(value: str) -> str:
    key = " ".join(value.strip().lower().split())
    return key
