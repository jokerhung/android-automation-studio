"""Backend-only provider routing; no mobile interactions or live API calls."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from langchain_core.messages import HumanMessage
from pydantic import SecretStr
import pytest

from artemis.agents.flash.summarizer import VisualStepSummarizer
from artemis.config.agent import AgentGlobalConfig, StepSummarizerConfig
from artemis.config.llm import LLM
from artemis.config.settings import settings
from artemis.llm.router import ModelFactory
from artemis.memory import ensure_step_memory
from artemis.sdk.builders.agent_config_builder import AgentConfigBuilder


@pytest.fixture(autouse=True)
def isolate_clients(monkeypatch):
    monkeypatch.setattr(ModelFactory, "_cache", {})
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr("test-openai-key"))
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", "https://proxy.example/api/v1")
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GCP_API_KEY"):
        monkeypatch.setattr(settings, name, None)
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("ARTEMIS_FAKE_LLM", raising=False)


def context(provider="openai", model="summary-model", api_base=None):
    cfg = LLM(provider=provider, model=model, api_base=api_base)
    return SimpleNamespace(
        data_engine=None,
        step_memory=None,
        llm_config=SimpleNamespace(get_agent=Mock(return_value=cfg)),
    )


def test_inherits_summarizer_node_and_environment_without_google_key():
    ctx = context()
    summary = VisualStepSummarizer(ctx)
    ctx.llm_config.get_agent.assert_called_once_with("summarizer")
    assert summary._llm.model_name == "summary-model"
    assert summary._llm.openai_api_base == "https://proxy.example/api/v1"
    assert summary._llm.openai_api_key.get_secret_value() == "test-openai-key"


@pytest.mark.parametrize(
    "base_url,expected",
    [
        (None, "https://node.example/v1"),
        ("https://override.example/v1/", "https://override.example/v1"),
    ],
)
def test_explicit_model_retains_node_endpoint_unless_overridden(base_url, expected):
    summary = VisualStepSummarizer(
        context(api_base="https://node.example/v1"),
        model_name="small-vision-model",
        base_url=base_url,
    )
    assert summary._model_name == "small-vision-model"
    assert summary._llm.openai_api_base == expected


def test_provider_switch_does_not_reuse_other_providers_url():
    summary = VisualStepSummarizer(
        context(provider="google", model="gemini-test", api_base="https://google.example/v1"),
        provider="openai",
        model_name="custom-vision-model",
    )
    assert summary._llm.model_name == "custom-vision-model"
    assert summary._llm.openai_api_base == "https://proxy.example/api/v1"


def test_custom_provider_explicit_url():
    summary = VisualStepSummarizer(
        context(), provider="custom", model_name="local-vision", base_url="http://localhost:9000/v1"
    )
    assert summary._llm.openai_api_base == "http://localhost:9000/v1"
    assert summary._llm.model_name == "local-vision"


def test_google_remains_supported_when_explicitly_selected():
    with patch("langchain_google_genai.ChatGoogleGenerativeAI") as google:
        VisualStepSummarizer(context(provider="google", model="gemini-test"))
    assert google.call_args.kwargs["model"] == "gemini-test"


def test_client_error_is_not_replaced_by_google_fallback():
    with patch.object(
        ModelFactory, "get_model", side_effect=ValueError("invalid endpoint")
    ) as create:
        with pytest.raises(ValueError, match="invalid endpoint"):
            VisualStepSummarizer(context())
    assert create.call_count == 1


@pytest.mark.parametrize("alias", ["api_base", "base_url"])
def test_config_url_alias_and_roundtrip(alias):
    cfg = StepSummarizerConfig.model_validate(
        {"provider": "openai", "model": "small-model", alias: "https://summary.example/v1"}
    )
    assert (
        StepSummarizerConfig.model_validate(cfg.model_dump()).api_base
        == "https://summary.example/v1"
    )
    assert StepSummarizerConfig().model is None
    assert StepSummarizerConfig().provider is None


def test_shared_memory_factory_forwards_provider_and_url():
    ctx = context(provider="google")
    cfg = AgentGlobalConfig()
    cfg.flash.step_summarizer = StepSummarizerConfig(
        provider="openai", model="small-model", base_url="https://summary.example/v1"
    )
    with patch("artemis.config.load_agent_config", return_value=cfg):
        summary = ensure_step_memory(ctx)
    assert ctx.step_memory is summary
    assert summary._llm.model_name == "small-model"
    assert summary._llm.openai_api_base == "https://summary.example/v1"


def test_builder_forwards_provider_and_url():
    builder = AgentConfigBuilder().with_flash_step_summarizer(
        model="small-model", provider="openai", base_url="https://summary.example/v1"
    )
    cfg = builder.build(validate_profiles=False).flash.step_summarizer
    assert cfg.provider == "openai"
    assert cfg.model == "small-model"
    assert cfg.api_base == "https://summary.example/v1"


@pytest.mark.asyncio
async def test_async_summary_http_request_uses_custom_endpoint():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": "summary-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "I see the next screen."},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    from langchain_openai import ChatOpenAI

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with patch(
            "langchain_openai.ChatOpenAI",
            side_effect=lambda **kw: ChatOpenAI(**kw, http_async_client=client),
        ):
            summary = VisualStepSummarizer(context())
        result = await summary._llm.ainvoke([HumanMessage(content="Summarize this transition")])
    assert result.content == "I see the next screen."
    assert len(requests) == 1
    assert str(requests[0].url) == "https://proxy.example/api/v1/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer test-openai-key"
