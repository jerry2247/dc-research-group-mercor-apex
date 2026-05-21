"""Dual-axis top-k retrieval from a Dynamic Ledger."""

from __future__ import annotations

from apex_bench.dynamic_ledger.embeddings import cosine_similarity
from apex_bench.dynamic_ledger.entry import DynamicLedger, Entry


def retrieve(
    store: DynamicLedger,
    *,
    query_embedding: list[float],
    k: int,
    similarity_threshold: float = 0.0,
) -> list[Entry]:
    """Dual-axis retrieval, source-problem axis first, with optional similarity floor.

    ``B_i = dedup-by-entry_id( top-k by source_problem_embedding +
    top-k by content_embedding )`` over active entries. Any entry whose
    best-axis cosine is below ``similarity_threshold`` is dropped — this
    prevents weakly-related notes from being injected when the retrieved
    set is structurally irrelevant. Set ``similarity_threshold=0.0`` to
    restore the original "always inject top-k" behaviour.
    """
    if k <= 0:
        return []
    active = store.active_entries()
    if not active:
        return []

    def score(axis_attr: str) -> list[tuple[float, Entry]]:
        scored: list[tuple[float, Entry]] = []
        for e in active:
            v = getattr(e, axis_attr)
            if not v:
                continue
            s = cosine_similarity(query_embedding, v)
            if s < similarity_threshold:
                continue
            scored.append((s, e))
        scored.sort(key=lambda p: p[0], reverse=True)
        return scored[:k]

    top_p = score("source_problem_embedding")
    top_c = score("content_embedding")

    out: list[Entry] = []
    seen: set[str] = set()
    for _s, e in top_p + top_c:
        if e.entry_id in seen:
            continue
        seen.add(e.entry_id)
        out.append(e)
    return out
