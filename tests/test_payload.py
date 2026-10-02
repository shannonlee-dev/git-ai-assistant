"""최종 HTTP 요청에서 안전 모드의 파일·행 제한과 마스킹을 검증한다."""

import io
import json
import subprocess
from urllib.error import HTTPError

import pytest

from ai_gitgen import ai_client
from ai_gitgen.cli import main


@pytest.fixture
def staged_repository(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for index in range(12):
        (tmp_path / f"user{index}@example.com.txt").write_text(
            "api_key=sk-secret1234567890123456789\n", encoding="utf-8"
        )
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_API_KEY", "local-placeholder")


@pytest.mark.parametrize("command", ["commit", "pr"])
def test_safe_mode_protects_final_http_payload(staged_repository, monkeypatch, command):
    requests = []

    def capture(request, timeout):
        requests.append(json.loads(request.data))
        return io.BytesIO(b'{"choices":[{"message":{"content":"feat: summary"}}]}')

    monkeypatch.setattr(ai_client, "urlopen", capture)
    assert main([command, "--max-files", "2", "--max-diff-lines", "12"]) == 0
    assert len(requests) == 1
    content = requests[0]["messages"][-1]["content"]
    assert "@example.com" not in content
    assert "sk-secret1234567890123456789" not in content
    assert "user2" not in content and "user9" not in content
    files, remainder = content.split("## Changed Files\n", 1)[1].split(
        "## Git Status Short\n", 1
    )
    status, diff = remainder.split("## Git Diff\n", 1)
    assert len(files.strip().splitlines()) == 2
    assert len(status.strip().splitlines()) == 2
    assert len(diff.strip().splitlines()) <= 12


def test_disabled_safe_mode_keeps_complete_payload(staged_repository, monkeypatch):
    requests = []

    def capture(request, timeout):
        requests.append(json.loads(request.data))
        return io.BytesIO(b'{"choices":[{"message":{"content":"feat: summary"}}]}')

    monkeypatch.setattr(ai_client, "urlopen", capture)
    assert main(["commit", "--no-safe-mode", "--max-files", "1"]) == 0
    content = requests[0]["messages"][-1]["content"]
    assert "user9@example.com.txt" in content
    assert "sk-secret1234567890123456789" in content


def test_api_error_reports_failure_without_retry(
    staged_repository, monkeypatch, capsys
):
    requests = []

    def reject(request, timeout):
        requests.append(request)
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"{}"))

    monkeypatch.setattr(ai_client, "urlopen", reject)
    assert main(["commit"]) == 1
    output = capsys.readouterr()
    assert "401" in output.err and "AI_API_KEY" in output.err
    assert len(requests) == 1


def test_invalid_output_returns_failure(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("invalid title\nsecond line\n"))
    assert main(["validate-output"]) == 1
    assert "[FAIL]" in capsys.readouterr().out
