"""Local model configuration editor; preserves unrelated JSONC and dotenv data."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from threading import RLock
from typing import Literal
from urllib.parse import urlsplit

from dotenv import dotenv_values
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from artemis.config.paths import get_config_path, get_env_file
from artemis.utils.file import load_jsonc

PROVIDER_KEYS = {
    "openai": ["OPENAI_API_KEY"],
    "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY", "GCP_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "openrouter": ["OPEN_ROUTER_API_KEY"],
    "xai": ["XAI_API_KEY"],
    "custom": ["OPENAI_API_KEY"],
    "ollama": ["OPENAI_API_KEY"],
    "vllm": ["OPENAI_API_KEY"],
}


class ModelSettingsUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    expected_version: str
    provider: Literal[
        "openai", "google", "anthropic", "openrouter", "xai", "custom", "ollama", "vllm"
    ]
    default_model: str = Field(min_length=1, max_length=200)
    fallback_model: str = Field(min_length=1, max_length=200)
    base_url: str = ""
    fallback_url: str = ""
    api_key: SecretStr | None = None
    confirm_restart: Literal[True]

    @field_validator("default_model", "fallback_model")
    @classmethod
    def clean_model(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Enter a valid model name")
        return value

    @field_validator("base_url", "fallback_url")
    @classmethod
    def clean_url(cls, value):
        value = value.strip().rstrip("/")
        if value:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or any(c.isspace() for c in value)
            ):
                raise ValueError("Use an HTTP(S) base URL without credentials, query or fragment")
        return value

    @model_validator(mode="after")
    def validate_provider_url(self):
        if self.provider == "google" and (self.base_url or self.fallback_url):
            raise ValueError("Custom URL is not supported for Google in this editor")
        if self.api_key and any(c in self.api_key.get_secret_value() for c in "\r\n\x00"):
            raise ValueError("Invalid API key")
        return self


def _replace_default(source: str, value: dict) -> str:
    # Token offsets preserve comments/whitespace outside the edited default object.
    tokens = list(re.finditer(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/|[{}:\[\]]', source))
    depth = 0
    start = None
    wanted = False
    for token in tokens:
        text = token.group()
        if text.startswith(("//", "/*")):
            continue
        if depth == 1 and text == '"default"':
            wanted = True
        if text in ("{", "["):
            if wanted and start is None:
                if text != "{":
                    raise ValueError("The default configuration must be an object")
                start = token.start()
            depth += 1
        elif text in ("}", "]"):
            depth -= 1
            if start is not None and depth == 1:
                replacement = json.dumps(value, ensure_ascii=False, indent=2).replace("\n", "\n  ")
                return source[:start] + replacement + source[token.end() :]
    raise ValueError("No unified default model configuration found")


def _env_update(source: str, updates: dict[str, str]) -> str:
    lines = source.splitlines()
    result, seen = [], set()
    for line in lines:
        match = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        key = match.group(1) if match else None
        if key in updates:
            if key in seen:
                continue
            seen.add(key)
            value = updates[key].replace("\\", "\\\\").replace("'", "\\'")
            result.append(f"{key}='{value}'")
        else:
            result.append(line)
    for key, value in updates.items():
        if key not in seen:
            value = value.replace("\\", "\\\\").replace("'", "\\'")
            result.append(f"{key}='{value}'")
    return "\n".join(result) + "\n"


def _atomic_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            os.chmod(name, path.stat().st_mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class ModelSettingsService:
    def __init__(self, config_path=None, env_path=None):
        self.config_path = Path(config_path) if config_path else get_config_path("artemis.jsonc")
        self.env_path = Path(env_path) if env_path else get_env_file()
        self.lock = RLock()

    def _read(self):
        config = self.config_path.read_bytes().decode("utf-8")
        env = self.env_path.read_bytes().decode("utf-8") if self.env_path.exists() else ""
        version = hashlib.sha256((config + "\0" + env).encode()).hexdigest()
        return config, env, version

    def get(self):
        with self.lock:
            source, env, version = self._read()
            config = load_jsonc(io.StringIO(source))
            default = config.get("default", {})
            fallback = default.get("fallback", {})
            values = dotenv_values(stream=io.StringIO(env))
            return {
                "provider": default.get("provider", "google"),
                "default_model": default.get("model", ""),
                "fallback_model": fallback.get("model", ""),
                "fallback_provider": fallback.get("provider", default.get("provider")),
                "base_url": default.get("api_base")
                or default.get("base_url")
                or (
                    values.get("OPENAI_BASE_URL")
                    if default.get("provider") in {"openai", "custom", "ollama", "vllm"}
                    else ""
                )
                or "",
                "fallback_url": fallback.get("api_base") or fallback.get("base_url") or "",
                "keys_configured": {
                    p: any(bool(values.get(k) or os.environ.get(k)) for k in keys)
                    for p, keys in PROVIDER_KEYS.items()
                },
                "version": version,
                "config_path": str(self.config_path),
                "env_path": str(self.env_path),
                "node_overrides": sorted(config.get("nodes", {}).keys()),
            }

    def save(self, request: ModelSettingsUpdate):
        with self.lock:
            source, env, version = self._read()
            if version != request.expected_version:
                raise FileExistsError("Configuration changed. Reload before saving.")
            config = load_jsonc(io.StringIO(source))
            default = dict(config.get("default", {}))
            fallback = dict(default.get("fallback", {}))
            for item, model, url in (
                (default, request.default_model, request.base_url),
                (fallback, request.fallback_model, request.fallback_url or request.base_url),
            ):
                if item.get("provider") != request.provider:
                    for key in (
                        "thinking_level",
                        "thinking_budget",
                        "include_thoughts",
                        "reasoning_effort",
                        "enable_grounding",
                    ):
                        item.pop(key, None)
                item.update(provider=request.provider, model=model)
                item.pop("base_url", None)
                item["api_base"] = url or None
            default["fallback"] = fallback
            updated = _replace_default(source, default)
            from artemis.config.llm import LLMWithFallback

            LLMWithFallback.model_validate(load_jsonc(io.StringIO(updated))["default"])
            updates = {}
            if request.api_key and request.api_key.get_secret_value().strip():
                for key in PROVIDER_KEYS[request.provider]:
                    updates[key] = request.api_key.get_secret_value().strip()
            if request.provider in {"openai", "custom", "ollama", "vllm"}:
                updates["OPENAI_BASE_URL"] = request.base_url
            new_env = _env_update(env, updates) if updates else env
            _atomic_write(self.env_path, new_env)
            try:
                _atomic_write(self.config_path, updated)
            except Exception:
                _atomic_write(self.env_path, env)
                raise
            # Return the names, not values, so the child can drop stale inherited
            # env and reload the newly saved .env at startup.
            return list(updates)
