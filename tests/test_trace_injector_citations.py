"""Unit tests for TRACE injector + citations extraction (apex-bench)."""

from __future__ import annotations

from apex_bench.trace.bullet import TraceLedger
from apex_bench.trace.citations import extract_and_strip_citations
from apex_bench.trace.injector import augment_user_prompt, render_bullets_block


def _two_bullets():
    s = TraceLedger(domain="Finance")
    s.add(
        section="A",
        content="alpha",
        source_problem="ap",
        content_embedding=[1.0],
        source_problem_embedding=[0.0],
        created=1,
    )
    s.add(
        section="B",
        content="beta",
        source_problem="bp",
        content_embedding=[0.0],
        source_problem_embedding=[1.0],
        created=2,
    )
    return list(s.bullets.values())


def test_render_bullets_block_includes_counters() -> None:
    out = render_bullets_block(_two_bullets())
    assert "<bullet bullet-1 section=A" in out
    assert "helpful=0" in out and "harmful=0" in out and "usage=0" in out


def test_render_bullets_block_empty_marker() -> None:
    assert "no relevant strategy bullets" in render_bullets_block([])


def test_augment_user_prompt_prepends_block() -> None:
    out = augment_user_prompt("the task prompt", bullets=_two_bullets())
    assert out.startswith("## Strategy cheatsheet")
    assert "<bullet bullet-1" in out
    assert out.endswith("the task prompt")


def test_extract_strip_well_formed_citations() -> None:
    response = "Some analysis here.\n\n<citations>[bullet-1, bullet-7]</citations>"
    ex = extract_and_strip_citations(response)
    assert ex.citations_present is True
    assert ex.cited_bullet_ids == ["bullet-1", "bullet-7"]
    assert "<citations>" not in ex.stripped_response
    assert "Some analysis here." in ex.stripped_response


def test_extract_empty_citations_tag() -> None:
    response = "Some analysis.\n<citations>[]</citations>"
    ex = extract_and_strip_citations(response)
    assert ex.citations_present is True
    assert ex.cited_bullet_ids == []


def test_extract_no_tag_keeps_response() -> None:
    response = "Some analysis. No tag here."
    ex = extract_and_strip_citations(response)
    assert ex.citations_present is False
    assert ex.stripped_response == response


def test_extract_picks_last_well_formed_tag() -> None:
    response = (
        "<citations>[bullet-1]</citations>\n"
        "interim text\n"
        "<citations>[bullet-2, bullet-3]</citations>"
    )
    ex = extract_and_strip_citations(response)
    assert ex.cited_bullet_ids == ["bullet-2", "bullet-3"]


def test_extract_counts_malformed() -> None:
    response = "<citations>not a valid list</citations>\nactual content"
    ex = extract_and_strip_citations(response)
    assert ex.citations_present is False
    assert ex.citations_malformed_count == 1
