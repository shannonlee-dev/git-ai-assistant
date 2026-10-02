"""사용자 설정 우선순위와 기본 규칙·파서 계약을 검증한다."""

import pytest

from ai_gitgen.config import ConfigError, load_ai_gitgen_config
from ai_gitgen.config_parser import parse_rules


def test_default_rules_and_explicit_missing_path(tmp_path):
    config = load_ai_gitgen_config(tmp_path)
    assert "feat" in config["commit"]["prefixes"]
    assert config["pr"]["sections"] == ("What", "Why", "How")
    with pytest.raises(ConfigError):
        load_ai_gitgen_config(tmp_path, "missing.yml")


def test_parser_keeps_quoted_hash_and_inline_list():
    data = parse_rules('commit:\n  prefixes: [feat, fix]\n  label: "값#태그" # 주석\n')
    assert data["commit"]["prefixes"] == ["feat", "fix"]
    assert data["commit"]["label"] == "값#태그"


def test_repository_rules_override_packaged_defaults(tmp_path):
    from ai_gitgen.config import resolve_config_path

    default = resolve_config_path(tmp_path)
    local = tmp_path / ".ai-gitgen.yml"
    local.write_text(
        default.read_text().replace("subject_max_length: 100", "subject_max_length: 60")
    )
    assert resolve_config_path(tmp_path) == local
    assert load_ai_gitgen_config(tmp_path)["commit"]["subject_max_length"] == 60
