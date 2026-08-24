import json

import codex_llm


def test_get_codex_settings_reads_codex_config_and_auth(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'model_provider = "my_codex"\n'
        '[model_providers.my_codex]\n'
        'base_url = "https://example.test/v1"\n',
        encoding="utf-8",
    )
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(
        json.dumps({"OPENAI_API_KEY": "test-key"}),
        encoding="utf-8",
    )

    monkeypatch.setenv("CODEX_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("CODEX_AUTH_PATH", str(auth_path))
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_BASE_URL", raising=False)
    monkeypatch.delenv("CODEX_MODEL", raising=False)

    settings = codex_llm.get_codex_settings()

    assert settings.api_key == "test-key"
    assert settings.responses_url == "https://example.test/v1/responses"
    assert settings.model == "gpt-5.6-terra"


def test_extract_response_text_from_responses_output():
    payload = {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "first"},
                    {"type": "output_text", "text": "second"},
                ],
            }
        ]
    }

    assert codex_llm.extract_response_text(payload) == "first\nsecond"


def test_call_codex_responses_uses_responses_schema(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"output_text": "ok"}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setenv("CODEX_API_KEY", "test-key")
    monkeypatch.setenv("CODEX_API_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("CODEX_MODEL", "gpt-5.6-terra")
    monkeypatch.setattr(codex_llm.requests, "post", fake_post)

    result = codex_llm.call_codex_responses(
        "system prompt",
        "user prompt",
        max_output_tokens=321,
        timeout=12,
    )

    assert result == "ok"
    assert captured["url"] == "https://example.test/v1/responses"
    assert captured["timeout"] == 12
    assert captured["json"] == {
        "model": "gpt-5.6-terra",
        "input": [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user prompt"},
        ],
        "max_output_tokens": 321,
        "store": False,
    }
