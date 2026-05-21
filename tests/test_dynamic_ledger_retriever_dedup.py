"""Unit tests for dual-axis retrieval + create-time dedup."""

from __future__ import annotations

from apex_bench.dynamic_ledger.dedup import is_too_similar_to_retrieved
from apex_bench.dynamic_ledger.entry import DynamicLedger
from apex_bench.dynamic_ledger.retriever import retrieve


def _make_ledger() -> DynamicLedger:
    s = DynamicLedger(domain="Finance")
    s.add(
        section="A",
        content="alpha content",
        source_problem="alpha problem",
        content_embedding=[1.0, 0.0, 0.0],
        source_problem_embedding=[0.0, 1.0, 0.0],
        created=1,
    )
    s.add(
        section="B",
        content="beta content",
        source_problem="beta problem",
        content_embedding=[0.0, 1.0, 0.0],
        source_problem_embedding=[1.0, 0.0, 0.0],
        created=2,
    )
    s.add(
        section="C",
        content="gamma content",
        source_problem="gamma problem",
        content_embedding=[0.0, 0.0, 1.0],
        source_problem_embedding=[0.0, 0.0, 1.0],
        created=3,
    )
    return s


def test_retrieve_dedupes_across_axes() -> None:
    s = _make_ledger()
    # Query aligned with entry-1's content_embedding AND entry-2's source_problem
    out = retrieve(s, query_embedding=[1.0, 0.0, 0.0], k=2)
    # Source-problem axis first: entry-2 (s.p.emb=[1,0,0]), entry-1 (s.p.emb=[0,1,0])
    # Content axis: entry-1 (c.emb=[1,0,0]), entry-2 (c.emb=[0,1,0])
    ids = [e.entry_id for e in out]
    # Both entries appear, but each only once
    assert set(ids) == {"entry-1", "entry-2"}


def test_retrieve_respects_k_per_axis() -> None:
    s = _make_ledger()
    out = retrieve(s, query_embedding=[0.0, 0.0, 1.0], k=1)
    # Both axes will pick entry-3 (highest match), so after dedup k=1
    assert [e.entry_id for e in out] == ["entry-3"]


def test_retrieve_skips_soft_deleted() -> None:
    s = _make_ledger()
    s.soft_delete("entry-1", updated=4)
    out = retrieve(s, query_embedding=[1.0, 0.0, 0.0], k=3)
    assert "entry-1" not in [e.entry_id for e in out]


def test_retrieve_zero_k_returns_empty() -> None:
    s = _make_ledger()
    assert retrieve(s, query_embedding=[1.0, 0.0, 0.0], k=0) == []


def test_dedup_blocks_above_threshold() -> None:
    s = _make_ledger()
    retrieved = [s.entries["entry-1"]]
    blocked, max_cos, by = is_too_similar_to_retrieved(
        candidate_embedding=[1.0, 0.0, 0.0],
        retrieved=retrieved,
        threshold=0.85,
    )
    assert blocked is True
    assert max_cos == 1.0
    assert by == "entry-1"


def test_dedup_passes_below_threshold() -> None:
    s = _make_ledger()
    retrieved = [s.entries["entry-1"]]
    blocked, _max_cos, by = is_too_similar_to_retrieved(
        candidate_embedding=[0.0, 1.0, 0.0],
        retrieved=retrieved,
        threshold=0.85,
    )
    assert blocked is False
    assert by is None


def test_dedup_empty_retrieved_passes() -> None:
    blocked, max_cos, by = is_too_similar_to_retrieved(
        candidate_embedding=[1.0],
        retrieved=[],
        threshold=0.85,
    )
    assert blocked is False
    assert max_cos == 0.0
    assert by is None
