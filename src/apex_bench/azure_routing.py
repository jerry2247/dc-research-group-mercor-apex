"""Azure-routing helper for GPT-5.5 chat completions (apex-bench).

Mirrors ``apex_agents_bench.azure_routing``. When
``AzureConfig.enabled`` is True, any ``gpt-5.5*`` model identifier
that would otherwise hit OpenAI is rewritten to the Azure-OpenAI
deployment instead (``azure/<deployment_name>``). LiteLLM resolves
Azure credentials from the standard environment variables:

  - ``AZURE_API_KEY``       (or ``AZURE_OPENAI_API_KEY``)
  - ``AZURE_API_BASE``      (or ``AZURE_OPENAI_ENDPOINT``)
  - ``AZURE_API_VERSION``   (or ``AZURE_OPENAI_API_VERSION``)

These are read by LiteLLM directly per-request.

The embedding model (``text-embedding-3-large``) is left untouched —
embeddings always go through OpenAI regardless of
``AzureConfig.enabled``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AzureConfig:
    """Azure-OpenAI routing configuration.

    When ``enabled=False`` (default), no routing happens — the project's
    OpenAI-based default paths are preserved byte-for-byte.

    ``deployment_name`` defaults to the ``AZURE_GPT55_DEPLOYMENT_NAME``
    env var, then to ``"gpt-5.5"`` if that env var is unset.
    """

    enabled: bool = False
    deployment_name: str = ""

    def resolved_deployment_name(self) -> str:
        if self.deployment_name:
            return self.deployment_name
        return os.environ.get("AZURE_GPT55_DEPLOYMENT_NAME", "gpt-5.5")


def _is_gpt55(model_id: str) -> bool:
    bare = model_id.split("/")[-1] if "/" in model_id else model_id
    return bare.startswith("gpt-5.5")


def route_model_id(model_id: str, *, cfg: AzureConfig) -> str:
    if not cfg.enabled:
        return model_id
    if not _is_gpt55(model_id):
        return model_id
    return f"azure/{cfg.resolved_deployment_name()}"


def route_provider_for_credentials(model_id: str) -> str | None:
    if model_id.startswith("azure/"):
        return "azure"
    return None
