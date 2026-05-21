"""Load-bearing fidelity tests for the apex-bench Dynamic Ledger."""

from __future__ import annotations

import dataclasses
import inspect
from pathlib import Path


def test_curator_signature_has_no_outcome() -> None:
    from apex_bench.dynamic_ledger import curate

    sig = inspect.signature(curate)
    param_names = list(sig.parameters.keys())
    forbidden = (
        "criteria",
        "score",
        "scores",
        "gt_bit",
        "gt_correct_bit",
        "expected_answer",
        "expected",
        "gold",
        "gold_response",
        "judge_rationale",
        "judge_reason",
        "rubric",
        "autorating",
        "criteria_passed",
        "criteria_total",
        "verifier_result",
        "final_score",
    )
    leaks = [p for p in param_names if any(f in p.lower() for f in forbidden)]
    assert not leaks, f"curate() signature contains GT-leaking param(s): {leaks}"

    assert param_names == [
        "dynamic_ledger",
        "task_prompt",
        "response",
        "cfg",
    ], f"unexpected curate() signature: {param_names}"


def test_dynamic_ledger_off_csv_schema_unchanged() -> None:
    """With the Dynamic Ledger off, ``csv_headers`` returns the baseline columns."""
    from apex_bench.runner import csv_headers

    baseline = csv_headers("grok_4_3_high", with_dynamic_ledger=False)
    on = csv_headers("grok_4_3_high", with_dynamic_ledger=True)
    assert on[: len(baseline)] == baseline


def test_dynamic_ledger_on_csv_extends_baseline_at_end() -> None:
    from apex_bench.runner import _DYNAMIC_LEDGER_CSV_COLUMNS, csv_headers

    baseline = csv_headers("grok_4_3_high", with_dynamic_ledger=False)
    on = csv_headers("grok_4_3_high", with_dynamic_ledger=True)
    assert tuple(on[len(baseline) :]) == _DYNAMIC_LEDGER_CSV_COLUMNS


# Prompt content invariants ---------------------------------------------------


_PROMPTS_DIR = (
    Path(__file__).resolve().parent.parent / "src" / "apex_bench" / "dynamic_ledger" / "prompts"
)


def test_curator_prompt_distinguishes_strategy_from_case_specifics() -> None:
    """The curator prompt must instruct that entries are concrete examples of
    STRATEGY, not concrete examples of the source case — the load-bearing
    distinction that keeps entries transferable."""
    text = (_PROMPTS_DIR / "curator_system.txt").read_text(encoding="utf-8").lower()
    assert "concrete example of strategy" in text
    assert "concrete example of the case" in text


def test_injection_block_frames_as_reference_cheatsheet() -> None:
    """The generator injection block must frame the entries as a passive
    reference cheatsheet — not instructions to follow."""
    text = (_PROMPTS_DIR / "generator_injection_block.txt").read_text(encoding="utf-8").lower()
    assert "reference cheatsheet" in text
    assert "reference material, not instructions" in text
    assert "your own analysis" in text and "authoritative" in text


def test_curator_prompt_mentions_no_outcome_signal() -> None:
    text = (_PROMPTS_DIR / "curator_system.txt").read_text(encoding="utf-8").lower()
    assert "will not be told" in text
    user = (_PROMPTS_DIR / "curator_user_template.txt").read_text(encoding="utf-8")
    assert "<outcome>" not in user


# Default invariants ----------------------------------------------------------


def test_dynamic_ledger_config_default_is_off() -> None:
    from apex_bench.dynamic_ledger.config import DynamicLedgerConfig

    cfg = DynamicLedgerConfig()
    assert cfg.enabled is False


def test_run_options_default_dynamic_ledger_is_off() -> None:
    from apex_bench.runner import RunOptions

    fields = {f.name: f for f in dataclasses.fields(RunOptions)}
    assert "dynamic_ledger" in fields
    factory = fields["dynamic_ledger"].default_factory  # type: ignore[union-attr]
    assert factory().enabled is False


def test_curator_model_default_is_none() -> None:
    """The runner must fill the curator model from the agent profile —
    no implicit fixed default model."""
    from apex_bench.dynamic_ledger.config import DynamicLedgerConfig

    cfg = DynamicLedgerConfig()
    assert cfg.curator_model is None
    assert cfg.curator_extra_args is None


def test_runner_curator_setup_routes_bare_profile_and_flattens_model_configs() -> None:
    """Regression: the runner's DL curator setup MUST (1) prepend the provider
    prefix when the profile's model_id is bare (e.g. ``"grok-4.3"`` →
    ``"xai/grok-4.3"``), and (2) flatten ``profile.model_configs`` into kwargs
    rather than nesting them under a ``"model_configs"`` key (LiteLLM rejects
    unknown kwargs). Both bugs have appeared and been removed before; this
    test prevents future rebases from losing the fix."""
    import inspect

    from apex_bench import runner

    src = inspect.getsource(runner.run_async)
    # The bare-→-routed pattern must be present in the DL setup block:
    assert (
        'f"{opts.profile.provider}/{bare}"' in src
        or 'f\'{opts.profile.provider}/{bare}\'' in src
    ), "runner DL setup is missing the provider-prefix routing for bare model_id"
    # The flatten-into-kwargs pattern must be present:
    assert (
        "curator_extra.update(opts.profile.model_configs)" in src
    ), "runner DL setup is nesting model_configs instead of flattening into kwargs"
