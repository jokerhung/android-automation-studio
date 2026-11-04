import io
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from httpx import ASGITransport, AsyncClient
import pytest

from admin_console.services.model_settings_service import ModelSettingsService, ModelSettingsUpdate
from admin_console.routers import model_settings as router
from apps.admin_console.server import app
from artemis.utils.file import load_jsonc


@pytest.fixture
def service(tmp_path):
    config = tmp_path / "artemis.jsonc"
    config.write_text(
        """{
  // Keep my comment
  "default": {"provider":"google","model":"old","thinking_level":"medium","fallback":{"provider":"google","model":"backup"}},
  "nodes": {"operator":{"temperature":0.5}},
  "agent": {"flash":{"max_turns":8}}
}""",
        encoding="utf-8",
    )
    env = tmp_path / ".env"
    env.write_text(
        "# User settings\nOPENAI_API_KEY='old-test-key'\nUNRELATED=unchanged\n", encoding="utf-8"
    )
    return ModelSettingsService(config, env)


def payload(service, **kw):
    return ModelSettingsUpdate(
        expected_version=service.get()["version"],
        provider="openai",
        default_model="my-model",
        fallback_model="my-fallback",
        base_url="https://proxy.example/api/v1",
        confirm_restart=True,
        **kw,
    )


def test_saves_models_and_credentials_only_in_sqlite_without_exposing_key(service):
    value = service.get()
    assert "old-test-key" not in json.dumps(value)
    old_config = service.config_path.read_bytes()
    old_env = service.env_path.read_bytes()
    service.save(payload(service, api_key="new#key'with\\quotes"))
    document, _ = service.store.model()
    config, env = document["config"], document["credentials"]
    assert config["nodes"] == {"operator": {"temperature": 0.5}}
    assert config["default"]["provider"] == "openai"
    assert "thinking_level" not in config["default"]
    assert config["default"]["fallback"]["api_base"] == "https://proxy.example/api/v1"
    assert env["OPENAI_API_KEY"] == "new#key'with\\quotes"
    assert env["OPENAI_BASE_URL"] == "https://proxy.example/api/v1"
    assert service.config_path.read_bytes() == old_config
    assert service.env_path.read_bytes() == old_env
    assert "new#key" not in json.dumps(service.get())
    assert service.get()["storage"] == "sqlite"


def test_blank_key_keeps_key_and_stale_version_cannot_write(service):
    request = payload(service, api_key="")
    service.save(request)
    assert service.store.model()[0]["credentials"]["OPENAI_API_KEY"] == "old-test-key"
    with pytest.raises(FileExistsError):
        service.save(request)


def test_transaction_failure_does_not_change_config_or_credentials(service):
    previous = service.store.model()

    def fail(document):
        document["credentials"]["OPENAI_API_KEY"] = "must-not-persist"
        raise ValueError("failed before commit")

    with pytest.raises(ValueError):
        service.store.update("model", fail)
    assert service.store.model() == previous


def test_migration_is_once_and_database_survives_removed_legacy_files(service):
    service.save(payload(service, api_key="database-key"))
    service.env_path.write_text("OPENAI_API_KEY=stale-file-key", encoding="utf-8")
    assert service.store.model()[0]["credentials"]["OPENAI_API_KEY"] == "database-key"
    service.env_path.unlink()
    service.config_path.unlink()
    reopened = ModelSettingsService(service.config_path, service.env_path, store=service.store)
    assert reopened.get()["default_model"] == "my-model"
    assert reopened.get()["keys_configured"]["openai"] is True


@pytest.mark.parametrize(
    "url", ["file:///tmp/config", "https://user:secret@host/v1", "https://host/v1?key=secret"]
)
def test_rejects_unsafe_urls(service, url):
    data = payload(service).model_dump()
    data["base_url"] = url
    with pytest.raises(ValueError):
        ModelSettingsUpdate.model_validate(data)


@pytest.mark.asyncio
async def test_api_never_echoes_invalid_secret():
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 1234)), base_url="http://localhost"
    ) as client:
        result = await client.put(
            "/api/settings/model", json={"api_key": "secret-do-not-echo", "provider": "invalid"}
        )
    assert result.status_code == 422
    assert "secret-do-not-echo" not in result.text


@pytest.mark.asyncio
async def test_busy_task_blocks_save_and_restart(service, monkeypatch):
    monkeypatch.setattr(
        app.state, "uvicorn_server", SimpleNamespace(should_exit=False), raising=False
    )
    monkeypatch.setattr(router.state, "is_draining", True)
    factory = Mock(return_value=service)
    monkeypatch.setattr(router, "ModelSettingsService", factory)
    with patch.object(router, "launch_restart") as launch:
        async with AsyncClient(
            transport=ASGITransport(app=app, client=("127.0.0.1", 1234)),
            base_url="http://localhost",
        ) as client:
            response = await client.put(
                "/api/settings/model", json=payload(service).model_dump(mode="json")
            )
    assert response.status_code == 409
    factory.assert_not_called()
    launch.assert_not_called()


@pytest.mark.asyncio
async def test_remote_can_change_models_when_server_is_lan_bound(monkeypatch):
    monkeypatch.setattr(router.state, "host", "0.0.0.0")
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("192.168.1.50", 1234)), base_url="http://localhost"
    ) as client:
        response = await client.put("/api/settings/model", json={})
    # The request reaches payload validation, proving the LAN peer is no
    # longer rejected by the loopback-only guard.
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_remote_cannot_change_models_when_server_is_loopback(monkeypatch):
    monkeypatch.setattr(router.state, "host", "127.0.0.1")
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("192.168.1.50", 1234)), base_url="http://localhost"
    ) as client:
        response = await client.put("/api/settings/model", json={})
    assert response.status_code == 403


def test_restart_drops_old_inherited_values(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "stale-secret")
    monkeypatch.setattr(router, "daemon_log_path", lambda port: tmp_path / "restart.log")
    with patch.object(router.subprocess, "Popen") as launch:
        router.launch_restart(8009, "127.0.0.1", ["OPENAI_API_KEY"])
    assert "OPENAI_API_KEY" not in launch.call_args.kwargs["env"]
    assert "stale-secret" not in str(launch.call_args.args)
    assert "--port" in launch.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("restart_fails", [False, True])
async def test_save_then_restart_idle_server(service, monkeypatch, restart_fails):
    server = SimpleNamespace(should_exit=False)
    monkeypatch.setattr(app.state, "uvicorn_server", server, raising=False)
    monkeypatch.setattr(router.state, "is_draining", False)
    monkeypatch.setattr(router.state, "is_shutting_down", False)
    monkeypatch.setattr(router.state, "queue_items", [])
    monkeypatch.setattr(router.state, "active_runs", {})
    monkeypatch.setattr(router.state, "current_process", None)
    monkeypatch.setattr(router.email_notification_service, "_inflight", set())
    monkeypatch.setattr(router.email_notification_service, "accepting_deliveries", True)
    monkeypatch.setattr(router, "ModelSettingsService", lambda: service)
    with (
        patch.object(
            router, "launch_restart", side_effect=OSError if restart_fails else None
        ) as launch,
        patch.object(router, "schedule_shutdown") as shutdown,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app, client=("127.0.0.1", 1234)),
            base_url="http://localhost",
        ) as client:
            response = await client.put(
                "/api/settings/model", json=payload(service).model_dump(mode="json")
            )
    assert response.status_code == 200
    assert service.get()["default_model"] == "my-model"
    launch.assert_called_once()
    if restart_fails:
        assert response.json()["status"] == "saved_restart_failed"
        shutdown.assert_not_called()
        assert not router.state.is_draining
    else:
        assert response.json()["status"] == "restarting"
        shutdown.assert_called_once_with(server)
        assert router.state.is_draining


def test_jsonc_preserves_url_and_escaped_string():
    source = r"""{ // comment
      "url": "https://proxy.example/v1", /* block */
      "text": "say \"hello//world\"", "literal": "/* not comment */"
    }"""
    parsed = load_jsonc(io.StringIO(source))
    assert parsed["url"] == "https://proxy.example/v1"
    assert parsed["text"] == 'say "hello//world"'
    assert parsed["literal"] == "/* not comment */"


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_textboxes_preserve_saved_model_settings(service, blank):
    service.save(payload(service, api_key="saved-test-key", fallback_url="https://backup.example/v1"))
    service.store.update("model", lambda doc: {
        **doc, "credentials": {**doc["credentials"], "ARTEMIS_CODEX_PATH": "C:/tools/codex.exe"}
    })
    before, _ = service.store.model()
    service.save(ModelSettingsUpdate(
        expected_version=service.get()["version"], provider="openai",
        default_model=blank, fallback_model=blank, base_url=blank,
        fallback_url=blank, api_key=blank, codex_path=blank, confirm_restart=True,
    ))
    after, _ = service.store.model()
    assert after == before
    service.save(ModelSettingsUpdate(
        expected_version=service.get()["version"], provider="openai",
        default_model="updated", fallback_model=blank, base_url=blank,
        fallback_url=blank, api_key=blank, confirm_restart=True,
    ))
    assert service.get()["default_model"] == "updated"
    assert service.get()["fallback_model"] == "my-fallback"
    assert service.get()["base_url"] == "https://proxy.example/api/v1"
