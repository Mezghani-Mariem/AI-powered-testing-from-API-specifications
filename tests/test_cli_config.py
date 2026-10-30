import json

import pytest
from pydantic import ValidationError

from ai_generator.cli import main
from ai_generator.config import LLMConfig

from conftest import SPEC


def test_env_loading_and_environment_priority(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("LLM_MODEL=file-model\nLLM_TIMEOUT=12\nLLM_API_KEY=private-test-key\n", encoding="utf-8")
    monkeypatch.setenv("LLM_MODEL", "env-model")
    config = LLMConfig.from_env(env)
    assert config.model == "env-model" and config.timeout == 12
    assert "private-test-key" not in repr(config)
    assert "api_key" not in config.public_settings()


@pytest.mark.parametrize("changes", [{"timeout": 0}, {"max_retries": 9}, {"temperature": "NaN"}, {"base_url": "https://user:pass@provider.invalid/v1"}, {"base_url": "http://remote.invalid/v1"}])
def test_config_invalid(changes):
    with pytest.raises(ValidationError):
        LLMConfig(**changes)


def test_cli_demo_inspect_and_validate(tmp_path, capsys):
    path = tmp_path / "generated.json"
    assert main(["inspect", "--spec", str(SPEC)]) == 0
    assert main(["generate", "--spec", str(SPEC), "--output", str(path), "--mode", "mock"]) == 0
    assert main(["validate", "--tests", str(path), "--spec", str(SPEC)]) == 0
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == "1.0"
    assert '"mode": "mock"' in capsys.readouterr().out


def test_cli_invalid_json(tmp_path, capsys):
    path = tmp_path / "invalid.json"
    path.write_text("not-json", encoding="utf-8")
    assert main(["validate", "--tests", str(path)]) == 2
    assert "Invalid JSON" in capsys.readouterr().err


def test_cli_requires_key_for_live(tmp_path, monkeypatch, capsys):
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    assert main(["generate", "--spec", str(SPEC), "--output", str(tmp_path / "tests.json"), "--mode", "live", "--env-file", str(tmp_path / "absent.env")]) == 2
    assert "requires" in capsys.readouterr().err


def test_colliding_paths_prevent_overwrite(tmp_path):
    source = tmp_path / "spec.json"
    source.write_bytes(SPEC.read_bytes())
    original = source.read_bytes()
    assert main(["generate", "--spec", str(source), "--output", str(source), "--mode", "mock"]) == 2
    assert source.read_bytes() == original


def test_content_logging_requires_explicit_optin(tmp_path):
    assert main(["generate", "--spec", str(SPEC), "--output", str(tmp_path / "tests.json"), "--mode", "mock", "--log-content"]) == 2
