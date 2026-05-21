"""TRACE — Tool-augmented Reasoning via Atomic Cheatsheet Editing
(apex-bench prose-deliverable adaptation).

Uses the GROUND-TRUTH correctness bit (boolean ``criteria_passed ==
criteria_total``) — intentionally, per the TRACE paper. Distinct from
the Dynamic Ledger subsystem which is no-GT.
"""

from __future__ import annotations

from apex_bench.trace.bullet import Bullet, TraceLedger
from apex_bench.trace.citations import (
    CitationExtract,
    extract_and_strip_citations,
)
from apex_bench.trace.config import TraceConfig
from apex_bench.trace.curator import (
    CuratedOp,
    CuratorResult,
    apply_ops,
    curate,
    parse_cheatsheet_updates,
)
from apex_bench.trace.dedup import is_too_similar_to_retrieved
from apex_bench.trace.embeddings import (
    EmbeddingClient,
    LiteLLMEmbeddingClient,
    cosine_similarity,
)
from apex_bench.trace.injector import augment_user_prompt, render_bullets_block
from apex_bench.trace.reflector import (
    ReflectorProposal,
    ReflectorResult,
    parse_reflector_proposals,
    reflect,
)
from apex_bench.trace.retriever import retrieve
from apex_bench.trace.runtime import TraceRuntime
from apex_bench.trace.store import SnapshotStore

__all__ = [
    "Bullet",
    "CitationExtract",
    "CuratedOp",
    "CuratorResult",
    "EmbeddingClient",
    "LiteLLMEmbeddingClient",
    "ReflectorProposal",
    "ReflectorResult",
    "SnapshotStore",
    "TraceConfig",
    "TraceLedger",
    "TraceRuntime",
    "apply_ops",
    "augment_user_prompt",
    "cosine_similarity",
    "curate",
    "extract_and_strip_citations",
    "is_too_similar_to_retrieved",
    "parse_cheatsheet_updates",
    "parse_reflector_proposals",
    "reflect",
    "render_bullets_block",
    "retrieve",
]
