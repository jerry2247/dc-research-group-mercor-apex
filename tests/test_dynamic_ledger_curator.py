"""Unit tests for the curator parser + apply_ops."""

from __future__ import annotations

from apex_bench.dynamic_ledger.config import DynamicLedgerConfig
from apex_bench.dynamic_ledger.curator import (
    CuratedOp,
    apply_ops,
    parse_memory_updates,
)
from apex_bench.dynamic_ledger.entry import DynamicLedger


class _FakeEmbed:
    def embed(self, texts: list[str]) -> list[list[float]]:
        # Each text gets a distinct unit vector
        return [[float(i + 1), float(len(t) % 7)] for i, t in enumerate(texts)]


def test_parser_extracts_well_formed_block() -> None:
    txt = (
        "some prose\n"
        "<memory_updates>\n"
        '[{"op": "CREATE", "section": "S", "content": "C", "source_problem": "P"}]'
        "\n</memory_updates>\n"
    )
    ops, err = parse_memory_updates(txt)
    assert err is None
    assert len(ops) == 1
    assert ops[0].op == "CREATE"
    assert ops[0].section == "S"


def test_parser_reports_missing_block() -> None:
    ops, err = parse_memory_updates("no block here")
    assert ops == []
    assert "no <memory_updates>" in err


def test_parser_picks_last_block_if_multiple() -> None:
    txt = (
        "<memory_updates>[]</memory_updates>\n"
        "<memory_updates>"
        '[{"op": "CREATE", "section": "S", "content": "C", "source_problem": "P"}]'
        "</memory_updates>"
    )
    ops, err = parse_memory_updates(txt)
    assert err is None
    assert len(ops) == 1


def test_parser_drops_bad_ops_keeps_good_ones() -> None:
    txt = (
        "<memory_updates>"
        '[{"op": "CREATE", "section": "S", "content": "C", "source_problem": "P"},'
        ' {"op": "GARBAGE"},'
        ' {"op": "UPDATE", "entry_id": "entry-1", "content": "X"}]'
        "</memory_updates>"
    )
    ops, err = parse_memory_updates(txt)
    assert err is None
    assert [o.op for o in ops] == ["CREATE", "UPDATE"]


def test_apply_create_commits_when_no_dedup() -> None:
    store = DynamicLedger(domain="Finance")
    ops = [CuratedOp(op="CREATE", section="S", content="C", source_problem="P")]
    cfg = DynamicLedgerConfig(enabled=True)
    stats = apply_ops(
        store=store,
        ops=ops,
        retrieved=[],
        embed=_FakeEmbed(),
        cfg=cfg,
        current_ordinal=1,
    )
    assert stats.create_committed == 1
    assert len(store.entries) == 1


def test_apply_create_blocked_by_dedup() -> None:
    class _ColinearEmbed:
        def embed(self, texts: list[str]) -> list[list[float]]:
            # Make the CREATE candidate's content embedding identical (up to
            # scale) to the existing entry's so cosine == 1.0 > threshold.
            return [[1.0, 0.0] for _ in texts]

    store = DynamicLedger(domain="Finance")
    existing = store.add(
        section="S0",
        content="orig",
        source_problem="op",
        content_embedding=[1.0, 0.0],
        source_problem_embedding=[0.0, 1.0],
        created=1,
    )
    ops = [CuratedOp(op="CREATE", section="S", content="C", source_problem="P")]
    cfg = DynamicLedgerConfig(enabled=True, create_time_similarity_threshold=0.85)
    stats = apply_ops(
        store=store,
        ops=ops,
        retrieved=[existing],
        embed=_ColinearEmbed(),
        cfg=cfg,
        current_ordinal=2,
    )
    assert stats.create_blocked == 1
    assert stats.create_committed == 0


def test_apply_delete_invalid_id_counted() -> None:
    store = DynamicLedger(domain="Finance")
    ops = [CuratedOp(op="DELETE", entry_id="entry-999")]
    stats = apply_ops(
        store=store,
        ops=ops,
        retrieved=[],
        embed=_FakeEmbed(),
        cfg=DynamicLedgerConfig(enabled=True),
        current_ordinal=1,
    )
    assert stats.skipped_invalid_entry_id == 1
    assert stats.delete == 0


def test_apply_update_active_entry() -> None:
    store = DynamicLedger(domain="Finance")
    e = store.add(
        section="S",
        content="orig",
        source_problem="op",
        content_embedding=[1.0, 0.0],
        source_problem_embedding=[0.0, 1.0],
        created=1,
    )
    ops = [CuratedOp(op="UPDATE", entry_id=e.entry_id, content="revised")]
    stats = apply_ops(
        store=store,
        ops=ops,
        retrieved=[],
        embed=_FakeEmbed(),
        cfg=DynamicLedgerConfig(enabled=True),
        current_ordinal=2,
    )
    assert stats.update == 1
    assert store.entries[e.entry_id].content == "revised"


def test_parser_drops_unknown_ops() -> None:
    """The Dynamic Ledger has 3 ops: CREATE / UPDATE / DELETE. Any other op
    (including the historical NO_OP / CONSOLIDATE we previously had) is
    dropped silently by the parser so the curator's wider prompt cannot
    poison the ledger."""
    txt = (
        "<memory_updates>"
        '[{"op": "CREATE", "section": "S", "content": "C", "source_problem": "P"},'
        ' {"op": "CONSOLIDATE", "entry_ids": ["entry-1","entry-2"]},'
        ' {"op": "NO_OP", "reason": "nothing"}]'
        "</memory_updates>"
    )
    ops, err = parse_memory_updates(txt)
    assert err is None
    assert [o.op for o in ops] == ["CREATE"]
