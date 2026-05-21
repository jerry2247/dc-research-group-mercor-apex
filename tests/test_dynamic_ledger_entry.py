"""Unit tests for apex_bench.dynamic_ledger.entry."""

from __future__ import annotations

import pytest

from apex_bench.dynamic_ledger.entry import (
    DynamicLedger,
    format_entry_id,
    parse_entry_id,
)


def test_format_entry_id_unpadded() -> None:
    assert format_entry_id(1) == "entry-1"
    assert format_entry_id(42) == "entry-42"
    assert format_entry_id(99_999) == "entry-99999"


def test_format_entry_id_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        format_entry_id(-1)


def test_parse_entry_id_roundtrip() -> None:
    for n in (1, 42, 12345, 99999):
        assert parse_entry_id(format_entry_id(n)) == n


def test_parse_entry_id_rejects_malformed() -> None:
    for bad in ("ctx_00001", "entry-", "00001", ""):
        with pytest.raises(ValueError):
            parse_entry_id(bad)


def test_add_increments_counter_and_unpadded_ids() -> None:
    s = DynamicLedger(domain="Finance")
    e1 = s.add(
        section="a",
        content="c1",
        source_problem="p1",
        content_embedding=[1.0],
        source_problem_embedding=[0.0],
        created=1,
    )
    e2 = s.add(
        section="b",
        content="c2",
        source_problem="p2",
        content_embedding=[0.0],
        source_problem_embedding=[1.0],
        created=1,
    )
    assert e1.entry_id == "entry-1"
    assert e2.entry_id == "entry-2"
    assert s.next_entry_ord == 3


def test_soft_delete_keeps_entry_but_excludes_from_active() -> None:
    s = DynamicLedger(domain="Legal")
    s.add(
        section="x",
        content="c",
        source_problem="p",
        content_embedding=[1.0],
        source_problem_embedding=[0.0],
        created=1,
    )
    assert len(s.active_entries()) == 1
    s.soft_delete("entry-1", updated=2)
    assert s.active_entries() == []
    assert s.entries["entry-1"].active is False


def test_update_content_preserves_active_and_re_embeds() -> None:
    s = DynamicLedger(domain="Medicine")
    s.add(
        section="x",
        content="orig",
        source_problem="p",
        content_embedding=[1.0, 0.0],
        source_problem_embedding=[0.0, 1.0],
        created=1,
    )
    updated = s.update_content(
        "entry-1", content="revised", content_embedding=[0.5, 0.5], updated=2
    )
    assert updated is not None
    assert updated.content == "revised"
    assert updated.content_embedding == [0.5, 0.5]
    # source_problem_embedding is untouched by UPDATE
    assert updated.source_problem_embedding == [0.0, 1.0]
    assert updated.updated == 2


def test_serialize_for_curator_omits_embeddings() -> None:
    s = DynamicLedger(domain="Consulting")
    s.add(
        section="x",
        content="c",
        source_problem="p",
        content_embedding=[1.0],
        source_problem_embedding=[0.0],
        created=1,
    )
    rendered = s.serialize_for_curator()
    assert rendered == [
        {
            "entry_id": "entry-1",
            "section": "x",
            "content": "c",
            "source_problem": "p",
            "created": 1,
            "updated": 1,
        }
    ]
