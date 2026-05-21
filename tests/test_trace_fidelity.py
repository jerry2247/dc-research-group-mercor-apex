"""Load-bearing fidelity tests for the apex-bench TRACE subsystem."""

from __future__ import annotations

import dataclasses
import inspect
from pathlib import Path


def test_reflector_signature() -> None:
    """The reflector takes the GT bit — INTENTIONAL per TRACE paper."""
    from apex_bench.trace import reflect

    sig = inspect.signature(reflect)
    assert list(sig.parameters.keys()) == [
        "ledger",
        "task_prompt",
        "response",
        "cited_bullet_ids",
        "gt_correct",
        "cfg",
    ]


def test_curator_signature() -> None:
    """The TRACE curator takes GT bit + reflector proposals."""
    from apex_bench.trace import curate

    sig = inspect.signature(curate)
    assert list(sig.parameters.keys()) == [
        "ledger",
        "task_prompt",
        "response",
        "cited_bullet_ids",
        "gt_correct",
        "reflector_proposals",
        "cfg",
    ]


def test_trace_off_csv_schema_baseline_is_unchanged() -> None:
    from apex_bench.runner import csv_headers

    baseline = csv_headers("grok_4_3_high")
    on = csv_headers("grok_4_3_high", with_trace=True)
    assert on[: len(baseline)] == baseline


def test_trace_on_csv_extends_baseline_at_end() -> None:
    from apex_bench.runner import _TRACE_CSV_COLUMNS, csv_headers

    baseline = csv_headers("grok_4_3_high")
    on = csv_headers("grok_4_3_high", with_trace=True)
    assert tuple(on[len(baseline) :]) == _TRACE_CSV_COLUMNS


def test_trace_and_dynamic_ledger_in_csv_headers_are_mutually_exclusive() -> None:
    import pytest

    from apex_bench.runner import csv_headers

    with pytest.raises(ValueError):
        csv_headers("m", with_dynamic_ledger=True, with_trace=True)


def test_trace_config_default_is_off() -> None:
    from apex_bench.trace.config import TraceConfig

    cfg = TraceConfig()
    assert cfg.enabled is False
    assert cfg.reflector_model is None
    assert cfg.curator_model is None


def test_run_options_default_trace_is_off() -> None:
    from apex_bench.runner import RunOptions

    fields = {f.name: f for f in dataclasses.fields(RunOptions)}
    assert "trace" in fields
    factory = fields["trace"].default_factory  # type: ignore[union-attr]
    assert factory().enabled is False


# Prompt content invariants ---------------------------------------------------


_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "src" / "apex_bench" / "trace" / "prompts"


def test_reflector_prompt_references_gt_bit() -> None:
    text = (_PROMPTS_DIR / "reflector_system.txt").read_text(encoding="utf-8").lower()
    assert "ground-truth" in text or "ground truth" in text
    assert "gt_correct" in text


def test_curator_prompt_references_gt_bit_and_proposals() -> None:
    text = (_PROMPTS_DIR / "curator_system.txt").read_text(encoding="utf-8").lower()
    assert "ground-truth" in text or "ground truth" in text
    assert "reflector" in text
    assert "proposals" in text


def test_injection_block_specifies_citation_format() -> None:
    text = (_PROMPTS_DIR / "generator_injection_block.txt").read_text(encoding="utf-8")
    assert "<citations>" in text
    assert "bullet-" in text
