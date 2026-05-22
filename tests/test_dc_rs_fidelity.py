"""Load-bearing fidelity invariants for DC-RS.

If any of these fails, the on/off invariants the rest of the harness
depends on no longer hold.
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
    """The synthesizer must NOT receive ``criteria``, ``score``,
    ``gt_correct``, ``expected_answer``, or ``judge_rationale``.
    This is the load-bearing fidelity invariant for the no-grading
    property of DC-RS."""
    from apex_bench.dc_rs import synthesize

    sig = inspect.signature(synthesize)
    params = list(sig.parameters.keys())
    assert "criteria" not in params
    assert "score" not in params
    assert "gt_correct" not in params
    assert "expected_answer" not in params
    assert "judge_rationale" not in params
    # And the only inputs are the three content placeholders + cfg:
    assert params == ["current_cheatsheet", "retrieved_entries_block", "task_prompt", "cfg"]


def test_dc_rs_prompts_have_no_code_execution_references() -> None:
    """apex-bench has no code-execution surface. The prompts must not
    reference Python execution or ``<execute_python>`` blocks."""
    prompt_dir = Path(__file__).parent.parent / "src" / "apex_bench" / "dc_rs" / "prompts"
    for name in (
        "synthesizer_system.txt",
        "synthesizer_user_template.txt",
        "generator_injection_template.txt",
    ):
        body = (prompt_dir / name).read_text(encoding="utf-8")
        assert "<execute_python>" not in body, f"{name} references code execution"
        # Also check the more general execution-tag pattern.
        assert "execute_python" not in body.lower(), f"{name} references execute_python"


def test_generator_injection_template_has_cheatsheet_placeholder() -> None:
    prompt_dir = Path(__file__).parent.parent / "src" / "apex_bench" / "dc_rs" / "prompts"
    body = (prompt_dir / "generator_injection_template.txt").read_text(encoding="utf-8")
    assert "{cheatsheet}" in body


def test_synthesizer_user_template_has_three_placeholders() -> None:
    prompt_dir = Path(__file__).parent.parent / "src" / "apex_bench" / "dc_rs" / "prompts"
    body = (prompt_dir / "synthesizer_user_template.txt").read_text(encoding="utf-8")
    assert "{current_cheatsheet}" in body
    assert "{retrieved_entries}" in body
    assert "{task_prompt}" in body
