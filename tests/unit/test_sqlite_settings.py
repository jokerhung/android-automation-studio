from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from artemis.config.sqlite_store import SettingsStore
from apps.admin_console.services.model_settings_service import (
    ModelSettingsService,
    ModelSettingsUpdate,
)


def configured_store(tmp_path):
    config = tmp_path / "artemis.jsonc"
    config.write_text(
        json.dumps(
            {
                "default": {
                    "provider": "openai",
                    "model": "legacy",
                    "fallback": {"provider": "openai", "model": "legacy-fallback"},
                }
            }
        ),
        encoding="utf-8",
    )
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=imported-key\n", encoding="utf-8")
    store = SettingsStore(tmp_path / "settings.db")
    service = ModelSettingsService(config, env, store=store)
    service.save(
        ModelSettingsUpdate(
            expected_version=service.get()["version"],
            provider="openai",
            default_model="database-model",
            fallback_model="database-fallback",
            base_url="https://database.example/v1",
            api_key="database-key",
            confirm_restart=True,
        )
    )
    return service


def test_separate_task_process_uses_sqlite_even_with_stale_files_and_inherited_key(tmp_path):
    service = configured_store(tmp_path)
    # A scheduled/manual worker starts with a different CWD and an inherited
    # environment. Neither may override settings saved through the console.
    service.config_path.write_text("not valid JSON", encoding="utf-8")
    service.env_path.write_text(
        "OPENAI_API_KEY=stale-file-key\nOPENAI_BASE_URL=https://stale.example/v1\n",
        encoding="utf-8",
    )
    script = """
from unittest.mock import patch
from artemis.config.llm import initialize_llm_config
from artemis.config.settings import settings
from artemis.llm.router import ModelEndpoint, ModelFactory
cfg = initialize_llm_config()
assert cfg.operator.model == "database-model"
assert cfg.operator.fallback.model == "database-fallback"
assert settings.get_api_key("openai").get_secret_value() == "database-key"
with patch("langchain_openai.ChatOpenAI") as client:
    ModelFactory.get_model(ModelEndpoint(provider=cfg.operator.provider, model_name=cfg.operator.model, api_base=cfg.operator.api_base))
    assert client.call_args.kwargs["api_key"] == "database-key"
    assert client.call_args.kwargs["base_url"] == "https://database.example/v1"
print("SQLITE_TASK_OK")
"""
    root = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "DATA_ENGINE_DB_PATH": str(service.store.path),
        "OPENAI_API_KEY": "stale-inherited-key",
        "PYTHONPATH": str(root),
        "PYTHONUTF8": "1",
        "ARTEMIS_FAKE_LLM": "0",
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    assert "SQLITE_TASK_OK" in result.stdout


def test_rotated_database_key_invalidates_model_client_cache(
    tmp_path, monkeypatch, sqlite_model_store
):
    from unittest.mock import patch
    from artemis.llm.router import ModelEndpoint, ModelFactory

    service = configured_store(tmp_path)
    monkeypatch.setenv("DATA_ENGINE_DB_PATH", str(service.store.path))
    monkeypatch.setenv("ARTEMIS_FAKE_LLM", "0")
    monkeypatch.setattr(ModelFactory, "_cache", {})
    endpoint = ModelEndpoint(provider="openai", model_name="database-model")
    with patch("langchain_openai.ChatOpenAI") as client:
        ModelFactory.get_model(endpoint)
        assert client.call_args.kwargs["api_key"] == "database-key"

        def rotate(document):
            document["credentials"]["OPENAI_API_KEY"] = "rotated-key"
            return document

        service.store.update("model", rotate)
        ModelFactory.get_model(endpoint)
        assert client.call_count == 2
        assert client.call_args.kwargs["api_key"] == "rotated-key"


def test_concurrent_settings_saves_allow_only_one_version_winner(tmp_path):
    service = configured_store(tmp_path)
    version = service.get()["version"]

    def save(index):
        def change(document):
            document["config"]["default"]["model"] = f"winner-{index}"
            return document

        try:
            SettingsStore(service.store.path).update("model", change, version)
            return True
        except FileExistsError:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(save, range(4))) == 1
    assert int(service.get()["version"]) == int(version) + 1


def test_missing_database_does_not_turn_import_failure_into_empty_settings(tmp_path):
    store = SettingsStore(tmp_path / "settings.db")
    config = tmp_path / "broken.jsonc"
    config.write_text("invalid JSON", encoding="utf-8")
    with pytest.raises(ValueError):
        store.model(config)
    config.write_text('{"default":{"model":"fixed"}}', encoding="utf-8")
    assert store.model(config)[0]["config"]["default"]["model"] == "fixed"


@pytest.mark.parametrize("ingress", ["frontend", "schedule"])
def test_task_launcher_pins_shared_sqlite_and_drops_inherited_credentials(
    sqlite_model_store, monkeypatch, ingress
):
    from apps.admin_console.services.task_queue_service import TaskQueueService
    from artemis.runtime.adb_endpoint import AdbEndpoint, AdbTarget

    monkeypatch.setenv("OPENAI_API_KEY", "stale-parent-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://stale-parent.example/v1")
    command, env = TaskQueueService._build_worker_invocation(
        {"ingress": ingress}, "run-key", "session-id", "Test goal", "flash",
        AdbTarget(AdbEndpoint.local(), "test-device"),
    )
    assert env["DATA_ENGINE_DB_PATH"] == str(sqlite_model_store.path.resolve())
    assert env["ARTEMIS_TASK_INGRESS"] == ingress
    assert "OPENAI_API_KEY" not in env and "OPENAI_BASE_URL" not in env
    assert "stale-parent-key" not in command
