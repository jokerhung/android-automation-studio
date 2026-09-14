from importlib import resources
from unittest.mock import MagicMock

import pytest

from artemis.runtime.tray_app import (
    PystrayBackend,
    TrayApp,
    TrayCallbacks,
    TrayDependencyError,
    TrayView,
    load_tray_icon,
)


class FakeBackend:
    def __init__(self):
        self.items = []
        self.icon = MagicMock()

    def item(self, text, action, **kwargs):
        item = {"text": text, "action": action, **kwargs}
        self.items.append(item)
        return item

    def menu(self, *items):
        return items

    def build(self, name, title, image, menu):
        self.icon.name = name
        self.icon.title = title
        self.icon.icon = image
        self.icon.menu = menu
        return self.icon


def callbacks():
    return TrayCallbacks(*(MagicMock() for _ in range(4)))


def test_builds_exact_native_menu_and_dispatches_callbacks():
    backend = FakeBackend()
    actions = callbacks()
    app = TrayApp(actions, TrayView("running", 8009), backend=backend, image_loader=lambda s: s)

    icon = app.build()
    assert [item["text"] for item in backend.items] == ["Start", "Stop", "Open homepage", "Exit"]
    assert icon.name == "artemis-8009"
    assert icon.title == "ARTEMIS — Running · 8009"
    assert icon.icon == "running"
    assert backend.items[2]["default"] is True

    for item in backend.items:
        item["action"](None, None)
    actions.start.assert_called_once_with()
    actions.stop.assert_called_once_with()
    actions.open_homepage.assert_called_once_with()
    actions.exit.assert_called_once_with()


def test_menu_enablement_tracks_view_without_rebuilding():
    backend = FakeBackend()
    app = TrayApp(callbacks(), TrayView("stopped", 8009), backend=backend, image_loader=lambda s: s)
    app.build()
    enabled = [item["enabled"] for item in backend.items]
    assert [fn(None) for fn in enabled] == [True, False, True, True]

    app.update(TrayView("starting", 8009))
    assert [fn(None) for fn in enabled] == [False, False, False, False]
    app.update(TrayView("running", 8009))
    assert [fn(None) for fn in enabled] == [False, True, True, True]
    backend.icon.update_menu.assert_called()


def test_pystray_adapter_uses_compatible_api():
    module = MagicMock()
    backend = PystrayBackend(module)
    action = MagicMock()
    backend.item("Start", action, enabled=True)
    backend.menu("one", "two")
    backend.build("name", "title", "image", "menu")
    module.MenuItem.assert_called_once_with("Start", action, enabled=True)
    module.Menu.assert_called_once_with("one", "two")
    module.Icon.assert_called_once_with("name", "image", "title", "menu")


def test_loads_all_packaged_icons():
    for state in ["stopped", "starting", "running", "stopping", "error"]:
        image = load_tray_icon(state)
        assert image.mode == "RGBA"
        assert image.size == (64, 64)
        assert (
            resources.files("artemis.resources.tray")
            .joinpath(f"artemis-tray-{state}.png")
            .is_file()
        )


def test_missing_pystray_has_safe_error(monkeypatch):
    def fail(_name):
        raise ImportError

    monkeypatch.setattr("artemis.runtime.tray_app.import_module", fail)
    with pytest.raises(TrayDependencyError, match="pystray"):
        PystrayBackend()


def test_import_and_build_do_not_enter_native_event_loop():
    backend = FakeBackend()
    app = TrayApp(callbacks(), TrayView("running", 8009), backend=backend, image_loader=lambda s: s)
    app.build()
    backend.icon.run.assert_not_called()
