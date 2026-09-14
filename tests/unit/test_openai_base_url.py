"""Backend-only endpoint tests: no device, live credentials, or network required."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from pydantic import SecretStr
import pytest

from artemis.config.llm import (
    LLMConfig,
    LLMWithFallback,
    _expand_default_into_nodes,
    deep_merge_llm_config,
)
from artemis.config.settings import Settings, settings
from artemis.llm.router import ModelEndpoint, ModelFactory
from artemis.services.llm import _resolve_endpoint, get_cached_raw_model, get_openai_llm
from artemis.utils.credentials_validator import validate_api_key


@pytest.fixture(autouse=True)
def isolate_openai(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("ARTEMIS_FAKE_LLM", raising=False)
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", None)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr("test-endpoint-key"))
    monkeypatch.setattr(ModelFactory, "_cache", {})


@pytest.mark.parametrize("field", ["api_base", "base_url"])
@pytest.mark.parametrize("fallback", [False, True])
def test_config_preserves_primary_and_fallback_urls(field, fallback):
    cfg = LLMWithFallback.model_validate(
        {
            "provider": "openai",
            "model": "primary-model",
            field: "https://primary.example/v1",
            "fallback": {
                "provider": "openai",
                "model": "fallback-model",
                field: "https://fallback.example/api/v1",
            },
        }
    )
    cfg = LLMWithFallback.model_validate(cfg.model_dump())
    ctx = SimpleNamespace(llm_config=SimpleNamespace(get_agent=lambda _: cfg))
    endpoint = _resolve_endpoint(ctx, "operator", use_fallback=fallback)
    expected = "https://fallback.example/api/v1" if fallback else "https://primary.example/v1"
    assert endpoint.api_base == expected
    assert ModelFactory.create_model(endpoint).openai_api_base == expected


@pytest.mark.parametrize(
    "explicit,configured,environment,expected",
    [
        (
            " https://explicit.example/api/v1/ ",
            "https://settings.example/v1",
            "https://env.example/v1",
            "https://explicit.example/api/v1",
        ),
        (
            None,
            "https://settings.example/v1/",
            "https://env.example/v1",
            "https://settings.example/v1",
        ),
        (None, None, "https://env.example/v1", "https://env.example/v1"),
        (" ", "", "", "https://api.openai.com/v1"),
    ],
)
def test_base_url_precedence(monkeypatch, explicit, configured, environment, expected):
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", configured)
    monkeypatch.setenv("OPENAI_BASE_URL", environment)
    model = ModelFactory.create_model(
        ModelEndpoint(provider="openai", model_name="test-model", base_url=explicit)
    )
    assert model.openai_api_base == expected


def test_base_url_loads_from_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_BASE_URL=https://dotenv.example/v1\n", encoding="utf-8")
    assert Settings(_env_file=env_file).get_openai_base_url() == "https://dotenv.example/v1"


def test_cache_tracks_effective_destination(monkeypatch):
    endpoint = ModelEndpoint(provider="openai", model_name="test-model")
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", "https://first.example/v1")
    first = ModelFactory.get_model(endpoint)
    assert ModelFactory.get_model(endpoint) is first
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", "https://second.example/v1")
    second = ModelFactory.get_model(endpoint)
    assert second is not first
    assert second.openai_api_base == "https://second.example/v1"
    assert endpoint.api_base is None


def test_python_helpers_accept_base_url():
    url = "https://helper.example/api/v1"
    assert get_openai_llm(base_url=url).openai_api_base == url
    assert get_cached_raw_model("openai", "test-model", base_url=url).openai_api_base == url


@pytest.mark.parametrize(
    "default_field,node_field", [("api_base", "base_url"), ("base_url", "api_base")]
)
def test_url_aliases_override_defaults(default_field, node_field):
    expanded = _expand_default_into_nodes(
        {
            "default": {
                "provider": "openai",
                "model": "test-model",
                default_field: "https://default.example/v1",
                "fallback": {"provider": "openai", "model": "backup"},
            },
            "nodes": {"operator": {node_field: "https://node.example/v1"}},
        }
    )
    config = LLMConfig.model_validate(expanded)
    assert config.operator.api_base == "https://node.example/v1"
    overridden = deep_merge_llm_config(
        config, {"operator": {"base_url": "https://override.example/v1"}}
    )
    assert overridden.operator.api_base == "https://override.example/v1"
    assert config.operator.api_base == "https://node.example/v1"


@pytest.mark.asyncio
async def test_diagnostics_authenticate_custom_endpoint_and_redact_key():
    from mcp_server.tools.diagnose import _verify_credentials

    credentials = SimpleNamespace(
        metadata={
            "providers": [{"provider": "custom", "raw_key": "https://custom.example/v1"}],
            "api_keys": {"openai": "test-secret-key"},
        }
    )
    with patch("mcp_server.tools.diagnose.validate_api_key", new_callable=AsyncMock) as validate:
        validate.return_value = (False, "Rejected test-secret-key")
        result = await _verify_credentials(credentials)
    validate.assert_awaited_once_with(
        "custom", "test-secret-key", base_url="https://custom.example/v1", timeout=12.0
    )
    assert "test-secret-key" not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit", [None, "https://override.example/api/v1/"])
async def test_credential_check_uses_custom_url(monkeypatch, explicit):
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", "https://configured.example/v1/")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as get:
        get.return_value = httpx.Response(200, json={"data": []})
        valid, _ = await validate_api_key("openai", "test-key", base_url=explicit)
    assert valid
    expected = explicit or settings.OPENAI_BASE_URL
    get.assert_awaited_once_with(
        f"{expected.rstrip('/')}/models", headers={"Authorization": "Bearer test-key"}
    )


def test_chat_request_reaches_custom_path_with_endpoint_key():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": "test-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with patch("langchain_openai.ChatOpenAI") as constructor:
            ModelFactory.create_model(
                ModelEndpoint(
                    provider="openai",
                    model_name="test-model",
                    base_url="https://proxy.example/api/v1/",
                )
            )
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(**constructor.call_args.kwargs, http_client=client)
        assert model.invoke("hello").content == "ok"
    assert len(requests) == 1
    assert str(requests[0].url) == "https://proxy.example/api/v1/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer test-endpoint-key"
