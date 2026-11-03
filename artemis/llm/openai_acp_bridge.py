"""ACP stdio agent backed by the installed Codex app-server.

This file is also an executable worker. Keep its imports stdlib-only so stdout
contains ACP JSON-RPC exclusively, without Artemis startup logging.
"""

import asyncio
import contextlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid


def resolve_codex(path: str = "") -> str:
    candidate = path or os.environ.get("ARTEMIS_CODEX_PATH", "") or shutil.which("codex")
    if not candidate and sys.platform == "win32":
        candidate = str(
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/OpenAI/Codex/bin/codex.exe"
        )
    resolved = shutil.which(candidate) if candidate else None
    if not resolved or not Path(resolved).is_file():
        raise ValueError("Codex CLI was not found. Install Codex or set its executable path.")
    if Path(resolved).suffix.lower() in {".cmd", ".bat", ".ps1"}:
        raise ValueError("Select the native Codex executable, not a shell wrapper.")
    return resolved


class RpcProcess:
    """One sequential JSON-RPC connection with notification handling."""

    def __init__(self, command, env=None):
        self.command, self.env = command, env
        self.process = None
        self.sequence = 0

    async def __aenter__(self):
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=self.env,
            limit=32 * 1024 * 1024,
            **flags,
        )
        return self

    async def __aexit__(self, *args):
        if self.process is None:
            return
        if self.process.stdin:
            self.process.stdin.close()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=3)
        except TimeoutError:
            if sys.platform == "win32" and self.process.returncode is None:
                # A prompt may still be running in the worker's Codex child.
                # Terminate that worker tree, never the user's shared daemon.
                with contextlib.suppress(OSError, TimeoutError):
                    killer = await asyncio.create_subprocess_exec(
                        "taskkill",
                        "/F",
                        "/T",
                        "/PID",
                        str(self.process.pid),
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    await asyncio.wait_for(killer.wait(), timeout=5)
            with contextlib.suppress(ProcessLookupError):
                self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=3)
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    self.process.kill()
                await self.process.wait()

    async def send(self, value):
        self.process.stdin.write((json.dumps(value, ensure_ascii=False) + "\n").encode())
        await self.process.stdin.drain()

    async def read(self):
        line = await self.process.stdout.readline()
        if not line:
            raise RuntimeError(
                "Codex ACP connection closed unexpectedly. Check Codex login and configuration."
            )
        return json.loads(line)

    async def request(self, method, params, on_notification=None):
        self.sequence += 1
        identifier = self.sequence
        await self.send({"jsonrpc": "2.0", "id": identifier, "method": method, "params": params})
        while True:
            value = await self.read()
            if value.get("method"):
                await self.handle_event(value, on_notification)
            elif value.get("id") == identifier:
                if "error" in value:
                    raise ValueError(value["error"].get("message", "Codex ACP request failed."))
                return value.get("result", {})

    async def handle_event(self, value, callback=None):
        if "id" in value:
            # Codex is used as a model, never as a second device/host operator.
            await self.send(
                {
                    "id": value["id"],
                    "error": {
                        "code": -32601,
                        "message": "Host tools are disabled in Artemis model mode.",
                    },
                }
            )
        elif callback:
            await callback(value)


class CodexAcpAgent:
    def __init__(self, codex):
        self.codex = codex
        self.sessions = {}
        self.workspaces = []

    async def start(self):
        # Artemis API/proxy credentials must not override the CLI's own login.
        environment = os.environ.copy()
        for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "CODEX_API_KEY"):
            environment.pop(key, None)
        self.rpc = RpcProcess(
            [
                self.codex,
                "app-server",
                "--stdio",
                "-c",
                "features.shell_tool=false",
                "-c",
                "features.multi_agent=false",
                "-c",
                "features.hooks=false",
                "-c",
                "mcp_servers={}",
            ],
            env=environment,
        )
        await self.rpc.__aenter__()
        await self.rpc.request(
            "initialize", {"clientInfo": {"name": "artemis_acp", "version": "1.0"}}
        )
        await self.rpc.send({"method": "initialized", "params": {}})

    async def models(self):
        account = await self.rpc.request("account/read", {"refreshToken": False})
        if not account.get("account") and account.get("requiresOpenaiAuth", True):
            raise ValueError("Codex is not signed in. Run codex login on the server computer.")
        result, cursor = [], None
        for _ in range(100):
            page = await self.rpc.request(
                "model/list", {"limit": 100, **({"cursor": cursor} if cursor else {})}
            )
            result.extend(page.get("data", []))
            next_cursor = page.get("nextCursor")
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        return result

    async def dispatch(self, method, params):
        if method == "initialize":
            if params.get("protocolVersion") != 1:
                raise ValueError("Unsupported ACP protocol version.")
            return {
                "protocolVersion": 1,
                "agentInfo": {"name": "openai-acp", "title": "OpenAI ACP", "version": "1.0"},
                "agentCapabilities": {"promptCapabilities": {"image": True}},
                "authMethods": [],
            }
        if method == "session/new":
            models = await self.models()
            if not models:
                raise ValueError("Codex returned no available models.")
            selected = next((m for m in models if m.get("isDefault")), models[0])
            session_id = str(uuid.uuid4())
            self.sessions[session_id] = selected.get("model", selected["id"])
            return {
                "sessionId": session_id,
                "models": {
                    "currentModelId": self.sessions[session_id],
                    "availableModels": [
                        {"modelId": m.get("model", m["id"]), "name": m.get("displayName", m["id"])}
                        for m in models
                    ],
                },
            }
        session_id = params.get("sessionId")
        if session_id not in self.sessions:
            raise ValueError("Unknown ACP session.")
        if method == "session/set_model":
            self.sessions[session_id] = params["modelId"]
            return {}
        if method == "session/prompt":
            return await self.prompt(session_id, params)
        raise ValueError("Unsupported ACP method.")

    async def prompt(self, session_id, params):
        # Isolated ephemeral threads keep CLI repo instructions out of model calls.
        workspace = tempfile.TemporaryDirectory(prefix="artemis-acp-", ignore_cleanup_errors=True)
        self.workspaces.append(workspace)
        cwd = workspace.name
        thread = await self.rpc.request(
            "thread/start",
            {
                "model": self.sessions[session_id],
                "cwd": cwd,
                "ephemeral": True,
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "baseInstructions": "You are a model inside Artemis. Follow the supplied conversation and output instructions. Never execute host commands, access files, or call Codex tools. Artemis executes all requested tools itself.",
            },
        )
        thread_id = thread["thread"]["id"]
        content = []
        for block in params["prompt"]:
            if block["type"] == "text":
                content.append({"type": "text", "text": block["text"]})
            elif block["type"] == "image":
                content.append(
                    {"type": "image", "url": f"data:{block['mimeType']};base64,{block['data']}"}
                )
            else:
                raise ValueError("OpenAI ACP supports text and image prompt blocks only.")
        options = params.get("_meta", {}).get("artemis", {})
        turn_options = {"threadId": thread_id, "input": content}
        if options.get("outputSchema"):
            turn_options["outputSchema"] = options["outputSchema"]
        if options.get("effort"):
            turn_options["effort"] = options["effort"]
        completed = None
        usage = None

        async def event(value):
            nonlocal completed, usage
            data = value.get("params", {})
            if data.get("threadId") != thread_id:
                return
            if (
                value["method"] == "item/completed"
                and data.get("item", {}).get("type") == "agentMessage"
            ):
                emit(
                    {
                        "jsonrpc": "2.0",
                        "method": "session/update",
                        "params": {
                            "sessionId": session_id,
                            "update": {
                                "sessionUpdate": "agent_message_chunk",
                                "content": {"type": "text", "text": data["item"].get("text", "")},
                            },
                        },
                    }
                )
            if value["method"] == "turn/completed":
                completed = data["turn"]
            if value["method"] == "thread/tokenUsage/updated":
                usage = data.get("tokenUsage", {}).get("last")

        await self.rpc.request("turn/start", turn_options, event)
        while completed is None:
            await self.rpc.handle_event(await self.rpc.read(), event)
        if completed.get("status") != "completed":
            error = completed.get("error") or {}
            raise ValueError(error.get("message", "Codex generation failed."))
        return {"stopReason": "end_turn", "_meta": {"artemis": {"usage": usage}}}


def emit(value):
    sys.stdout.buffer.write((json.dumps(value, ensure_ascii=False) + "\n").encode())
    sys.stdout.buffer.flush()


async def main():
    agent = CodexAcpAgent(resolve_codex(sys.argv[1] if len(sys.argv) > 1 else ""))
    try:
        await agent.start()
        while line := await asyncio.to_thread(sys.stdin.buffer.readline):
            request = json.loads(line)
            if "id" not in request:
                continue
            try:
                result = await agent.dispatch(request["method"], request.get("params", {}))
                emit({"jsonrpc": "2.0", "id": request["id"], "result": result})
            except Exception as error:
                emit(
                    {
                        "jsonrpc": "2.0",
                        "id": request["id"],
                        "error": {"code": -32603, "message": str(error)},
                    }
                )
    finally:
        if hasattr(agent, "rpc"):
            await agent.rpc.__aexit__(None, None, None)
        for workspace in agent.workspaces:
            workspace.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
