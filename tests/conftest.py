# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Repository-wide pytest fixtures and classification helpers.

The default test paths contain only deterministic tests.  Tests under the
integration and end-to-end trees remain directly runnable, and receive stable
markers here so callers can select them without relying on filename patterns.
"""

from pathlib import Path

import pytest

from artemis.drivers.mock.mock_driver import MockDeviceDriver


@pytest.fixture
def mock_driver():
    """Provide an isolated mock mobile driver."""
    return MockDeviceDriver(device_id="fixture-mock-device", width=1080, height=2400)


@pytest.fixture
def sqlite_model_store(tmp_path, monkeypatch):
    """Keep provider tests independent of the developer's saved credentials."""
    import os
    from artemis.config.settings import settings
    from artemis.config.sqlite_store import MODEL_ENV_KEYS, SettingsStore

    for name in MODEL_ENV_KEYS:
        if name in os.environ:
            monkeypatch.setenv(name, os.environ[name])
        else:
            monkeypatch.delenv(name, raising=False)
        if name in type(settings).model_fields:
            monkeypatch.setattr(settings, name, getattr(settings, name))
    store = SettingsStore(tmp_path / "settings.db")
    store.get_or_import("model", lambda: {
        "config": {"default": {"provider": "google", "model": "test-model",
            "fallback": {"provider": "google", "model": "test-backup"}}},
        "credentials": {"OPENAI_API_KEY": "test-endpoint-key"},
    })
    monkeypatch.setenv("DATA_ENGINE_DB_PATH", str(store.path))
    return store


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Attach test-layer markers according to the owning test directory."""
    for item in items:
        parts = Path(str(item.path)).parts
        if "integration" in parts:
            item.add_marker(pytest.mark.integration)
        if "e2e" in parts:
            item.add_marker(pytest.mark.e2e)
