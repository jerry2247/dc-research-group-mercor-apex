"""Top-k cosine retrieval over the single global memory pool.

Faithful to Suzgun et al.'s DC-RS reference (``dc_rs.py:_retrieve``):
single-axis cosine on the prompt embedding, no similarity threshold,
no dedup. The pool itself is global per run; the caller passes the
``Bank`` to score against.
"""

from __future__ import annotations

from dataclasses import dataclass

from apex_bench.dc_rs.bank import Bank, BankEntry
from apex_bench.dc_rs.embeddings import cosine_similarity


@dataclass(frozen=True)
class Retrieved:
    """A retrieved bank entry together with its cosine score."""

    entry: BankEntry
    similarity: float


def retrieve(
    bank: Bank,
    *,
    query_embedding: list[float],
    k: int = 3,
) -> list[Retrieved]:
    """Return up to ``k`` entries ranked by descending cosine similarity.

    Returns an empty list when the pool is empty. When the pool has
    fewer than ``k`` entries, returns all of them (sorted by similarity).
    """
    if not bank.entries or k <= 0:
        return []
    scored = sorted(
        (
            Retrieved(
                entry=e,
                similarity=cosine_similarity(query_embedding, e.prompt_embedding),
            )
            for e in bank.entries
        ),
        key=lambda r: r.similarity,
        reverse=True,
    )
    return scored[:k]
