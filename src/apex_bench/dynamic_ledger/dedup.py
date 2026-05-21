"""Create-time cosine-block dedup against the per-task retrieved subset."""

from __future__ import annotations

from apex_bench.dynamic_ledger.embeddings import cosine_similarity
from apex_bench.dynamic_ledger.entry import Entry


def is_too_similar_to_retrieved(
    *,
    candidate_embedding: list[float],
    retrieved: list[Entry],
    threshold: float,
) -> tuple[bool, float, str | None]:
    """Return ``(blocked, max_cosine, by_entry_id)``.

    The candidate is blocked when its content embedding has cosine
    similarity > ``threshold`` against any retrieved entry's
    ``content_embedding``. ``by_entry_id`` is the closest retrieved
    entry's id when blocked, ``None`` otherwise.
    """
    if not retrieved or not candidate_embedding:
        return False, 0.0, None
    best = 0.0
    by: str | None = None
    for e in retrieved:
        if not e.content_embedding:
            continue
        s = cosine_similarity(candidate_embedding, e.content_embedding)
        if s > best:
            best = s
            by = e.entry_id
    blocked = best > threshold
    return blocked, best, by if blocked else None
