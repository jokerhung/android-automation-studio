"""Versioned SQLite model settings; legacy files are imported once."""

from __future__ import annotations

import asyncio
from pathlib import Path
from threading import RLock
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from artemis.config.paths import get_env_file
from artemis.config.sqlite_store import (
    PROVIDER_KEYS,
    MODEL_ENV_KEYS,
    SettingsStore,
    get_settings_store,
)


class ModelListRequest(BaseModel):
    model_config = {"extra": "forbid"}
    provider: Literal[
        "openai",
        "openai_acp",
        "google",
        "anthropic",
        "openrouter",
        "xai",
        "custom",
        "ollama",
        "vllm",
    ]
    base_url: str = ""
    fallback_url: str = ""
    api_key: SecretStr | None = None
    codex_path: str = Field(default="", max_length=2048)

    @field_validator("base_url", "fallback_url")
    @classmethod
    def clean_url(cls, value):
        return ModelSettingsUpdate.clean_url(value)

    @field_validator("api_key")
    @classmethod
    def clean_key(cls, value):
        if value and any(ord(c) < 32 for c in value.get_secret_value()):
            raise ValueError("Invalid API key")
        return value


class ModelSettingsUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    expected_version: str
    provider: Literal[
        "openai",
        "openai_acp",
        "google",
        "anthropic",
        "openrouter",
        "xai",
        "custom",
        "ollama",
        "vllm",
    ]
    default_model: str = Field(max_length=200)
    fallback_model: str = Field(max_length=200)
    base_url: str = ""
    fallback_url: str = ""
    api_key: SecretStr | None = None
    codex_path: str = Field(default="", max_length=2048)
    confirm_restart: Literal[True]

    @field_validator("default_model", "fallback_model")
    @classmethod
    def clean_model(cls, value):
        value = value.strip()
        if any(ord(c) < 32 for c in value):
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
        if self.provider == "openai_acp":
            if (
                self.base_url
                or self.fallback_url
                or (self.api_key and self.api_key.get_secret_value().strip())
            ):
                raise ValueError(
                    "OpenAI ACP uses the installed Codex CLI login, not API keys or URLs"
                )
        if self.provider == "google" and (self.base_url or self.fallback_url):
            raise ValueError("Custom URL is not supported for Google in this editor")
        if self.api_key and any(c in self.api_key.get_secret_value() for c in "\r\n\x00"):
            raise ValueError("Invalid API key")
        return self


class ModelSettingsService:
    def __init__(self, config_path=None, env_path=None, *, store=None):
        self.config_path = Path(config_path) if config_path is not None else None
        self.env_path = Path(env_path) if env_path else get_env_file()
        self.store = store or (
            SettingsStore(self.config_path.parent / "settings.sqlite3")
            if config_path is not None
            else get_settings_store()
        )
        self.lock = RLock()

    def _read(self):
        return self.store.model(self.config_path, self.env_path)

    async def list_models(self, request: ModelListRequest):
        if request.provider == "openai_acp":
            from artemis.llm.openai_acp import available_codex_models

            document, _ = self._read()
            models = await available_codex_models(
                request.codex_path.strip() or document["credentials"].get("ARTEMIS_CODEX_PATH", "")
            )
            return {"default_models": models, "fallback_models": models}
        # Use the draft credential without persisting it or returning it to the UI.
        with self.lock:
            document, _ = self._read()
            env = document["credentials"]
        key = request.api_key.get_secret_value().strip() if request.api_key else ""
        if not key:
            key = next(
                (env[k] for k in PROVIDER_KEYS[request.provider] if env.get(k)),
                "",
            )
        defaults = {
            "openai": "https://api.openai.com/v1",
            "google": "https://generativelanguage.googleapis.com/v1beta",
            "anthropic": "https://api.anthropic.com/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "xai": "https://api.x.ai/v1",
            "ollama": "http://localhost:11434/v1",
            "vllm": "http://localhost:8000/v1",
        }
        base = request.base_url or defaults.get(request.provider)
        if not base:
            raise ValueError("Enter a base URL before fetching models.")
        fallback = request.fallback_url or base
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        if request.provider == "google":
            base = fallback = defaults["google"]
            headers = {"x-goog-api-key": key}
        elif request.provider == "anthropic":
            headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}

        async def fetch(client, url):
            models, seen = set(), set()
            params = {"pageSize": 1000} if request.provider == "google" else {}
            if request.provider == "anthropic":
                params = {"limit": 1000}
            for _ in range(100):
                response = await client.get(
                    f"{url.rstrip('/')}/models", headers=headers, params=params
                )
                if not response.is_success:
                    raise ValueError(
                        f"Unable to fetch models (HTTP {response.status_code}). Check the API key and endpoint."
                    )
                data = response.json()
                items = data.get("models" if request.provider == "google" else "data")
                if not isinstance(items, list):
                    raise ValueError("The endpoint returned an invalid model list.")
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if request.provider == "google":
                        if "generateContent" not in item.get("supportedGenerationMethods", []):
                            continue
                        name = item.get("name", "").removeprefix("models/")
                    else:
                        name = item.get("id")
                    if isinstance(name, str) and name.strip() and len(name) <= 200:
                        models.add(name)
                token = (
                    data.get("nextPageToken")
                    if request.provider == "google"
                    else (
                        data.get("last_id")
                        if request.provider == "anthropic" and data.get("has_more")
                        else None
                    )
                )
                if not token:
                    return sorted(models)
                if token in seen:
                    break
                seen.add(token)
                params["pageToken" if request.provider == "google" else "after_id"] = token
            raise ValueError("Unable to finish loading the model list. Try again.")

        try:
            async with (
                asyncio.timeout(25),
                httpx.AsyncClient(timeout=10, follow_redirects=False) as client,
            ):
                primary = await fetch(client, base)
                secondary = primary if fallback == base else await fetch(client, fallback)
                return {"default_models": primary, "fallback_models": secondary}
        except (httpx.HTTPError, TimeoutError):
            raise ValueError(
                "Unable to reach the model endpoint. Check the URL and connection."
            ) from None
        except (TypeError, AttributeError):
            raise ValueError("The endpoint returned an invalid model list.") from None

    def get(self):
        document, version = self._read()
        config, values = document["config"], document["credentials"]
        default = config.get("default", {})
        fallback = default.get("fallback", {})
        return {
            "provider": default.get("provider", "google"),
            "default_model": default.get("model", ""),
            "fallback_model": fallback.get("model", ""),
            "fallback_provider": fallback.get("provider", default.get("provider")),
            "base_url": default.get("api_base")
            or default.get("base_url")
            or (
                values.get("OPENAI_BASE_URL", "")
                if default.get("provider") in {"openai", "custom", "ollama", "vllm"}
                else ""
            ),
            "fallback_url": fallback.get("api_base") or fallback.get("base_url") or "",
            "codex_path": values.get("ARTEMIS_CODEX_PATH", ""),
            "keys_configured": {
                p: any(bool(values.get(k)) for k in keys) for p, keys in PROVIDER_KEYS.items()
            },
            "version": str(version),
            "storage": "sqlite",
            "database_path": str(self.store.path),
            "node_overrides": sorted(config.get("nodes", {}).keys()),
        }

    def save(self, request: ModelSettingsUpdate):
        self._read()

        def change(document):
            config = document["config"]
            default = dict(config.get("default", {}))
            fallback = dict(default.get("fallback", {}))
            for item, model, url in (
                (default, request.default_model, request.base_url),
                (fallback, request.fallback_model, request.fallback_url),
            ):
                provider_changed = item.get("provider") != request.provider
                if provider_changed:
                    for key in (
                        "thinking_level",
                        "thinking_budget",
                        "include_thoughts",
                        "reasoning_effort",
                        "enable_grounding",
                    ):
                        item.pop(key, None)
                item.update(provider=request.provider, model=model or item.get("model", ""))
                if url or provider_changed:
                    item.pop("base_url", None)
                    item["api_base"] = url or (
                        request.base_url if item is fallback else None
                    ) or None
            default["fallback"] = fallback
            from artemis.config.llm import LLMWithFallback

            LLMWithFallback.model_validate(default)
            config["default"] = default
            values = document["credentials"]
            if request.provider == "openai_acp":
                from artemis.llm.openai_acp_bridge import resolve_codex

                resolve_codex(request.codex_path.strip() or values.get("ARTEMIS_CODEX_PATH", ""))
            if request.provider == "openai_acp" and request.codex_path.strip():
                values["ARTEMIS_CODEX_PATH"] = request.codex_path.strip()
            if request.api_key and request.api_key.get_secret_value().strip():
                for key in PROVIDER_KEYS[request.provider]:
                    values[key] = request.api_key.get_secret_value().strip()
            if request.provider in {"openai", "custom", "ollama", "vllm"} and request.base_url:
                values["OPENAI_BASE_URL"] = request.base_url
            return document

        self.store.update("model", change, request.expected_version)
        return list(MODEL_ENV_KEYS)
