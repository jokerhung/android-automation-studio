import json
from unittest.mock import AsyncMock

import pytest

from artemis.core.diagnostics.probes.credentials_probe import LLMCredentialsProbe
from artemis.core.diagnostics.probes.runtime_probe import SystemConfigProbe
from artemis.core.diagnostics.schema import ProbeStatus
from admin_console.routers import system
from admin_console.services import settings_diagnostics_service as email_diagnostics


@pytest.mark.asyncio
async def test_selected_provider_and_config_come_from_sqlite(
    sqlite_model_store, monkeypatch, tmp_path
):
    store = sqlite_model_store
    store.update(
        "model",
        lambda doc: {
            "config": {
                "default": {
                    "provider": "openai",
                    "model": "sqlite-primary",
                    "fallback": {"provider": "openai", "model": "sqlite-backup"},
                }
            },
            "credentials": {
                "OPENAI_API_KEY": "sqlite-test-secret",
                "GOOGLE_API_KEY": "other-secret",
            },
        },
    )
    legacy = tmp_path / "artemis.jsonc"
    legacy.write_text('{"default":{"provider":"openai_acp","model":"stale"}}')
    monkeypatch.setattr("artemis.config.paths.get_config_path", lambda _: legacy)
    monkeypatch.setenv("OPENAI_API_KEY", "stale-env-secret")
    credentials = await LLMCredentialsProbe().probe()
    assert credentials.status == ProbeStatus.PASS
    assert credentials.metadata["provider"] == "openai"
    assert credentials.metadata["current_key"] == "sqlite-test-secret"
    assert "sqlite-test-secret" not in credentials.model_dump_json()
    assert "other-secret" not in credentials.model_dump_json()
    runtime = await SystemConfigProbe().probe()
    assert runtime.status == ProbeStatus.PASS
    assert runtime.metadata["planner_model"] == "sqlite-primary"
    assert runtime.metadata["database_path"] == str(store.path)
    # Corrupt legacy files do not affect an initialized database.
    legacy.write_text("{invalid")
    response = await system.get_model_config_and_env()
    assert response["storage"] == "sqlite"
    assert response["default_model"]["model"] == "sqlite-primary"
    assert "sqlite-test-secret" not in json.dumps(response)
    assert "stale-env-secret" not in json.dumps(response)


@pytest.mark.asyncio
async def test_unrelated_key_or_endpoint_does_not_make_selected_provider_ready(
    sqlite_model_store, monkeypatch
):
    store = sqlite_model_store
    store.update(
        "model",
        lambda doc: {
            "config": {"default": {"provider": "openai", "model": "selected"}},
            "credentials": {
                "GOOGLE_API_KEY": "other-secret",
                "OPENAI_BASE_URL": "https://proxy.example/v1",
            },
        },
    )
    monkeypatch.setenv("OPENAI_API_KEY", "stale-secret")
    result = await LLMCredentialsProbe().probe()
    assert result.status == ProbeStatus.FAIL
    assert result.metadata["current_key"] == ""
    assert ".env" not in result.description
    response = await system.get_model_config_and_env()
    assert (
        next(entry for entry in response["env_vars"] if entry["provider"] == "openai")["is_set"]
        is False
    )


@pytest.mark.asyncio
async def test_acp_selection_uses_database(sqlite_model_store, monkeypatch):
    sqlite_model_store.update(
        "model",
        lambda doc: {
            "config": {"default": {"provider": "openai_acp", "model": "codex"}},
            "credentials": {"ARTEMIS_CODEX_PATH": "C:/sqlite/codex.exe"},
        },
    )
    models = AsyncMock(return_value=["codex"])
    monkeypatch.setattr("artemis.llm.openai_acp.available_codex_models", models)
    result = await LLMCredentialsProbe().probe()
    assert result.status == ProbeStatus.PASS
    assert result.metadata["provider"] == "openai_acp"
    models.assert_awaited_once()
    models.side_effect = RuntimeError("private-internal-error")
    result = await LLMCredentialsProbe().probe()
    assert result.status == ProbeStatus.FAIL
    assert "private-internal-error" not in result.model_dump_json()


@pytest.mark.parametrize(
    "enabled,configured,expected",
    [
        (False, False, ProbeStatus.PASS),
        (True, False, ProbeStatus.WARN),
        (True, True, ProbeStatus.PASS),
    ],
)
def test_email_diagnostics_read_sqlite_without_exposing_password(
    sqlite_model_store, monkeypatch, enabled, configured, expected
):
    from admin_console.services.email_settings_service import EmailSettingsService
    from unittest.mock import Mock

    secret = Mock()
    secret.unprotect.return_value = "smtp-private-secret"
    monkeypatch.setattr(email_diagnostics.sys, "platform", "win32")
    monkeypatch.setattr(email_diagnostics, "create_secret_store", lambda: secret)
    sqlite_model_store.get_or_import(
        "email",
        lambda: {
            "settings": {
                "enabled": enabled,
                "smtp_host": "smtp.example.com",
                "sender_email": "sender@example.com",
                "smtp_username": "user",
            },
            "password": "Ynl0ZXM=" if configured else None,
        },
    )
    result = email_diagnostics.email_settings_probe()
    assert result.status == expected
    assert result.is_blocker is False
    assert result.metadata["ready"] is (enabled and configured)
    assert "smtp-private-secret" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_invalid_database_config_has_sanitized_error(sqlite_model_store):
    sqlite_model_store.update(
        "model",
        lambda doc: {
            "config": {"default": {"provider": "invalid-private-value", "model": "private-model"}},
            "credentials": {},
        },
    )
    result = await SystemConfigProbe().probe()
    assert result.status == ProbeStatus.FAIL
    assert "invalid-private-value" not in result.model_dump_json()
    assert "private-model" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_http_readiness_includes_email_without_mutating_cached_report(sqlite_model_store, monkeypatch):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from artemis.core.diagnostics.schema import SystemReadinessReport

    sqlite_model_store.update("model", lambda doc: {
        **doc, "credentials": {"GOOGLE_API_KEY": "test-private-key"},
    })
    sqlite_model_store.get_or_import("email", lambda: {"settings": {"enabled": False}, "password": None})
    probe = await LLMCredentialsProbe().probe()
    cached = SystemReadinessReport(
        overall_ready=True, blocker_count=1, passed_blocker_count=1,
        probes=[probe], timestamp=1,
    )
    monkeypatch.setattr(system.readiness_engine, "run_all", AsyncMock(return_value=cached))
    app = FastAPI()
    app.include_router(system.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get("/api/system/readiness?force=true")
    assert response.status_code == 200
    body = response.json()
    assert body["overall_ready"] is True
    assert {item["id"] for item in body["probes"]} == {"gemini_api_key", "email_settings"}
    assert "test-private-key" not in response.text
    assert "current_key" not in response.text
    assert len(cached.probes) == 1
