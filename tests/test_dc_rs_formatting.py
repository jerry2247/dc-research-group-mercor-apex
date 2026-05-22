"""Unit tests for the retrieved-entries markdown shape (the synthesizer input)."""

from __future__ import annotations

from apex_bench.dc_rs.bank import BankEntry
from apex_bench.dc_rs.formatting import format_retrieved_entries
from apex_bench.dc_rs.retriever import Retrieved


def _entry(idx: int) -> BankEntry:
    return BankEntry(
        bank_id=f"bank-{idx:05d}",
        task_id=f"t-{idx}",
        task_prompt=f"PROMPT-{idx}",
        deliverable=f"DELIVERABLE-{idx}",
        prompt_embedding=[float(idx)],
        added=idx - 1,
    )


def test_format_empty_returns_placeholder() -> None:
    out = format_retrieved_entries([])
    assert "PREVIOUS SOLUTIONS (START)" in out
    assert "PREVIOUS SOLUTIONS (END)" in out
    assert "no prior pairs" in out


def test_format_three_entries_reversed_so_most_similar_is_last() -> None:
    retrieved = [
        Retrieved(entry=_entry(1), similarity=0.91),  # most similar
        Retrieved(entry=_entry(2), similarity=0.78),
        Retrieved(entry=_entry(3), similarity=0.55),  # least similar
    ]
    out = format_retrieved_entries(retrieved)
    # Reversed order: least similar first.
    pos1 = out.find("PROMPT-3")
    pos2 = out.find("PROMPT-2")
    pos3 = out.find("PROMPT-1")
    assert 0 < pos1 < pos2 < pos3
    # Similarities are rendered.
    assert "0.91" in out
    assert "0.78" in out
    assert "0.55" in out
    # Each entry has its prompt + deliverable.
    assert "DELIVERABLE-1" in out
    assert "DELIVERABLE-2" in out
    assert "DELIVERABLE-3" in out
    # Header / footer present.
    assert "PREVIOUS SOLUTIONS (START)" in out
    assert "PREVIOUS SOLUTIONS (END)" in out


def test_format_single_entry_has_no_pre_or_post_entries() -> None:
    retrieved = [Retrieved(entry=_entry(1), similarity=0.91)]
    out = format_retrieved_entries(retrieved)
    assert "PROMPT-1" in out
    # There should be exactly one "Previous Input #" header.
    assert out.count("#### Previous Input #") == 1
