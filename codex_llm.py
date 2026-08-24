"""Shared client for the Codex-compatible Responses API."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import requests

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


DEFAULT_CODEX_BASE_URL = "https://www.cctq.ai/v1"
DEFAULT_CODEX_MODEL = "gpt-5.6-terra"


@dataclass(frozen=True)
class CodexSettings:
    api_key: str
    base_url: str
    model: str

    @property
    def responses_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/responses"


def _load_env_file() -> None:
    """Load the project .env without overwriting process environment values."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


def _read_codex_provider_base_url(config_path: Path) -> str:
    if not config_path.exists():
        return ""

    try:
        with config_path.open("rb") as config_file:
            data = tomllib.load(config_file)
        provider_name = data.get("model_provider", "")
        provider = data.get("model_providers", {}).get(provider_name, {})
        return str(provider.get("base_url", "")).strip()
    except (OSError, ValueError, TypeError):
        return ""


def _read_codex_auth_key(auth_path: Path) -> str:
    if not auth_path.exists():
        return ""

    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
        return str(data.get("OPENAI_API_KEY") or "").strip()
    except (OSError, ValueError, TypeError):
        return ""


def get_codex_settings() -> CodexSettings:
    """Resolve provider settings from env overrides and the active Codex config."""
    _load_env_file()

    codex_home = Path(os.getenv("CODEX_HOME") or Path.home() / ".codex").expanduser()
    config_path = Path(
        os.getenv("CODEX_CONFIG_PATH") or codex_home / "config.toml"
    ).expanduser()
    auth_path = Path(
        os.getenv("CODEX_AUTH_PATH") or codex_home / "auth.json"
    ).expanduser()

    api_key = (
        os.getenv("CODEX_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
        or _read_codex_auth_key(auth_path)
    )
    if not api_key:
        raise RuntimeError(
            "Codex API key not found. Set CODEX_API_KEY or OPENAI_API_KEY, "
            "or sign in with Codex so ~/.codex/auth.json is available."
        )

    base_url = (
        os.getenv("CODEX_API_BASE_URL", "").strip()
        or _read_codex_provider_base_url(config_path)
        or DEFAULT_CODEX_BASE_URL
    )
    model = os.getenv("CODEX_MODEL", DEFAULT_CODEX_MODEL).strip() or DEFAULT_CODEX_MODEL

    return CodexSettings(api_key=api_key, base_url=base_url, model=model)


def extract_response_text(payload: Dict[str, Any]) -> str:
    """Extract assistant text from a raw Responses API payload."""
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text

    text_parts = []
    for output_item in payload.get("output", []):
        if not isinstance(output_item, dict):
            continue
        for content_item in output_item.get("content", []):
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str) and text:
                text_parts.append(text)
    if text_parts:
        return "\n".join(text_parts)

    # Some compatible gateways return a Chat Completions-shaped response.
    choices = payload.get("choices", [])
    if choices and isinstance(choices[0], dict):
        content = choices[0].get("message", {}).get("content")
        if isinstance(content, str):
            return content

    raise ValueError("Codex Responses API returned no text output")


def call_codex_responses(
    system_prompt: str,
    user_prompt: str,
    *,
    max_output_tokens: int = 2000,
    timeout: int = 60,
) -> str:
    """Call gpt-5.6-terra through the active Codex-compatible provider."""
    settings = get_codex_settings()
    response = requests.post(
        settings.responses_url,
        headers={
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_output_tokens": max_output_tokens,
            "store": False,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return extract_response_text(response.json())
