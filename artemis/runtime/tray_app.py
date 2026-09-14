"""Native Windows tray shell with lazy pystray/Pillow loading.

Importing this module never creates an icon, opens a window, or changes OS
state. Callers supply lifecycle callbacks; daemon policy remains outside this
UI adapter.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module, resources
from typing import Any, Protocol

_ICON_PACKAGE = "artemis.resources.tray"
_ALLOWED_STATES = frozenset({"stopped", "starting", "running", "stopping", "error"})


class TrayDependencyError(RuntimeError):
    """Raised when the optional Windows tray backend cannot be loaded."""


@dataclass(frozen=True, slots=True)
class TrayCallbacks:
    start: Callable[[], None]
    stop: Callable[[], None]
    open_homepage: Callable[[], None]
    exit: Callable[[], None]


@dataclass(frozen=True, slots=True)
class TrayView:
    state: str
    port: int

    def __post_init__(self) -> None:
        if self.state not in _ALLOWED_STATES:
            raise ValueError(f"Unsupported tray state: {self.state!r}")
        if not 1 <= self.port <= 65535:
            raise ValueError("Invalid server port")

    @property
    def title(self) -> str:
        labels = {
            "stopped": "Stopped",
            "starting": "Starting…",
            "running": "Running",
            "stopping": "Stopping…",
            "error": "Server unavailable",
        }
        return f"ARTEMIS — {labels[self.state]} · {self.port}"


class TrayBackend(Protocol):
    def build(self, name: str, title: str, image: Any, menu: Any) -> Any: ...
    def item(self, text: str, action: Callable[..., None], **kwargs: Any) -> Any: ...
    def menu(self, *items: Any) -> Any: ...


class PystrayBackend:
    """Lazy adapter so non-Windows/test imports do not initialize GUI code."""

    def __init__(self, module: Any | None = None) -> None:
        if module is None:
            try:
                module = import_module("pystray")
            except (ImportError, OSError) as exc:
                raise TrayDependencyError(
                    "Windows tray support requires the 'pystray' package"
                ) from exc
        self._module = module

    def build(self, name: str, title: str, image: Any, menu: Any) -> Any:
        return self._module.Icon(name, image, title, menu)

    def item(self, text: str, action: Callable[..., None], **kwargs: Any) -> Any:
        return self._module.MenuItem(text, action, **kwargs)

    def menu(self, *items: Any) -> Any:
        return self._module.Menu(*items)


def load_tray_icon(state: str = "running", *, image_module: Any | None = None) -> Any:
    """Load a packaged PNG into Pillow without relying on a source-tree path."""
    if state not in _ALLOWED_STATES:
        raise ValueError(f"Unsupported tray state: {state!r}")
    if image_module is None:
        try:
            image_module = import_module("PIL.Image")
        except ImportError as exc:
            raise TrayDependencyError("Windows tray support requires Pillow") from exc
    resource = resources.files(_ICON_PACKAGE).joinpath(f"artemis-tray-{state}.png")
    with resources.as_file(resource) as path:
        with image_module.open(path) as source:
            return source.convert("RGBA").copy()


class TrayApp:
    """Four-item tray menu whose callbacks only dispatch supplied actions."""

    def __init__(
        self,
        callbacks: TrayCallbacks,
        view: TrayView,
        *,
        backend: TrayBackend | None = None,
        image_loader: Callable[[str], Any] = load_tray_icon,
    ) -> None:
        self.callbacks = callbacks
        self.view = view
        self.backend = backend or PystrayBackend()
        self.image_loader = image_loader
        self.icon: Any | None = None

    def _dispatch(self, action: Callable[[], None]) -> Callable[..., None]:
        def callback(*_args: Any) -> None:
            action()

        return callback

    def _enabled(self, item: str) -> Callable[[Any], bool]:
        def enabled(_item: Any) -> bool:
            state = self.view.state
            if item == "start":
                return state in {"stopped", "error"}
            if item == "stop":
                return state == "running"
            if item == "open":
                return state in {"running", "stopped", "error"}
            return state not in {"starting", "stopping"}

        return enabled

    def build(self) -> Any:
        menu = self.backend.menu(
            self.backend.item(
                "Start", self._dispatch(self.callbacks.start), enabled=self._enabled("start")
            ),
            self.backend.item(
                "Stop", self._dispatch(self.callbacks.stop), enabled=self._enabled("stop")
            ),
            self.backend.item(
                "Open homepage",
                self._dispatch(self.callbacks.open_homepage),
                enabled=self._enabled("open"),
                default=True,
            ),
            self.backend.item(
                "Exit", self._dispatch(self.callbacks.exit), enabled=self._enabled("exit")
            ),
        )
        self.icon = self.backend.build(
            f"artemis-{self.view.port}",
            self.view.title,
            self.image_loader(self.view.state),
            menu,
        )
        return self.icon

    def update(self, view: TrayView) -> None:
        self.view = view
        if self.icon is None:
            return
        self.icon.title = view.title
        self.icon.icon = self.image_loader(view.state)
        update_menu = getattr(self.icon, "update_menu", None)
        if update_menu is not None:
            update_menu()

    def run(self) -> None:
        """Enter the native event loop; the caller must invoke this explicitly."""
        icon = self.icon or self.build()
        icon.run()

    def stop(self) -> None:
        if self.icon is not None:
            self.icon.stop()
