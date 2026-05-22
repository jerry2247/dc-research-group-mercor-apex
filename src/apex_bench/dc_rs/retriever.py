"""Top-k cosine retrieval over a per-domain memory bank.

Single-axis: the retrieval key is the prompt embedding only. There is
no similarity threshold, no dedup, no domain filter at this layer (the
caller picks the domain bank). The ``k`` is fixed by the caller; DC-RS
ships with ``k = 3``.
"""

from __future__ import annotations

from dataclasses import dataclass

from apex_bench.dc_rs.bank import BankEntry, DomainBank
from apex_bench.dc_rs.embeddings import cosine_similarity


@dataclass(frozen=True)
class Retrieved:
    """A retrieved bank entry together with its cosine score."""

    entry: BankEntry
    similarity: float


def retrieve(
    bank: DomainBank,
    *,
    query_embedding: list[float],
    k: int = 3,
) -> list[Retrieved]:
    """Return up to ``k`` entries ranked by descending cosine similarity.

    Returns an empty list when the bank is empty. When the bank has fewer
    than ``k`` entries, returns all of them (sorted by similarity).
    """
    if not bank.entries or k <= 0:
        return []
    scored = [
        Retrieved(entry=e, similarity=cosine_similarity(query_embedding, e.prompt_embedding))
        for e in bank.entries
    ]
    scored.sort(key=lambda r: r.similarity, reverse=True)
    return scored[:k]
