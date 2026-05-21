"""Unit tests for apex_bench.trace.bullet."""

from __future__ import annotations

import pytest

from apex_bench.trace.bullet import (
    TraceLedger,
    format_bullet_id,
    parse_bullet_id,
)


def test_format_bullet_id_unpadded() -> None:
    assert format_bullet_id(1) == "bullet-1"
    assert format_bullet_id(99) == "bullet-99"


def test_parse_bullet_id_roundtrip() -> None:
    for n in (1, 42, 99999):
        assert parse_bullet_id(format_bullet_id(n)) == n


def test_parse_bullet_id_rejects_malformed() -> None:
    for bad in ("bullet_1", "bullet-", "1", ""):
        with pytest.raises(ValueError):
            parse_bullet_id(bad)


def test_record_citation_bumps_counters() -> None:
    s = TraceLedger(domain="Finance")
    b = s.add(
        section="x",
        content="c",
        source_problem="p",
        content_embedding=[1.0, 0.0],
        source_problem_embedding=[0.0, 1.0],
        created=1,
    )
    assert s.record_citation(b.bullet_id, gt_correct=True) is True
    after = s.bullets[b.bullet_id]
    assert after.usage == 1
    assert after.helpful == 1
    assert after.harmful == 0

    assert s.record_citation(b.bullet_id, gt_correct=False) is True
    after = s.bullets[b.bullet_id]
    assert after.usage == 2
    assert after.helpful == 1
    assert after.harmful == 1


def test_record_citation_skips_unknown() -> None:
    s = TraceLedger(domain="Finance")
    assert s.record_citation("bullet-999", gt_correct=True) is False


def test_serialize_for_llm_includes_counters_omits_embeddings() -> None:
    s = TraceLedger(domain="Legal")
    b = s.add(
        section="x",
        content="c",
        source_problem="p",
        content_embedding=[1.0, 0.0],
        source_problem_embedding=[0.0, 1.0],
        created=1,
    )
    s.record_citation(b.bullet_id, gt_correct=False)
    rendered = s.serialize_for_llm()
    assert rendered == [
        {
            "bullet_id": "bullet-1",
            "section": "x",
            "content": "c",
            "source_problem": "p",
            "created": 1,
            "updated": 1,
            "helpful": 0,
            "harmful": 1,
            "usage": 1,
        }
    ]
