"""LangChain model using ACP and the machine's existing Codex installation."""

import asyncio
import json
from pathlib import Path
import sys
from typing import Any
import uuid

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, Field

from artemis.llm.openai_acp_bridge import RpcProcess, resolve_codex


class AcpRequestError(ValueError):
    status_code = 400


class AcpSession:
    def __init__(self, codex_path="", timeout=120):
        self.codex_path, self.timeout = codex_path, timeout

    async def __aenter__(self):
        path = resolve_codex(self.codex_path)
        self.rpc = RpcProcess(
            [sys.executable, str(Path(__file__).with_name("openai_acp_bridge.py")), path]
        )
        try:
            await self.rpc.__aenter__()
            await self.request("initialize", {"protocolVersion": 1, "clientCapabilities": {}})
            self.session = await self.request(
                "session/new", {"cwd": str(Path.cwd()), "mcpServers": []}
            )
            return self
        except BaseException:
            await self.rpc.__aexit__(None, None, None)
            raise

    async def __aexit__(self, *args):
        await self.rpc.__aexit__(*args)

    async def request(self, method, params, callback=None):
        return await asyncio.wait_for(self.rpc.request(method, params, callback), self.timeout)

    async def prompt(self, model, content, schema=None, effort=None):
        session_id = self.session["sessionId"]
        await self.request("session/set_model", {"sessionId": session_id, "modelId": model})
        parts = []

        async def update(value):
            params = value.get("params", {})
            item = params.get("update", {})
            if (
                value.get("method") == "session/update"
                and params.get("sessionId") == session_id
                and item.get("sessionUpdate") == "agent_message_chunk"
            ):
                parts.append(item["content"].get("text", ""))

        result = await self.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": content,
                "_meta": {"artemis": {"outputSchema": schema, "effort": effort}},
            },
            update,
        )
        if result.get("stopReason") != "end_turn" or not parts:
            raise RuntimeError("Codex ACP did not return a completed response.")
        self.usage = result.get("_meta", {}).get("artemis", {}).get("usage")
        return "\n".join(parts)


async def available_codex_models(codex_path=""):
    async with asyncio.timeout(20), AcpSession(codex_path, timeout=15) as session:
        return [item["modelId"] for item in session.session["models"]["availableModels"]]


class OpenAIAcpChatModel(BaseChatModel):
    model_name: str
    codex_path: str = ""
    timeout_seconds: float = 120
    reasoning_effort: str | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: Any = None

    @property
    def _llm_type(self):
        return "openai-acp"

    @property
    def _identifying_params(self):
        return {"model_name": self.model_name, "provider": "openai_acp"}

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self.model_copy(
            update={
                "tools": [convert_to_openai_tool(tool) for tool in tools],
                "tool_choice": tool_choice,
            }
        )

    def with_structured_output(self, schema, *, include_raw=False, **kwargs):
        is_pydantic = isinstance(schema, type) and issubclass(schema, BaseModel)
        json_schema = schema.model_json_schema() if is_pydantic else schema

        def parse(message):
            try:
                value = json.loads(message.content)
                parsed = schema.model_validate(value) if is_pydantic else value
                return (
                    {"raw": message, "parsed": parsed, "parsing_error": None}
                    if include_raw
                    else parsed
                )
            except Exception as error:
                if include_raw:
                    return {"raw": message, "parsed": None, "parsing_error": error}
                raise

        return self.bind(response_schema=json_schema) | RunnableLambda(parse)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._agenerate(messages, stop=stop, **kwargs))
        raise RuntimeError("Use ainvoke for OpenAI ACP inside an event loop.")

    async def _agenerate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        conversation, images = [], []
        for message in messages:
            blocks = []
            content = message.content
            if isinstance(content, str):
                blocks.append(content)
            else:
                for block in content:
                    if isinstance(block, str):
                        blocks.append(block)
                    elif block.get("type") == "text":
                        blocks.append(block.get("text", ""))
                    elif block.get("type") in {"image_url", "image"}:
                        url = block.get("image_url", {})
                        url = url.get("url", "") if isinstance(url, dict) else url
                        if not url and block.get("source_type") == "base64":
                            url = f"data:{block.get('mime_type', 'image/png')};base64,{block.get('data', '')}"
                        if (
                            not isinstance(url, str)
                            or not url.startswith("data:image/")
                            or ";base64," not in url
                        ):
                            raise AcpRequestError(
                                "OpenAI ACP requires inline base64 image inputs; video and remote image URLs are not supported."
                            )
                        header, data = url.split(";base64,", 1)
                        images.append({"type": "image", "mimeType": header[5:], "data": data})
                        blocks.append(f"[Attached image {len(images)}]")
                    elif block.get("type") not in {"thinking", "reasoning"}:
                        raise AcpRequestError("OpenAI ACP supports text and image content only.")
            entry = {"role": message.type, "content": "\n".join(blocks)}
            if getattr(message, "tool_calls", None):
                entry["tool_calls"] = message.tool_calls
            if getattr(message, "tool_call_id", None):
                entry["tool_call_id"] = message.tool_call_id
            conversation.append(entry)
        schema = kwargs.get("response_schema")
        structured_schema = schema
        tools = self.tools if self.tool_choice != "none" else []
        instruction = "Continue the following conversation as its assistant. Respond only to the latest turn.\n"
        if tools and schema is None:
            schema = {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "tool_calls": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "enum": [tool["function"]["name"] for tool in tools],
                                },
                                "arguments": {
                                    "type": "string",
                                    "description": "JSON object containing the tool arguments",
                                },
                            },
                            "required": ["name", "arguments"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["content", "tool_calls"],
                "additionalProperties": False,
            }
            instruction += "Return content and tool_calls as JSON. Request tools by name and JSON-encoded arguments. Never execute them yourself. Use an empty tool_calls array when no tool is needed.\n"
            instruction += (
                "Tool choice: "
                + json.dumps(self.tool_choice)
                + "\nAvailable tools: "
                + json.dumps(tools, ensure_ascii=False)
                + "\n"
            )
        if structured_schema is not None:
            # Arbitrary Pydantic schemas (optional fields, maps, $defs) need not
            # satisfy Codex's strict response-format subset. Carry their JSON in
            # a strict envelope, then let the caller's Pydantic parser validate.
            instruction += (
                "The json field must contain a JSON-encoded value matching this requested schema: "
                + json.dumps(structured_schema, ensure_ascii=False)
                + "\n"
            )
            schema = {
                "type": "object",
                "properties": {"json": {"type": "string"}},
                "required": ["json"],
                "additionalProperties": False,
            }
        if schema is not None:
            instruction += (
                "Your final answer must conform to this JSON schema: "
                + json.dumps(schema, ensure_ascii=False)
                + "\n"
            )
        prompt = [
            {"type": "text", "text": instruction + json.dumps(conversation, ensure_ascii=False)},
            *images,
        ]
        async with AcpSession(self.codex_path, self.timeout_seconds) as session:
            text = await session.prompt(self.model_name, prompt, schema, self.reasoning_effort)
            native_usage = session.usage
        usage = None
        if native_usage:
            usage = {
                "input_tokens": native_usage.get("inputTokens", 0),
                "output_tokens": native_usage.get("outputTokens", 0),
                "total_tokens": native_usage.get("totalTokens", 0),
            }
        calls = []
        if structured_schema is not None:
            text = json.loads(text)["json"]
        if tools and not kwargs.get("response_schema"):
            result = json.loads(text)
            text = result["content"]
            names = {tool["function"]["name"] for tool in tools}
            for item in result["tool_calls"]:
                arguments = json.loads(item["arguments"])
                if item["name"] not in names or not isinstance(arguments, dict):
                    raise AcpRequestError("Codex returned an invalid tool call.")
                calls.append(
                    {"name": item["name"], "args": arguments, "id": f"acp-{uuid.uuid4().hex}"}
                )
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content=text,
                        tool_calls=calls,
                        response_metadata={"model_name": self.model_name, "provider": "openai_acp"},
                        usage_metadata=usage,
                    )
                )
            ]
        )
