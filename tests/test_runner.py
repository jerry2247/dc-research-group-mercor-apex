"""Structural tests for the multi-task runner.

These tests exercise the resume/filter/stats machinery in pure Python — no
LLM calls, no Reducto, no network. They do NOT test the generate or grade
paths because those would require live API access.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apex_bench.dataset import Task
from apex_bench.paths import vendor_dir
from apex_bench.runner import (
    JudgeOverride,
    RunOptions,
    _agent_usage_fields,
    _missing_attachment_sections,
    _parsed_attachment_text_from_prompt,
    _preflight_credentials,
    _select_tasks,
    append_failure,
    append_row,
    calculate_stats,
    csv_headers,
    failure_log_path,
    load_completed_task_ids,
    manifest_path,
    sanitize_model_key,
    write_manifest,
)
from apex_bench.test_models import get_profile
from apex_bench.vendor_imports import vendor_cwd


def _make_task(tid: str, domain: str = "Consulting", prompt: str = "p") -> Task:
    return Task(task_id=tid, domain=domain, prompt=prompt, rubric_json="{}", attachments=())


def test_sanitize_model_key_matches_upstream_rule() -> None:
    assert sanitize_model_key("gpt-5.5") == "gpt_5_5"
    assert sanitize_model_key("grok-4.3") == "grok_4_3"
    assert sanitize_model_key("bedrock/us.anthropic") == "bedrock_us_anthropic"


def test_csv_headers_contains_all_expected_columns() -> None:
    h = csv_headers("gpt_5_5")
    assert h[:3] == ["task_id", "domain", "status"]
    assert "gpt_5_5_1_response" in h
    assert "gpt_5_5_1_score" in h
    assert "gpt_5_5_1_score_summary" in h
    assert "attachments_expected" in h
    assert "attachments_sent" in h
    assert "parsed_attachment_chars" in h
    assert "final_prompt_sha256" in h
    assert "agent_input_tokens" in h
    assert "agent_output_tokens" in h
    assert "agent_tokens" in h
    assert "agent_usage_available" in h
    assert "agent_usage_source" in h
    assert "agent_usage_consistent" in h
    assert "agent_cost_usd" not in h
    assert "agent_estimated_cost_usd" not in h
    assert "judge_tokens" not in h
    assert "judge_cost_usd" not in h
    assert "judge_model" in h
    assert "test_model_profile" in h


def test_select_tasks_domain_filter() -> None:
    tasks = [
        _make_task("1", "Consulting"),
        _make_task("2", "Finance"),
        _make_task("3", "Consulting"),
    ]
    opts = RunOptions(
        profile=get_profile("grok-4.3-low"),
        judge=JudgeOverride(),
        dataset_dir=Path("."),
        output_csv=Path("out.csv"),
        domain="Consulting",
    )
    selected = _select_tasks(tasks, opts)
    assert [t.task_id for t in selected] == ["1", "3"]


def test_select_tasks_start_and_limit() -> None:
    tasks = [_make_task(str(i), "Consulting") for i in range(10)]
    opts = RunOptions(
        profile=get_profile("grok-4.3-low"),
        judge=JudgeOverride(),
        dataset_dir=Path("."),
        output_csv=Path("out.csv"),
        domain="Consulting",
        start_index=3,
        limit=4,
    )
    assert [t.task_id for t in _select_tasks(tasks, opts)] == ["3", "4", "5", "6"]


def test_select_tasks_task_ids_overrides_domain_and_order() -> None:
    tasks = [
        _make_task("1", "Consulting"),
        _make_task("2", "Finance"),
        _make_task("3", "Legal"),
        _make_task("4", "Medicine"),
    ]
    opts = RunOptions(
        profile=get_profile("grok-4.3-low"),
        judge=JudgeOverride(),
        dataset_dir=Path("."),
        output_csv=Path("out.csv"),
        domain="Consulting",
        task_ids=("2", "4"),
    )
    selected = _select_tasks(tasks, opts)
    assert [t.task_id for t in selected] == ["2", "4"]


def test_select_tasks_limit_25_returns_full_domain(tmp_path: Path) -> None:
    """The user's intended pattern: --limit 25 picks exactly the domain's tasks."""
    tasks = [_make_task(str(i), "Finance") for i in range(25)] + [
        _make_task(str(100 + i), "Legal") for i in range(25)
    ]
    opts = RunOptions(
        profile=get_profile("grok-4.3-low"),
        judge=JudgeOverride(),
        dataset_dir=tmp_path,
        output_csv=tmp_path / "out.csv",
        domain="Finance",
        limit=25,
    )
    selected = _select_tasks(tasks, opts)
    assert len(selected) == 25
    assert {t.domain for t in selected} == {"Finance"}


def test_load_completed_task_ids_empty_when_no_file(tmp_path: Path) -> None:
    assert load_completed_task_ids(tmp_path / "nope.csv") == set()


def test_append_row_then_resume_skips_completed(tmp_path: Path) -> None:
    csv_p = tmp_path / "results.csv"
    headers = csv_headers("gpt_5_5")
    for tid, status in (("1", "completed"), ("2", "completed"), ("3", "pending")):
        append_row(
            csv_p,
            headers,
            {
                "task_id": tid,
                "domain": "Consulting",
                "status": status,
                "gpt_5_5_1_score": 50.0,
                "judge_model": "gpt-5.5",
                "test_model_profile": "gpt-5.5-medium",
                "test_model_id": "gpt-5.5",
            },
        )
    done = load_completed_task_ids(csv_p)
    assert done == {"1", "2"}


def test_failure_log_is_jsonl_sidecar(tmp_path: Path) -> None:
    csv_p = tmp_path / "results.csv"
    append_failure(
        csv_p,
        {
            "scope": "task",
            "status": "skipped",
            "task_id": "123",
            "error": "attachment parsing produced no text",
        },
    )
    failure_p = failure_log_path(csv_p)
    assert failure_p == tmp_path / "results.failures.jsonl"
    body = failure_p.read_text(encoding="utf-8")
    assert '"task_id": "123"' in body
    assert '"output_csv":' in body


def test_manifest_is_json_sidecar(tmp_path: Path) -> None:
    csv_p = tmp_path / "results.csv"
    write_manifest(csv_p, {"schema_version": 1, "status": "starting"})
    manifest_p = manifest_path(csv_p)
    assert manifest_p == tmp_path / "results.run_manifest.json"
    assert '"status": "starting"' in manifest_p.read_text(encoding="utf-8")


def test_attachment_audit_reads_vendor_final_prompt_block() -> None:
    prompt = (
        "Original task prompt\n\n"
        "==== Attached files content: ====\n\n"
        "=== first.pdf ===\nalpha\n\n"
        "=== data.csv ===\nbeta"
    )
    assert _parsed_attachment_text_from_prompt(prompt).startswith("=== first.pdf ===")
    assert _missing_attachment_sections(prompt, ["first.pdf", "data.csv"]) == []
    assert _missing_attachment_sections(prompt, ["first.pdf", "missing.xlsx"]) == ["missing.xlsx"]


def test_agent_usage_fields_are_provider_reported_and_cost_free() -> None:
    class FakeGenerationResult:
        total_tokens = 999

    fields = _agent_usage_fields(
        {
            "input_tokens": 123,
            "output_tokens": 45,
            "tokens_used": 168,
            "total_cost": 12.34,
        },
        FakeGenerationResult(),
    )
    assert fields == {
        "agent_input_tokens": 123,
        "agent_output_tokens": 45,
        "agent_tokens": 168,
        "agent_usage_available": True,
        "agent_usage_source": "provider_response_via_litellm",
        "agent_usage_consistent": True,
    }
    assert all("cost" not in key for key in fields)


def test_agent_usage_fields_flag_inconsistent_provider_usage() -> None:
    fields = _agent_usage_fields(
        {
            "input_tokens": 10,
            "output_tokens": 5,
            "tokens_used": 99,
        },
        object(),
    )
    assert fields["agent_usage_available"] is True
    assert fields["agent_usage_consistent"] is False


def test_vendor_cwd_temporarily_switches_and_restores() -> None:
    import os

    old = os.getcwd()
    with vendor_cwd():
        assert Path(os.getcwd()) == vendor_dir()
    assert os.getcwd() == old


def test_calculate_stats_basic(tmp_path: Path) -> None:
    csv_p = tmp_path / "results.csv"
    headers = csv_headers("grok_4_3")
    for tid, domain, score in (
        ("a", "Consulting", 60.0),
        ("b", "Consulting", 80.0),
        ("c", "Finance", 40.0),
    ):
        append_row(
            csv_p,
            headers,
            {
                "task_id": tid,
                "domain": domain,
                "status": "completed",
                "grok_4_3_1_score": score,
                "judge_model": "gpt-5.5",
                "test_model_profile": "grok-4.3-low",
                "test_model_id": "grok-4.3",
            },
        )
    stats = calculate_stats(csv_p, "grok_4_3")
    assert stats["total_completed"] == 3
    assert stats["overall_mean"] == 60.0
    assert stats["by_domain"]["Consulting"] == {"n": 2, "mean": 70.0}
    assert stats["by_domain"]["Finance"] == {"n": 1, "mean": 40.0}


def test_run_options_is_frozen() -> None:
    """RunOptions must be immutable so a running runner can't be mutated."""
    from dataclasses import FrozenInstanceError

    opts = RunOptions(
        profile=get_profile("grok-4.3-low"),
        judge=JudgeOverride(),
        dataset_dir=Path("."),
        output_csv=Path("out.csv"),
    )
    with pytest.raises(FrozenInstanceError):
        opts.limit = 5  # type: ignore[misc]


def test_preflight_credentials_fails_before_api_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("OPENAI_API_KEY", "XAI_API_KEY", "REDUCTO_API_KEY"):
        monkeypatch.setenv(key, "")

    opts = RunOptions(
        profile=get_profile("gpt-5.5-low"),
        judge=JudgeOverride(),
        dataset_dir=Path("."),
        output_csv=Path("out.csv"),
    )
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        _preflight_credentials(opts, [_make_task("1")])
