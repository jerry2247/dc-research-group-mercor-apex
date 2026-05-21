"""Unit tests for the Azure routing helper (apex-bench)."""

from __future__ import annotations

import os

from apex_bench.azure_routing import (
    AzureConfig,
    route_model_id,
    route_provider_for_credentials,
)


def test_route_off_is_identity() -> None:
    cfg = AzureConfig(enabled=False)
    assert route_model_id("openai/gpt-5.5", cfg=cfg) == "openai/gpt-5.5"
    assert route_model_id("xai/grok-4.3-high", cfg=cfg) == "xai/grok-4.3-high"


def test_route_on_gpt55_with_default_deployment() -> None:
    cfg = AzureConfig(enabled=True)
    deployment = os.environ.get("AZURE_GPT55_DEPLOYMENT_NAME", "gpt-5.5")
    assert route_model_id("openai/gpt-5.5", cfg=cfg) == f"azure/{deployment}"
    assert route_model_id("gpt-5.5-medium", cfg=cfg) == f"azure/{deployment}"


def test_route_on_with_explicit_deployment() -> None:
    cfg = AzureConfig(enabled=True, deployment_name="my-gpt55")
    assert route_model_id("openai/gpt-5.5", cfg=cfg) == "azure/my-gpt55"


def test_route_on_non_gpt55_is_identity() -> None:
    cfg = AzureConfig(enabled=True)
    assert route_model_id("xai/grok-4.3-high", cfg=cfg) == "xai/grok-4.3-high"
    assert route_model_id("text-embedding-3-large", cfg=cfg) == "text-embedding-3-large"


def test_route_provider_for_credentials_azure() -> None:
    assert route_provider_for_credentials("azure/gpt-5.5") == "azure"
    assert route_provider_for_credentials("openai/gpt-5.5") is None


def test_required_api_key_recognizes_azure() -> None:
    from apex_bench.runner import _required_api_key

    assert _required_api_key("azure/gpt-5.5") == "AZURE_API_KEY"
    assert _required_api_key("openai/gpt-5.5") == "OPENAI_API_KEY"


def test_run_options_default_azure_is_off() -> None:
    import dataclasses

    from apex_bench.runner import RunOptions

    fields = {f.name: f for f in dataclasses.fields(RunOptions)}
    assert "azure" in fields
    factory = fields["azure"].default_factory  # type: ignore[union-attr]
    assert factory().enabled is False
