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

"""LLM & Multimodal Vision Credentials Readiness Probe."""

from typing import Any
from artemis.config import settings
from artemis.core.diagnostics.probes.base import BaseProbe
from artemis.core.diagnostics.schema import (
    ProbeAction,
    ProbeCategory,
    ProbeResult,
    ProbeStatus,
)


class LLMCredentialsProbe(BaseProbe):
    """Probe verifying Gemini and multi-provider multimodal LLM credentials."""

    @property
    def probe_id(self) -> str:
        return "gemini_api_key"

    @property
    def category(self) -> ProbeCategory:
        return ProbeCategory.CREDENTIALS

    @property
    def is_blocker(self) -> bool:
        return True

    def _mask_key(self, key_str: str) -> str:
        """Helper to safely mask an API credential for display."""
        if len(key_str) > 10:
            return f"****{key_str[-4:]}"
        return "***"

    async def probe(self) -> ProbeResult:
        from artemis.config.settings import is_placeholder_key
        from artemis.config.sqlite_store import PROVIDER_KEYS, get_settings_store

        store = get_settings_store()
        document, version = store.model()
        default = document["config"].get("default", {})
        selected_provider = default.get("provider", "google")
        values = document["credentials"]

        def credential(provider):
            return next(
                (
                    str(values[key]).strip()
                    for key in PROVIDER_KEYS.get(provider, [])
                    if values.get(key) and not is_placeholder_key(values[key])
                ),
                "",
            )

        labels = {
            "google": "Gemini",
            "openai": "OpenAI",
            "anthropic": "Claude",
            "openrouter": "OpenRouter",
            "xai": "xAI (Grok)",
        }
        providers: list[dict[str, Any]] = []
        api_keys = {}
        for provider, label in labels.items():
            key = credential(provider)
            if key:
                providers.append(
                    {
                        "provider": provider,
                        "label": label,
                        "masked": self._mask_key(key),
                        "raw_key": key,
                        "key": key,
                    }
                )
                api_keys[provider] = key
        if api_keys.get("google"):
            api_keys["gemini"] = api_keys["google"]
        ocr_key = next(
            (
                str(values[key]).strip()
                for key in ("OCR_API_KEY", "VISION_API_KEY")
                if values.get(key) and not is_placeholder_key(values[key])
            ),
            "",
        )
        if ocr_key:
            api_keys["ocr"] = ocr_key
        base_url = (
            default.get("api_base") or default.get("base_url") or values.get("OPENAI_BASE_URL")
        )
        if base_url and selected_provider in {"openai", "custom", "ollama", "vllm"}:
            endpoint_provider = (
                selected_provider if selected_provider in {"ollama", "vllm"} else "custom"
            )
            providers.append(
                {
                    "provider": endpoint_provider,
                    "label": "Configured model endpoint",
                    "masked": "Configured",
                    "raw_key": base_url,
                    "key": base_url,
                }
            )
        metadata = {
            "storage": "sqlite",
            "database_path": str(store.path),
            "version": version,
            "provider": selected_provider,
            "model": default.get("model", ""),
            "configured_count": len(providers),
            "providers": providers,
            "has_ocr_key": bool(ocr_key),
            "api_keys": api_keys,
            "current_key": credential(selected_provider),
            "current_gemini_key": api_keys.get("google", ""),
        }
        ready = bool(credential(selected_provider))
        if selected_provider in {"ollama", "vllm"}:
            ready = bool(base_url)
        if selected_provider == "openai_acp":
            from artemis.llm.openai_acp import available_codex_models

            settings.refresh_model_settings()
            try:
                models = await available_codex_models()
                ready = bool(models)
                metadata["model_count"] = len(models)
            except (OSError, ValueError, RuntimeError, TimeoutError):
                ready = False
        label = labels.get(selected_provider, selected_provider)
        return ProbeResult(
            id=self.probe_id,
            category=self.category,
            title="Model credentials (SQLite)",
            status=ProbeStatus.PASS if ready else ProbeStatus.FAIL,
            is_blocker=True,
            summary=f"Configured ({label})" if ready else f"Configuration missing ({label})",
            description=(
                f"The selected {label} model uses credentials stored in SQLite. "
                "Configuration checked; API connectivity is checked when a task runs."
                if ready and selected_provider != "openai_acp"
                else "Installed Codex is signed in and available through ACP; selection comes from SQLite."
                if ready
                else f"Configure the selected {label} provider in Settings > Models (SQLite)."
            ),
            metadata=metadata,
            actions=[]
            if ready
            else [
                ProbeAction(
                    action_type="link", label="Model settings", payload="/settings/?tab=models"
                )
            ],
        )


class VisionOCRProbe(BaseProbe):
    """Probe verifying optional Google Cloud Vision OCR credentials."""

    @property
    def probe_id(self) -> str:
        return "vision_ocr_key"

    @property
    def category(self) -> ProbeCategory:
        return ProbeCategory.CREDENTIALS

    @property
    def is_blocker(self) -> bool:
        return False

    def _mask_key(self, key_str: str) -> str:
        """Helper to safely mask an API credential for display."""
        if len(key_str) > 10:
            return f"****{key_str[-4:]}"
        return "***"

    async def probe(self) -> ProbeResult:
        from artemis.utils.ocr_api import is_ocr_configured

        ocr_key = settings.get_api_key("ocr")
        is_configured = is_ocr_configured() and ocr_key is not None

        if is_configured and ocr_key:
            val = ocr_key.get_secret_value()
            masked = self._mask_key(val)
            return ProbeResult(
                id=self.probe_id,
                category=self.category,
                title="Vision OCR API Key (Optional)",
                status=ProbeStatus.PASS,
                is_blocker=False,
                summary="Active & Configured",
                description=f"Google Cloud Vision OCR ({masked}) is active for image text recognition.",
                metadata={
                    "configured": True,
                    "storage": "sqlite",
                    "masked_key": masked,
                    "key": val,
                    "raw_key": val,
                },
                actions=[
                    ProbeAction(
                        action_type="hint",
                        label="OCR Enabled",
                        payload="OCR is active and will fuse text with UI XML hierarchy.",
                    )
                ],
            )

        return ProbeResult(
            id=self.probe_id,
            category=self.category,
            title="Vision OCR API Key (Optional)",
            status=ProbeStatus.PASS,
            is_blocker=False,
            summary="Not Configured (Optional)",
            description="No OCR credential is configured in SQLite. Perception uses the UI XML hierarchy without OCR.",
            metadata={"configured": False, "storage": "sqlite"},
            actions=[
                ProbeAction(
                    action_type="hint",
                    label="Standard XML Perception",
                    payload="Artemis uses pure UI layout parsing and Set-of-Marks visual grounding.",
                )
            ],
        )
