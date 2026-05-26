"""Load-bearing fidelity invariants for DC-RS.

Each test pins a system-level property of the implementation that, if
broken, would cause DC-RS to diverge from Suzgun et al.'s reference
or to leak information / domain assumptions it should not have.
"""

from __future__ import annotations

import inspect
from pathlib import Path


def test_dc_rs_config_default_is_off() -> None:
    from apex_bench.dc_rs.config import DCRSConfig

    cfg = DCRSConfig()
    assert cfg.enabled is False
    assert cfg.synthesizer_model is None
    assert cfg.top_k == 3


def test_settings_default_dc_rs_is_off() -> None:
    from apex_bench.config import Settings

    s = Settings.defaults()
    assert s.dc_rs.enabled is False


def test_csv_off_state_is_byte_identical_to_baseline() -> None:
    from apex_bench.runner import csv_headers

    baseline = csv_headers("grok_4_3_high")
    off = csv_headers("grok_4_3_high", with_dc_rs=False, with_trace=False)
    assert baseline == off


def test_csv_dc_rs_on_appends_known_columns_at_end() -> None:
    from apex_bench.runner import _DC_RS_CSV_COLUMNS, csv_headers

    baseline = csv_headers("grok_4_3_high")
    on = csv_headers("grok_4_3_high", with_dc_rs=True)
    assert tuple(on[len(baseline) :]) == _DC_RS_CSV_COLUMNS


def test_csv_mutex_dc_rs_and_trace_raises() -> None:
    import pytest

    from apex_bench.runner import csv_headers

    with pytest.raises(ValueError):
        csv_headers("m", with_dc_rs=True, with_trace=True)


def test_synthesizer_signature_has_no_outcome_inputs() -> None:
    """The synthesizer must NOT receive grading data of any kind. The
    accepted ``task_id`` parameter is for provenance tagging in
    cheatsheet entries (``(Reference: <task_id>, …)``) only — not a
    grading signal. This is the load-bearing fidelity invariant for
    the no-grading property of DC-RS."""
    from apex_bench.dc_rs import synthesize

    sig = inspect.signature(synthesize)
    params = list(sig.parameters.keys())
    assert "criteria" not in params
    assert "score" not in params
    assert "gt_correct" not in params
    assert "expected_answer" not in params
    assert "judge_rationale" not in params
    assert "rubric" not in params
    assert params == [
        "current_cheatsheet",
        "retrieved_entries_block",
        "task_prompt",
        "task_id",
        "cfg",
    ]


def test_synthesizer_prompt_has_no_code_execution_references() -> None:
    """apex-bench has no code-execution surface. The prompt must not
    reference Python execution or ``<execute_python>`` blocks."""
    prompt_dir = Path(__file__).parent.parent / "src" / "apex_bench" / "dc_rs" / "prompts"
    for name in ("synthesizer_prompt.txt", "generator_injection_template.txt"):
        body = (prompt_dir / name).read_text(encoding="utf-8")
        assert "<execute_python>" not in body, f"{name} references code execution"
        assert "execute_python" not in body.lower(), f"{name} references execute_python"


def test_synthesizer_prompt_has_no_domain_specific_terms() -> None:
    """The prompt must remain domain-agnostic — no benchmark-specific
    terminology that would prejudice the synthesizer toward one
    domain. The output cheatsheet is free to use domain-fluent
    vocabulary appropriate to the case; the *prompt instructions* are
    not."""
    import re

    forbidden = (
        # Domain names
        r"\bfinance\b", r"\bfinancial\b", r"\blegal\b", r"\bjurisdiction\b",
        r"\bmedicine\b", r"\bmedical\b", r"\bclinical\b", r"\bpatient\b",
        r"\bconsulting\b", r"\bconsultant\b",
        # Domain-specific terms a junior would expect to see in a finance prompt etc.
        r"\bM&A\b", r"\bLBO\b", r"\bMOIC\b", r"\bIRR\b(?!_)", r"\bEBITDA\b",
        r"\bWACC\b", r"\bDCF\b", r"\bGAAP\b", r"\bSEC\b",
        r"\bstatute\b", r"\battorney\b", r"\blawyer\b", r"\bdoctor\b",
        r"\bdiagnosis\b", r"\bsymptom\b", r"\bdrug\b",
    )
    prompt_dir = Path(__file__).parent.parent / "src" / "apex_bench" / "dc_rs" / "prompts"
    for name in ("synthesizer_prompt.txt", "generator_injection_template.txt"):
        body = (prompt_dir / name).read_text(encoding="utf-8")
        for pat in forbidden:
            hits = re.findall(pat, body, re.IGNORECASE)
            assert not hits, f"{name} leaks domain term {pat!r}: {hits}"


def test_generator_injection_template_has_cheatsheet_placeholder() -> None:
    prompt_dir = Path(__file__).parent.parent / "src" / "apex_bench" / "dc_rs" / "prompts"
    body = (prompt_dir / "generator_injection_template.txt").read_text(encoding="utf-8")
    assert "{cheatsheet}" in body


def test_synthesizer_prompt_has_four_placeholders() -> None:
    prompt_dir = Path(__file__).parent.parent / "src" / "apex_bench" / "dc_rs" / "prompts"
    body = (prompt_dir / "synthesizer_prompt.txt").read_text(encoding="utf-8")
    assert "{current_cheatsheet}" in body
    assert "{retrieved_entries}" in body
    assert "{task_prompt}" in body
    assert "{task_id}" in body


def test_synthesizer_prompt_uses_senior_partner_framing() -> None:
    prompt_dir = Path(__file__).parent.parent / "src" / "apex_bench" / "dc_rs" / "prompts"
    body = (prompt_dir / "synthesizer_prompt.txt").read_text(encoding="utf-8")
    assert "senior partner" in body.lower()
    assert "junior" in body.lower()


def test_generator_wrapper_uses_senior_partner_framing() -> None:
    prompt_dir = Path(__file__).parent.parent / "src" / "apex_bench" / "dc_rs" / "prompts"
    body = (prompt_dir / "generator_injection_template.txt").read_text(encoding="utf-8")
    assert "senior partner" in body.lower()
