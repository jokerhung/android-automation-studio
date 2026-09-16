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

"""Contract tests for release metadata and bundled runtime resources."""

from importlib.metadata import version
from pathlib import Path
import shutil
import uuid

import pytest

import artemis
from artemis import resources


@pytest.fixture
def resource_root():
    root = Path.cwd() / "test_outputs" / f"resources-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_public_version_comes_from_distribution_metadata():
    assert artemis.__version__ == version("artemis")


def test_source_tree_contains_complete_release_resources():
    config_path = resources.get_bundled_config_path("artemis.jsonc")
    showcase_path = Path(__file__).parents[2] / "apps" / "showcase_next" / "out"

    assert config_path is not None and config_path.is_file()
    assert showcase_path is not None and (showcase_path / "index.html").is_file()


def test_bundled_resource_accessors_require_complete_assets(resource_root, monkeypatch):
    resource_root = resource_root / "resources"
    config_dir = resource_root / "config"
    showcase_dir = resource_root / "showcase_next"
    config_dir.mkdir(parents=True)
    showcase_dir.mkdir()
    (config_dir / "artemis.jsonc").write_text("{}", encoding="utf-8")
    (showcase_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    monkeypatch.setattr(resources, "files", lambda _package: resource_root)

    assert resources.get_bundled_config_path("artemis.jsonc") == (config_dir / "artemis.jsonc")
    assert resources.get_bundled_config_path("missing.jsonc") is None
    assert resources.get_bundled_showcase_dist() == showcase_dir


def test_incomplete_showcase_resource_is_rejected(resource_root, monkeypatch):
    resource_root = resource_root / "resources"
    (resource_root / "showcase_next").mkdir(parents=True)
    monkeypatch.setattr(resources, "files", lambda _package: resource_root)

    assert resources.get_bundled_showcase_dist() is None


def test_bundled_frontend_can_be_selected_by_framework_directory(resource_root, monkeypatch):
    resource_root = resource_root / "resources"
    next_dir = resource_root / "showcase_next"
    next_dir.mkdir(parents=True)
    (next_dir / "index.html").write_text("<html>next</html>", encoding="utf-8")
    monkeypatch.setattr(resources, "files", lambda _package: resource_root)

    assert resources.get_bundled_showcase_dist("next") == next_dir
    with pytest.raises(ValueError):
        resources.get_bundled_showcase_dist("angular")


def test_manifest_can_identify_framework_in_legacy_bundle_location(resource_root, monkeypatch):
    resource_root = resource_root / "resources"
    showcase_dir = resource_root / "showcase_next"
    showcase_dir.mkdir(parents=True)
    (showcase_dir / "index.html").write_text("<html>next</html>", encoding="utf-8")
    (showcase_dir / "manifest.json").write_text(
        '{"framework": "next"}', encoding="utf-8"
    )
    monkeypatch.setattr(resources, "files", lambda _package: resource_root)

    assert resources.get_bundled_showcase_dist("next") == showcase_dir
    assert resources.get_bundled_showcase_dist() == showcase_dir


def test_bundled_frontend_rejects_unknown_framework():
    with pytest.raises(ValueError, match="Next.js"):
        resources.get_bundled_showcase_dist("react")
