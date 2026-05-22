"""``TraceConfig`` — knobs for the TRACE subsystem (apex-bench).

Mirrors ``apex_agents_bench.trace.config`` minus the agentic
trajectory-rendering knob. The reflector and curator both run on the
same model as the active ``TestModelProfile``; only the judge model is
fixed (gpt-5.5 medium).

See ``docs/TRACE_PRD.md``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TraceConfig:
    """TRACE configuration. The GROUND-TRUTH bit IS threaded into the
    reflector and curator — intentionally, per the TRACE paper."""

    enabled: bool = False
    embedding_model: str = "text-embedding-3-large"
    embedding_dim: int = 3072
    top_k_per_axis: int = 8

    reflector_model: str | None = None
    curator_model: str | None = None
    model_extra_args: dict | None = None

    reflector_temperature: float = 1.0
    curator_temperature: float = 1.0
    reflector_max_tokens: int = 24_000
    curator_max_tokens: int = 24_000
    reflector_timeout_seconds: int = 1800
    curator_timeout_seconds: int = 1800

    create_time_similarity_threshold: float = 0.85
    per_domain_ledger: bool = True
    snapshot_every_problem: bool = True
