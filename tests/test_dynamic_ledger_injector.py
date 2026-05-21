"""Unit tests for the user-prompt injection helper."""

from __future__ import annotations

from apex_bench.dynamic_ledger.entry import DynamicLedger
from apex_bench.dynamic_ledger.injector import augment_user_prompt, render_entries_block


def _two_entries() -> list:
    s = DynamicLedger(domain="Finance")
    s.add(
        section="A topic",
        content="alpha workflow",
        source_problem="alpha problem",
        content_embedding=[1.0],
        source_problem_embedding=[0.0],
        created=1,
    )
    s.add(
        section="B topic",
        content="beta note",
        source_problem="beta problem",
        content_embedding=[0.0],
        source_problem_embedding=[1.0],
        created=2,
    )
    return list(s.entries.values())


def test_render_entries_block_empty_returns_marker() -> None:
    out = render_entries_block([])
    assert "no relevant prior notes" in out


def test_render_entries_block_two_entries() -> None:
    out = render_entries_block(_two_entries())
    assert "<entry entry-1 section=A topic>" in out
    assert "<entry entry-2 section=B topic>" in out
    assert "alpha workflow" in out
    assert "beta note" in out


def test_augment_user_prompt_prepends_block() -> None:
    out = augment_user_prompt("the task prompt", entries=_two_entries())
    assert out.startswith("## Reference cheatsheet")
    assert out.endswith("the task prompt")
    assert "<entry entry-1" in out


def test_augment_user_prompt_with_empty_entries_still_injects_marker() -> None:
    out = augment_user_prompt("the task", entries=[])
    assert "## Reference cheatsheet" in out
    assert "no relevant prior notes" in out
    assert out.endswith("the task")
