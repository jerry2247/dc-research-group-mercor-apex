"""Unit tests for the retrieved-entries markdown shape (synthesizer input).

These tests pin the exact shape Suzgun et al. produce in their reference
``_format_entries`` (``dc_rs.py:275-300``): empty pool → ``"(empty)"``,
non-empty → preamble + per-entry blocks in reversed order + footer.
"""

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


def test_format_empty_pool_returns_literal_empty_placeholder() -> None:
    """Matches Suzgun's reference: ``return '(empty)'`` when no entries."""
    assert format_retrieved_entries([]) == "(empty)"


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
    # Similarities are rendered with 2-decimal format.
    assert "0.91" in out
    assert "0.78" in out
    assert "0.55" in out
    # Each entry has its prompt + deliverable.
    for k in (1, 2, 3):
        assert f"DELIVERABLE-{k}" in out
    # Preamble + footer present.
    assert "### PREVIOUS SOLUTIONS (START)" in out
    assert "#### PREVIOUS SOLUTIONS (END)" in out
    # Preamble cautions against blind copying.
    assert "critical mindset" in out


def test_format_single_entry_has_exactly_one_previous_input_header() -> None:
    retrieved = [Retrieved(entry=_entry(1), similarity=0.91)]
    out = format_retrieved_entries(retrieved)
    assert "PROMPT-1" in out
    assert out.count("#### Previous Input #") == 1
