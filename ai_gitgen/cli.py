"""Command line parser for generating commit messages and PR drafts."""

from __future__ import annotations

import argparse
import os

from .constants import (
    AI_API_BASE_URL_ENV,
    AI_MODEL_ENV,
    CLI_PROG,
    COMMAND_COMMIT,
    COMMAND_PR,
    COMMAND_VALIDATE_OUTPUT,
    DEFAULT_API_BASE_URL,
    DEFAULT_CONFIG_FILE,
    DEFAULT_MAX_DIFF_LINES,
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_SAFE_MODE,
    DEFAULT_TEMPERATURE,
    MIN_MAX_TOKENS,
)
from .runner import run_generation, validate_from_stdin


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
    parser.add_argument("--max-files", type=parse_positive_int, default=DEFAULT_MAX_FILES, help="Safe-mode diff file limit")
    parser.add_argument(
        "--max-diff-lines",
        type=parse_positive_int,
        default=DEFAULT_MAX_DIFF_LINES,
        help="Safe-mode diff line limit",
    )


def parse_max_tokens(value: str) -> int:
    try:
        max_tokens = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if max_tokens < MIN_MAX_TOKENS:
        raise argparse.ArgumentTypeError(f"must be at least {MIN_MAX_TOKENS}")
    return max_tokens


def parse_positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == COMMAND_VALIDATE_OUTPUT:
        return validate_from_stdin(args.config)
    return run_generation(args)
