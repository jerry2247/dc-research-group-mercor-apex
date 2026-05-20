"""Registry of test-model profiles for APEX runs.

A *profile* is a named, fully-specified `ModelConfig` shape — i.e. a model id
plus the right per-provider knobs to put it in a specific reasoning/thinking
mode. We use named profiles instead of free-form CLI flags so that:

  1. The set of models we run against is explicit and reviewable.
  2. Per-provider config quirks (reasoning_effort vs enable_thinking vs
     thinking_tokens, Bedrock inference-profile prefixes, etc.) live in
     one place.
  3. A run's record can persist a single profile name and be reproduced
     exactly later.

Picking a model: `apex-bench smoke --model gpt-5.5-xhigh`.
Listing all profiles: `apex-bench models`.

Adding a new profile is a code change here, not a CLI flag — by design.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass(frozen=True)
class TestModelProfile:
    """One named (test-model, mode) combination.

    `to_model_config_kwargs` returns the dict you'd splat into
    `generation.ModelConfig(**kwargs)`. We pass that directly to the vendor's
    Pydantic ModelConfig so any validation it does runs unchanged.
    """

    # Tell pytest not to collect this class as a test fixture — the name
    # starts with `Test` for domain reasons, not because it's a test class.
    __test__: ClassVar[bool] = False

    name: str
    """The slug the user types: `gpt-5.5-medium`, `claude-opus-4.6-thinking-high`, …"""

    family: str
    """Display family: `gpt-5.5`, `grok-4.3`, `claude-opus-4.6`, …"""

    provider: str
    """`openai` | `xai` | `anthropic-bedrock`. Affects which API key must be set."""

    model_id: str
    """The litellm-routable id."""

    max_tokens: int
    """Output token cap."""

    max_input_tokens: int | None = None

    temperature: float | None = None
    """Some reasoning models reject custom temperatures. None = omit the field."""

    model_configs: dict[str, Any] | None = None
    """Per-provider extra config — `{"reasoning_effort": "high", ...}` for
    OpenAI/xAI; thinking knobs live in dedicated fields below for Anthropic."""

    enable_thinking: bool | None = None
    """Anthropic extended-thinking toggle."""

    thinking_tokens: int | None = None
    """Anthropic thinking budget (must be < max_tokens)."""

    notes: str = ""
    """One-line summary printed by `apex-bench models`."""

    def to_model_config_kwargs(self) -> dict[str, Any]:
        """Build the kwargs dict for `generation.ModelConfig(**kwargs)`."""
        kwargs: dict[str, Any] = {
            "model_id": self.model_id,
            "max_tokens": self.max_tokens,
            "number_of_runs": 1,  # project policy — see config.RUNS_PER_TASK
        }
        if self.max_input_tokens is not None:
            kwargs["max_input_tokens"] = self.max_input_tokens
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.model_configs:
            kwargs["model_configs"] = dict(self.model_configs)
        if self.enable_thinking is not None:
            kwargs["enable_thinking"] = self.enable_thinking
        if self.thinking_tokens is not None:
            kwargs["thinking_tokens"] = self.thinking_tokens
        return kwargs


# -----------------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------------
#
# Per-provider notes (justifying the specific knob values below):
#
# OpenAI GPT-5.5
#   - reasoning_effort: none | low | medium | high | xhigh. Default is medium.
#   - 1M context, 128k output ceiling per OpenAI docs.
#   - Temperature: GPT-5.5 accepts custom temperature when not in a strict
#     reasoning mode; we leave it unset to defer to OpenAI's default.
#
# xAI Grok 4.3
#   - reasoning_effort: low | medium | high (three tiers; no xhigh).
#   - 1M context, 256k output ceiling per xAI docs.
#   - Custom temperature accepted; left unset to defer to xAI's default.
#
# Anthropic Claude on AWS Bedrock
#   - Cross-region inference profile prefix is required: `bedrock/us.anthropic...`
#     The bare `bedrock/anthropic.claude-opus-4-6-v1:0` fails with
#     ValidationException; see IMPLEMENTATION_PLAN §1.1.
#   - Extended thinking is a binary toggle (`enable_thinking`) + a token budget
#     (`thinking_tokens`). thinking_tokens must be < max_tokens.
#   - `-off` profiles disable thinking entirely. `-medium` and `-high` set
#     two budget tiers; budgets are conservative — Bedrock charges for
#     thinking tokens and APEX rubric grading isn't where you want to spend
#     them, but solution-generation may benefit.
#
# Haiku stops at 4.5 — Claude Haiku 4.6 does not exist on Bedrock as of
# 2026-05-19. Confirmed via AWS Bedrock docs.

_REGISTRY: dict[str, TestModelProfile] = {}


def _add(p: TestModelProfile) -> None:
    if p.name in _REGISTRY:
        raise RuntimeError(f"duplicate profile name: {p.name}")
    _REGISTRY[p.name] = p


# --- OpenAI GPT-5.5 ----------------------------------------------------------
# Values match Mercor's upstream `MODELS` list pattern for the gpt-5.x family
# in vendor/apex_evals/examples/run_with_hf.py:25-28 verbatim:
#   model_configs = {"reasoning_effort": <effort>, "verbosity": "medium"}
#   max_tokens     = 127_997
#   max_input_tokens = 272_000
#   temperature    = 1.0, which is the only accepted/default temperature for
#                     OpenAI reasoning models. Mercor's dict omits the key, but
#                     the vendored Pydantic ModelConfig would otherwise inject
#                     its class default of 0.7 before the LiteLLM call.
# We expand `reasoning_effort` across all four levels OpenAI publishes for
# gpt-5.5 (low/medium/high/xhigh). Mercor's upstream only ships `high`.
# Note: gpt-5.5 is also the judge in this project; cells using
# gpt-5.5-* as the test model carry a within-family judge-bias caveat —
# see docs/REPRODUCIBILITY.md.

for _effort in ("low", "medium", "high", "xhigh"):
    _add(
        TestModelProfile(
            name=f"gpt-5.5-{_effort}",
            family="gpt-5.5",
            provider="openai",
            model_id="gpt-5.5",
            max_tokens=127_997,
            max_input_tokens=272_000,
            temperature=1.0,
            model_configs={
                "reasoning_effort": _effort,
                "verbosity": "medium",
                # 1800s (30 min) per LLM call. The vendor's
                # map_parameters_for_litellm forwards model_configs into
                # acompletion(**params) verbatim, and LiteLLM accepts
                # `timeout` as a top-level kwarg. Without this, LiteLLM
                # applies its own 600s default, which is too short for
                # reasoning-effort=high on very large parsed-attachment
                # prompts (observed timing out on the Finance domain).
                "timeout": 1800,
            },
            notes=f"OpenAI GPT-5.5, reasoning_effort={_effort}, verbosity=medium.",
        )
    )

# --- xAI Grok 4.3 ------------------------------------------------------------
# Values match Mercor's upstream `MODELS` list pattern for grok-4-0709
# (the only Grok entry in the upstream MODELS list) verbatim:
#   model_configs    = {"reasoning_effort": <effort>}
#   max_tokens       = 256_000
#   max_input_tokens = 256_000
#   temperature      = 0.8
# Grok 4.3's API surface exposes three reasoning_effort tiers
# (low / medium / high) per docs.x.ai.

for _effort in ("low", "medium", "high"):
    _add(
        TestModelProfile(
            name=f"grok-4.3-{_effort}",
            family="grok-4.3",
            provider="xai",
            model_id="grok-4.3",
            max_tokens=256_000,
            max_input_tokens=256_000,
            temperature=0.8,
            model_configs={
                "reasoning_effort": _effort,
                # 1800s (30 min) per LLM call. See the gpt-5.5 block above
                # for rationale; the same LiteLLM default (600s) was too
                # short for reasoning-effort=high on large parsed-attachment
                # prompts observed during the Finance domain run.
                "timeout": 1800,
            },
            notes=f"xAI Grok 4.3, reasoning_effort={_effort}, temperature=0.8.",
        )
    )

# --- Anthropic Claude on AWS Bedrock — DEFERRED ----------------------------
# Bedrock routing is not yet supported in the vendored LiteLLM client. The
# vendor's PROVIDER_PREFIXES / PROVIDER_MAPPINGS dicts have no `bedrock`
# entry, and MODEL_MAPPINGS does not list any bedrock-prefixed model ids.
# Adding Bedrock support is a STRUCTURAL patch (not a 2-line addition to
# MODEL_MAPPINGS), and is deferred until after GPT-5.5 + Grok 4.3 baselines
# are running cleanly. Tracked in docs/IMPLEMENTATION_PLAN.md § "Future
# work — Bedrock for Claude profiles".
#
# When that work happens, the Claude profile shapes are sketched below.
# They are NOT registered today; calling them would fail with
# "Model bedrock/... is not supported" from
# vendor/apex_evals/src/call_llm/litellm_client.py:429-434.
_DEFERRED_CLAUDE_PROFILES_NOTE = """
Claude profile shape (to be enabled once vendor Bedrock support lands):

  claude-opus-4.6:   bedrock/us.anthropic.claude-opus-4-6-v1:0
  claude-sonnet-4.6: bedrock/us.anthropic.claude-sonnet-4-6-v1:0
  claude-haiku-4.5:  bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0

Each with three thinking tiers (off / medium=8192 / high=32768 tokens).
"""


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


def all_profiles() -> list[TestModelProfile]:
    """All registered profiles, in insertion order (= display order)."""
    return list(_REGISTRY.values())


def profile_names() -> list[str]:
    return list(_REGISTRY.keys())


def get_profile(name: str) -> TestModelProfile:
    """Look up a profile by name; raise KeyError with a helpful message."""
    if name not in _REGISTRY:
        # Suggest near-matches by family.
        suggestions = [n for n in _REGISTRY if name.split("-")[0] in n]
        suggestion_text = f" Did you mean one of: {suggestions}?" if suggestions else ""
        raise KeyError(
            f"Unknown test-model profile {name!r}. "
            f"Use `apex-bench models` to list available profiles.{suggestion_text}"
        )
    return _REGISTRY[name]


def profiles_by_family() -> dict[str, list[TestModelProfile]]:
    """Group profiles by their display family (for help output)."""
    out: dict[str, list[TestModelProfile]] = {}
    for p in _REGISTRY.values():
        out.setdefault(p.family, []).append(p)
    return out


__all__ = [
    "TestModelProfile",
    "all_profiles",
    "get_profile",
    "profile_names",
    "profiles_by_family",
]
