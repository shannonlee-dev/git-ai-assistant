"""격리된 Git 저장소에서 CLI와 모의 AI 응답을 검증한다."""

import os
import subprocess
import sys

import pytest

from ai_gitgen.safety import apply_safe_mode

pytestmark = pytest.mark.smoke


@pytest.fixture
def cli(tmp_path):
    subprocess.run(
        ["git", "init", "-q", "--initial-branch=main", str(tmp_path)],
        check=True,
        timeout=30,
    )
    (tmp_path / "sample.txt").write_text("검증용 변경\n")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "sample.txt"],
        check=True,
        timeout=30,
    )
    env = dict(
        os.environ, AI_API_KEY="local-mock-placeholder", PYTHONDONTWRITEBYTECODE="1"
    )

    def run(args, input_text=None):
        result = subprocess.run(
            [sys.executable, "-m", "ai_gitgen", *args],
            input=input_text,
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    return run


def test_dry_run_skips_api_calls(cli):
    assert "AI API 호출 횟수: 0" in cli(["commit", "--dry-run", "--safe-mode"])


@pytest.mark.parametrize("command", ["commit", "pr"])
def test_generated_output_satisfies_contract(cli, command):
    generated = cli([command, "--api-base-url", f"mock://{command}"])
    assert "AI API 호출 횟수: 1" in generated
    assert "[PASS]" in cli(["validate-output"], generated)


def test_safe_mode_masks_credentials_and_email():
    safe = apply_safe_mode(
        "api_key=sk-testcredential123456\nname@example.com", True, 10, 200
    )
    assert "sk-testcredential123456" not in safe.text
    assert "name@example.com" not in safe.text
