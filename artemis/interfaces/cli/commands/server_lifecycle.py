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

"""CLI commands for Artemis server lifecycle management: restart, stop, and status."""

from __future__ import annotations

import datetime
import time
from typing import Annotated
import webbrowser

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import typer

from artemis.interfaces.cli.commands.ui import (
    ensure_showcase_built,
    load_session_reconciler,
    ui_command,
)
from artemis.config.paths import ROOT_DIR
from artemis.runtime.background_runtime import (
    WindowsTrayRuntimeAdapter,
    ensure_background_runtime,
)
from artemis.runtime.daemon_client import daemon_log_path
from artemis.runtime.server_lifecycle import read_server_info
from artemis.runtime.tray_controller import (
    ArtemisLifecycleAdapter,
    DaemonPresence,
    LifecycleStatus,
)

console = Console()


def _format_uptime(seconds: float | None) -> str:
    """Format seconds into human-friendly duration (e.g. 1h 23m 45s)."""
    if seconds is None:
        return "Unknown"
    sec = int(seconds)
    hours, remainder = divmod(sec, 3600)
    minutes, remainder_sec = divmod(remainder, 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{remainder_sec}s")
    return " ".join(parts)


def restart_command(
    host: Annotated[
        str,
        typer.Option(
            "--host",
            "-H",
            help=(
                "Bind host address for the UI server. Defaults to loopback; for remote "
                "access prefer a Tailscale/SSH tunnel over a wide bind."
            ),
        ),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to run the unified UI server on."),
    ] = 8000,
    open_browser: Annotated[
        bool,
        typer.Option(
            "--open/--no-open",
            help="Automatically open the Showcase UI in default web browser.",
        ),
    ] = True,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force kill previous server immediately without waiting for graceful exit.",
        ),
    ] = False,
    reload: Annotated[
        bool,
        typer.Option(
            "--reload/--no-reload",
            help="Enable uvicorn live auto-reload (for development).",
        ),
    ] = False,
    daemon: Annotated[
        bool,
        typer.Option(
            "--daemon/--foreground",
            "-d/-F",
            help=(
                "Run the new server as a detached background daemon (default) or attached "
                "to the current terminal. The daemon is launched via 'python -m' so the "
                "console-script executable is never pinned by a long-lived server "
                "(which would block 'uv sync' reinstalls on Windows)."
            ),
        ),
    ] = True,
) -> None:
    """Restart only an identity-verified Artemis daemon on the target port."""
    console.print()
    if reload and daemon:
        console.print("   [dim]ℹ --reload requested: switching to foreground mode.[/dim]")
        daemon = False
    console.print(
        Panel(
            f"[bold cyan]🔄 Artemis Server Restart[/bold cyan]\n"
            f"[dim]Verifying the Artemis instance on port {port}...[/dim]",
            border_style="cyan",
            expand=False,
        )
    )

    lifecycle = ArtemisLifecycleAdapter(host=host, port=port)
    current = lifecycle.status()
    if current.presence is DaemonPresence.PORT_CONFLICT:
        console.print(f"   [red]⚠ {current.detail} Refusing to stop or replace it.[/red]\n")
        raise typer.Exit(code=1)
    if current.presence is DaemonPresence.ARTEMIS:
        load_session_reconciler()
        console.print("   [yellow]🛑 Requesting verified graceful shutdown...[/yellow]")
        if not lifecycle.stop(timeout=12.0):
            console.print("   [red]⚠ Verified daemon did not stop; no PID was terminated.[/red]\n")
            raise typer.Exit(code=1)
    else:
        console.print(f"   [dim]ℹ No verified Artemis daemon found on port {port}.[/dim]")

    local_url = f"http://localhost:{port}"
    if daemon:
        ensure_showcase_built(console)
        tray = WindowsTrayRuntimeAdapter(workspace=ROOT_DIR)
        result = ensure_background_runtime(
            host=host,
            port=port,
            lifecycle=lifecycle,
            tray=tray,
            wait_timeout=60.0,
        )
        log_path = daemon_log_path(port)
        if not result.ok:
            console.print(
                f"   [red]❌ Background daemon did not become identity-verified.[/red]\n"
                f"   [dim]{result.detail}[/dim]\n"
                f"   📄 [dim]Check logs: {log_path}[/dim]\n"
            )
            raise typer.Exit(code=1)
        metadata = read_server_info(port) or {}
        pid = metadata.get("pid", "Unknown")
        console.print(
            f"   [bold green]✓ Artemis server running in background (PID: {pid})[/bold green]\n"
            f"   🌐 [cyan]{local_url}[/cyan]\n"
            f"   🛠️  [cyan]{local_url}/admin[/cyan]\n"
            f"   📄 [dim]Logs: {log_path}[/dim]\n"
        )
        if open_browser:
            webbrowser.open(local_url)
        return

    console.print("   [cyan]🚀 Launching Artemis in the current terminal...[/cyan]\n")
    ui_command(host=host, port=port, open_browser=open_browser, reload=reload)


def stop_command(
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port of the Artemis server to stop."),
    ] = 8000,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force kill immediately without waiting for graceful shutdown.",
        ),
    ] = False,
) -> None:
    """Stop the verified Artemis daemon; never terminate a port owner by PID."""
    console.print()
    lifecycle = ArtemisLifecycleAdapter(port=port)
    current = lifecycle.status()
    if current.presence is DaemonPresence.STOPPED:
        console.print(
            Panel(
                f"[dim]No verified Artemis daemon found on port {port}.[/dim]",
                title="ℹ Status",
                border_style="dim",
                expand=False,
            )
        )
        return
    if current.presence is not DaemonPresence.ARTEMIS:
        console.print(
            Panel(
                f"[bold red]⚠ {current.detail}[/bold red]\n\n"
                "Refusing to terminate an unverified process.",
                title="⚠ Port Conflict",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(code=1)
    if force:
        console.print(
            "   [dim]ℹ --force does not bypass daemon identity or graceful shutdown.[/dim]"
        )
    load_session_reconciler()
    if not lifecycle.stop(timeout=12.0):
        console.print("   [red]⚠ Verified daemon did not stop; no PID was terminated.[/red]")
        raise typer.Exit(code=1)
    console.print(
        Panel(
            "[bold green]✓ Artemis server stopped gracefully.[/bold green]",
            title="🛑 Server Stopped",
            border_style="green",
            expand=False,
        )
    )


def status_command(
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to query for Artemis server status."),
    ] = 8000,
) -> None:
    """Display identity-aware Artemis daemon status for the target port."""
    console.print()
    lifecycle = ArtemisLifecycleAdapter(port=port)
    state: LifecycleStatus = lifecycle.status()
    metadata = read_server_info(port) or {}
    if state.presence is DaemonPresence.ARTEMIS:
        uptime = None
        if isinstance(metadata.get("started_at"), (int, float)):
            uptime = max(0.0, time.time() - metadata["started_at"])
        started_at = "Unknown"
        if metadata.get("started_at"):
            try:
                started_at = datetime.datetime.fromtimestamp(metadata["started_at"]).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except (TypeError, ValueError, OSError, OverflowError):
                pass
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_row(
            "[bold cyan]Status[/bold cyan]", "[bold green]● VERIFIED ARTEMIS[/bold green]"
        )
        table.add_row(
            "[bold cyan]PID[/bold cyan]", f"[yellow]{metadata.get('pid', 'Unknown')}[/yellow]"
        )
        table.add_row("[bold cyan]Port[/bold cyan]", f"[white]{port}[/white]")
        table.add_row("[bold cyan]Uptime[/bold cyan]", f"[white]{_format_uptime(uptime)}[/white]")
        table.add_row("[bold cyan]Started At[/bold cyan]", f"[dim]{started_at}[/dim]")
        table.add_row("[bold cyan]Showcase UI[/bold cyan]", f"[cyan]http://localhost:{port}[/cyan]")
        if metadata.get("cwd"):
            table.add_row("[bold cyan]Workspace[/bold cyan]", f"[dim]{metadata['cwd']}[/dim]")
        console.print(
            Panel(table, title="🚀 Artemis Server Status", border_style="green", expand=False)
        )
        return
    if state.presence is DaemonPresence.PORT_CONFLICT:
        console.print(
            Panel(
                f"[bold red]● PORT CONFLICT[/bold red]\n\n{state.detail}\n"
                "[dim]No process ownership or Artemis status is inferred from port liveness alone.[/dim]",
                title="⚠ Artemis Server Status",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(code=1)
    console.print(
        Panel(
            f"[dim]○ OFFLINE / STOPPED[/dim]\n\nNo Artemis daemon is listening on port {port}.",
            title="ℹ Artemis Server Status",
            border_style="dim",
            expand=False,
        )
    )
