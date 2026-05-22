"""Multi-task APEX runner.

This module is a *faithful fork* of the upstream Mercor reference runner
`vendor/apex_evals/examples/run_with_hf.py` (commit
6cbf3f43156bf332329abe76ed4a695fc71ec5b0, 2026-04-09). The loop semantics,
result-row shape, resume-by-completed-task mechanism, and end-of-run stats
aggregation are copied byte-for-byte from upstream. Only the following
points differ, all centralized at the top of `run_async`:

  1. The hardcoded upstream `MODELS` list is replaced by a single profile
     picked from `apex_bench.test_models` via the CLI `--model` flag.
     Project policy: one test model per invocation, one run per task.
     Re-runs against a different model are separate invocations.
  2. The hardcoded upstream `GRADING_MODEL = "gemini-2.5-flash"` is replaced
     by `apex_bench.config.DEFAULT_JUDGE_MODEL` (project default: gpt-5.5
     at OpenAI's medium reasoning effort).
  3. The hardcoded upstream `Path("prompt/...")` loads (which fail when CWD
     is not the vendor directory) are replaced by reads from the absolute
     vendor path via `apex_bench.paths.vendor_dir`. The grading template is
     always passed explicitly to `GradingTask` to work around the upstream
     CWD-dependent module load bug; see `docs/HARNESS_NOTES.md`.

Everything else — per-task generate→grade→write loop, per-criterion judge
calls, status="completed" resume, median/mean stats — is preserved.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import logging
import os
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apex_bench import __version__
from apex_bench.azure_routing import AzureConfig, route_model_id
from apex_bench.config import (
    DEFAULT_JUDGE_MAX_TOKENS,
    DEFAULT_JUDGE_MODEL,
    DEFAULT_JUDGE_TEMPERATURE,
)
from apex_bench.dataset import Task, csv_path, load_tasks, validate
from apex_bench.dc_rs.config import DCRSConfig
from apex_bench.paths import repo_root, vendor_dir
from apex_bench.test_models import TestModelProfile
from apex_bench.trace.config import TraceConfig
from apex_bench.vendor_imports import vendor_cwd

log = logging.getLogger(__name__)

ATTACHMENT_BLOCK_MARKER = "==== Attached files content: ===="


# -----------------------------------------------------------------------------
# Reasoning-model judge handling
# -----------------------------------------------------------------------------

# OpenAI reasoning models (gpt-5 family, o-series) reject any temperature
# other than 1.0. If the user (or the project default) supplies something
# else, we coerce it to 1.0 with a warning rather than have the run blow up
# on Attempt 7 of a hopeless retry loop -- which is what happened to the
# first real apex-bench run on 2026-05-19.
_REASONING_JUDGE_PREFIXES: tuple[str, ...] = ("gpt-5", "o1", "o3", "o4")


def _safe_judge_temperature(model_id: str, requested: float) -> float:
    """Return a temperature compatible with the judge model.

    For OpenAI reasoning models (``gpt-5.x``, ``o``-series), the API only
    accepts ``temperature == 1.0``. We coerce any other value to 1.0 and
    emit a warning. Other models (Gemini, Claude, Grok, ...) receive the
    requested value unchanged.
    """
    bare = model_id.split("/")[-1] if "/" in model_id else model_id
    is_reasoning = any(bare.startswith(p) for p in _REASONING_JUDGE_PREFIXES)
    if is_reasoning and requested != 1.0:
        log.warning(
            "judge %s is a reasoning model -- coercing temperature %.3f to 1.0 "
            "(OpenAI rejects any non-default temperature for reasoning models)",
            model_id,
            requested,
        )
        return 1.0
    return requested


# -----------------------------------------------------------------------------
# Public types
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class JudgeOverride:
    """Optional grading-side overrides. Defaults mirror config.DEFAULT_JUDGE_*."""

    model_id: str = DEFAULT_JUDGE_MODEL
    temperature: float = DEFAULT_JUDGE_TEMPERATURE
    max_tokens: int = DEFAULT_JUDGE_MAX_TOKENS


@dataclass(frozen=True)
class RunOptions:
    """One full apex-bench run.

    All paths are absolute. The runner does not consult environment variables
    except for the API keys that LiteLLM, boto3, and Reducto read directly.
    """

    profile: TestModelProfile
    judge: JudgeOverride
    dataset_dir: Path
    output_csv: Path
    domain: str | None = None
    task_ids: tuple[str, ...] | None = None
    start_index: int = 0
    limit: int | None = None
    dc_rs: DCRSConfig = field(default_factory=DCRSConfig)
    """DC Retrieval Synthesis configuration. When ``enabled=False``
    (default) the runner takes the baseline code path and the CSV schema
    is byte-identical to the no-memory shape. See ``docs/DC_RS_PRD.md``."""

    trace: TraceConfig = field(default_factory=TraceConfig)
    """TRACE (uses-GT) configuration. Mutually exclusive with DC-RS —
    at most one of ``dc_rs.enabled`` and ``trace.enabled`` may be True
    per run. See ``docs/TRACE_PRD.md``."""

    azure: AzureConfig = field(default_factory=AzureConfig)
    """Azure-OpenAI routing for GPT-5.5 chat completions. When
    ``enabled=True`` any ``gpt-5.5*`` model id (judge, test profile,
    DC-RS synthesizer, TRACE reflector/curator) is rewritten to
    ``azure/<deployment_name>`` before reaching LiteLLM. The embedding
    model (``text-embedding-3-large``) always uses OpenAI regardless
    of this setting. See ``apex_bench/azure_routing.py``."""


@dataclass(frozen=True)
class TaskOutcome:
    task_id: str
    domain: str
    status: str  # "completed" | "skipped"
    response_chars: int
    percentage_score: float | None
    points_earned: float | None
    points_possible: int | None


# -----------------------------------------------------------------------------
# CSV schema — preserved from upstream run_with_hf.py:55-61
# -----------------------------------------------------------------------------

# Upstream uses one column-suffix scheme per (model_key, run_index). We hold
# RUNS_PER_TASK=1 and run exactly one test-model profile per invocation, so
# our column suffix is `<model_key>_1_<field>`.
RESULT_FIELDS = ("response", "score", "score_summary")


def sanitize_model_key(model_id: str) -> str:
    """Upstream sanitize() — identical to run_with_hf.py:47."""
    return model_id.replace("-", "_").replace(".", "_").replace("/", "_")


_TRACE_CSV_COLUMNS = (
    "trace_enabled",
    "trace_snapshot_index_before",
    "retrieved_bullet_count",
    "retrieved_bullet_ids",
    "citations_present",
    "citations_count",
    "citations_malformed_count",
    "trailing_chars_after_citations",
    "gt_correct_bit",
    "reflector_proposal_count",
    "curator_create_count",
    "curator_create_blocked_count",
    "curator_update_count",
    "curator_delete_count",
    "curator_consolidate_count",
    "curator_no_op",
    "trace_active_bullet_count_after",
    "trace_total_bullet_count_after",
    "trace_total_active_chars_after",
    "reflector_prompt_tokens",
    "reflector_completion_tokens",
    "reflector_wall_seconds",
    "curator_prompt_tokens",
    "curator_completion_tokens",
    "curator_wall_seconds",
)


_DC_RS_CSV_COLUMNS = (
    "dc_rs_enabled",
    "dc_rs_bank_size_before",
    "dc_rs_bank_size_after",
    "dc_rs_retrieved_count",
    "dc_rs_retrieved_bank_ids",
    "dc_rs_appended_bank_id",
    "synthesizer_prompt_tokens",
    "synthesizer_completion_tokens",
    "synthesizer_wall_seconds",
    "synthesizer_cheatsheet_chars",
    "synthesizer_used_fallback",
)


def csv_headers(
    model_key: str,
    *,
    with_dc_rs: bool = False,
    with_trace: bool = False,
) -> list[str]:
    """Per-task row schema. Preserves upstream's shape, adds audit columns.

    Columns we inherit from upstream (`run_with_hf.py:55-61`):
        task_id, domain, status,
        <model_key>_1_response, <model_key>_1_score, <model_key>_1_score_summary,
        generation_chars, wall_time_seconds,
        judge_model, test_model_profile, test_model_id

    Additive audit columns record the vendor's existing telemetry and a
    fingerprint of what actually reached the model. They do not change
    generation, grading, resume, or scoring behavior.

    When ``with_dc_rs`` is True we additionally append the DC-RS columns
    at the END of the row. This preserves the no-memory header order
    byte-identical (a load-bearing fidelity invariant).
    """
    base = ["task_id", "domain", "status"]
    for field_name in RESULT_FIELDS:
        base.append(f"{model_key}_1_{field_name}")
    base.extend(
        [
            "generation_chars",
            "wall_time_seconds",
            "attachments_expected",
            "attachments_sent",
            "parsed_attachment_chars",
            "final_prompt_chars",
            "final_prompt_sha256",
            "agent_input_tokens",
            "agent_output_tokens",
            "agent_tokens",
            "agent_usage_available",
            "agent_usage_source",
            "agent_usage_consistent",
            "judge_model",
            "test_model_profile",
            "test_model_id",
        ]
    )
    if with_dc_rs and with_trace:
        raise ValueError("with_dc_rs and with_trace are mutually exclusive")
    if with_dc_rs:
        base.extend(_DC_RS_CSV_COLUMNS)
    if with_trace:
        base.extend(_TRACE_CSV_COLUMNS)
    return base


# -----------------------------------------------------------------------------
# Vendor-template loaders (run-time so paths resolve correctly)
# -----------------------------------------------------------------------------


def _read_response_generation_template() -> str:
    """Returns the response-generation prompt CONTENT.

    We substitute {{Domain}} and {{Prompt}} into this ourselves and pass the
    resulting prompt to GenerationTask, so the file's content is what we
    need (not the path).
    """
    p = vendor_dir() / "prompt" / "response_generation_prompt.txt"
    if not p.is_file():
        raise RuntimeError(
            f"missing vendor response_generation_prompt.txt at {p}. Did `make install` succeed?"
        )
    return p.read_text(encoding="utf-8")


def _grading_template_path() -> str:
    """Returns the ABSOLUTE PATH to the grading prompt template, as a string.

    The vendor's GradingTask.grading_prompt_template is documented as
    Optional[str], with _resolve_prompt_template() doing:
        candidate = Path(template); if candidate.exists(): return candidate.read_text(); else return template

    That check is unguarded against macOS ENAMETOOLONG: if you pass the
    template *content* (>255 chars), Path.exists() raises OSError instead
    of returning False. So we pass the PATH and let the vendor read the
    file itself. Confirmed by the trace from a real run on 2026-05-19.
    """
    p = vendor_dir() / "prompt" / "grading_prompt.txt"
    if not p.is_file():
        raise RuntimeError(f"missing vendor grading_prompt.txt at {p}. Did `make install` succeed?")
    return str(p)


# -----------------------------------------------------------------------------
# Resume / IO  — direct ports of upstream
# -----------------------------------------------------------------------------


def load_completed_task_ids(output_csv: Path) -> set[str]:
    """Port of upstream load_completed_tasks() at run_with_hf.py:77-86."""
    if not output_csv.is_file():
        return set()
    completed: set[str] = set()
    with output_csv.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "completed":
                completed.add(row.get("task_id", ""))
    return completed


def append_row(output_csv: Path, headers: list[str], row: dict) -> None:
    """Port of upstream save_result() at run_with_hf.py:89-93."""
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    new_file = not output_csv.is_file()
    with output_csv.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def failure_log_path(output_csv: Path) -> Path:
    """Sidecar JSONL file for tasks that were selected but not completed."""
    return output_csv.with_name(f"{output_csv.stem}.failures.jsonl")


def manifest_path(output_csv: Path) -> Path:
    """Sidecar JSON manifest describing the exact run configuration."""
    return output_csv.with_name(f"{output_csv.stem}.run_manifest.json")


def append_failure(output_csv: Path, failure: dict[str, Any]) -> None:
    """Persist skipped-task context without polluting the upstream-style CSV."""
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": _utc_now(),
        "output_csv": str(output_csv),
        **failure,
    }
    with failure_log_path(output_csv).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_manifest(output_csv: Path, manifest: dict[str, Any]) -> None:
    """Write a deterministic JSON manifest next to the result CSV."""
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    manifest_path(output_csv).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _parsed_attachment_text_from_prompt(final_prompt: str) -> str:
    """Return the vendor-appended attachment block, or empty string if absent."""
    if ATTACHMENT_BLOCK_MARKER not in final_prompt:
        return ""
    return final_prompt.split(ATTACHMENT_BLOCK_MARKER, 1)[1].strip()


def _missing_attachment_sections(final_prompt: str, filenames: list[str]) -> list[str]:
    parsed_text = _parsed_attachment_text_from_prompt(final_prompt)
    return [name for name in filenames if f"=== {name} ===" not in parsed_text]


def _agent_usage_fields(gen_row: dict[str, Any], gen_result: Any) -> dict[str, Any]:
    """Extract provider-reported agent usage from the vendored generation result.

    The vendored harness fills these from `response.usage.prompt_tokens`,
    `response.usage.completion_tokens`, and `response.usage.total_tokens`.
    We do not compute or save cost here because the exposed cost field is a
    LiteLLM estimate, not a provider billing value.
    """
    input_tokens = int(gen_row.get("input_tokens", 0) or 0)
    output_tokens = int(gen_row.get("output_tokens", 0) or 0)
    total_tokens = int(gen_row.get("tokens_used", 0) or getattr(gen_result, "total_tokens", 0) or 0)
    usage_available = input_tokens > 0 or output_tokens > 0 or total_tokens > 0
    return {
        "agent_input_tokens": input_tokens,
        "agent_output_tokens": output_tokens,
        "agent_tokens": total_tokens,
        "agent_usage_available": usage_available,
        "agent_usage_source": "provider_response_via_litellm" if usage_available else "unavailable",
        "agent_usage_consistent": total_tokens == input_tokens + output_tokens,
    }


def _git_output(args: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo_root(),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _vendor_upstream_commit() -> str | None:
    upstream_md = vendor_dir() / "UPSTREAM.md"
    if not upstream_md.is_file():
        return None
    for line in upstream_md.read_text(encoding="utf-8").splitlines():
        if "Upstream commit" in line and "`" in line:
            parts = line.split("`")
            if len(parts) >= 2:
                return parts[1]
    return None


def _template_sha256s() -> dict[str, str | None]:
    prompt_dir = vendor_dir() / "prompt"
    return {
        "response_generation_prompt.txt": _sha256_file(
            prompt_dir / "response_generation_prompt.txt"
        ),
        "grading_prompt.txt": _sha256_file(prompt_dir / "grading_prompt.txt"),
    }


def _redact_profile_kwargs(profile: TestModelProfile) -> dict[str, Any]:
    """Profile kwargs are persisted because they are run-critical and secret-free."""
    return profile.to_model_config_kwargs()


def build_run_manifest(
    opts: RunOptions,
    selected: list[Task],
    pending: list[Task],
    headers: list[str],
    *,
    status: str,
    saved: int = 0,
    skipped: int = 0,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe the exact non-secret run state for reproducibility review."""
    git_status = _git_output(["status", "--short"])
    dataset_csv = csv_path(opts.dataset_dir)
    judge_temperature = _safe_judge_temperature(opts.judge.model_id, opts.judge.temperature)
    return {
        "schema_version": 1,
        "status": status,
        "created_or_updated_at": _utc_now(),
        "apex_bench_version": __version__,
        "run_policy": {
            "runs_per_task": 1,
            "domain_filter": opts.domain,
            "task_ids": list(opts.task_ids or ()),
            "start_index": opts.start_index,
            "limit": opts.limit,
        },
        "repo": {
            "root": str(repo_root()),
            "head": _git_output(["rev-parse", "HEAD"]),
            "dirty": bool(git_status),
            "dirty_status_short": git_status.splitlines() if git_status else [],
        },
        "vendor": {
            "path": str(vendor_dir()),
            "mercor_apex_evals_commit": _vendor_upstream_commit(),
            "prompt_template_sha256": _template_sha256s(),
        },
        "dataset": {
            "dir": str(opts.dataset_dir),
            "csv": str(dataset_csv),
            "csv_sha256": _sha256_file(dataset_csv),
            "selected_tasks": len(selected),
            "pending_tasks_at_start": len(pending),
            "task_ids": [t.task_id for t in selected],
            "domains": sorted({t.domain for t in selected}),
        },
        "test_model": {
            "profile": opts.profile.name,
            "provider": opts.profile.provider,
            "model_id": opts.profile.model_id,
            "model_config_kwargs": _redact_profile_kwargs(opts.profile),
        },
        "judge": {
            "model_id": opts.judge.model_id,
            "max_tokens": opts.judge.max_tokens,
            "requested_temperature": opts.judge.temperature,
            "effective_temperature": judge_temperature,
        },
        "outputs": {
            "csv": str(opts.output_csv),
            "failures_jsonl": str(failure_log_path(opts.output_csv)),
            "headers": headers,
        },
        "progress": {
            "saved_this_invocation": saved,
            "skipped_this_invocation": skipped,
            "stats": stats or {},
        },
    }


def _required_api_key(model_id: str, provider: str | None = None) -> str | None:
    if provider == "azure" or model_id.startswith("azure/"):
        return "AZURE_API_KEY"
    if provider == "xai" or model_id.startswith("xai/") or model_id.startswith("grok"):
        return "XAI_API_KEY"
    if provider == "openai" or model_id.startswith(("openai/", "gpt-", "o1", "o3", "o4")):
        return "OPENAI_API_KEY"
    if provider == "anthropic-bedrock" or model_id.startswith("bedrock/"):
        return "AWS_ACCESS_KEY_ID"
    if model_id.startswith(("anthropic/", "claude")):
        return "ANTHROPIC_API_KEY"
    if model_id.startswith(("gemini/", "gemini", "google/")):
        return "GOOGLE_API_KEY"
    return None


def _preflight_credentials(opts: RunOptions, selected: list[Task]) -> None:
    """Fail before a long run if required credentials are obviously missing."""
    if not selected:
        return

    try:
        from dotenv import load_dotenv

        load_dotenv(repo_root() / ".env", override=False)
    except Exception:
        pass

    missing: list[str] = []
    routed_test = route_model_id(opts.profile.model_id, cfg=opts.azure)
    routed_judge = route_model_id(opts.judge.model_id, cfg=opts.azure)
    test_key = _required_api_key(
        routed_test,
        "azure" if routed_test.startswith("azure/") else opts.profile.provider,
    )
    judge_key = _required_api_key(routed_judge)
    for key in (test_key, judge_key):
        if key and not os.environ.get(key) and key not in missing:
            missing.append(key)
    if any(t.attachments for t in selected) and not os.environ.get("REDUCTO_API_KEY"):
        missing.append("REDUCTO_API_KEY")
    # Embeddings always go through OpenAI even when chat is routed to Azure.
    if (
        (opts.dc_rs.enabled or opts.trace.enabled)
        and not os.environ.get("OPENAI_API_KEY")
        and "OPENAI_API_KEY" not in missing
    ):
        missing.append("OPENAI_API_KEY")
    if missing:
        raise RuntimeError(
            "missing required environment variable(s): "
            + ", ".join(missing)
            + ". Load your .env or export the keys before running apex-bench."
        )


# -----------------------------------------------------------------------------
# Per-task generate + grade  — direct port of upstream process_task()
# -----------------------------------------------------------------------------


async def _process_task(
    task: Task,
    profile: TestModelProfile,
    judge: JudgeOverride,
    response_template: str,
    grading_template_path: str,
    *,
    dc_rs_runtime: Any | None = None,  # type: DCRSRuntime | None
    trace_runtime: Any | None = None,  # type: TraceRuntime | None
    azure_cfg: AzureConfig | None = None,
) -> tuple[str, dict] | tuple[None, str]:
    """Generate and grade one task. Returns (status, row_dict) or (None, error).

    `status` is "completed" on success. If any sub-step fails the task is
    skipped, mirroring upstream behavior at run_with_hf.py:144-191 — a task
    row is written ONLY if all (model x run) combinations succeed.

    When ``dc_rs_runtime`` is None, the function takes the BASELINE code
    path — no DC-RS imports, no retrieval, no synthesizer, no extra CSV
    columns. This is the byte-identical baseline preserved by the
    ``test_dc_rs_off_csv_schema_unchanged`` fidelity test.

    When ``dc_rs_runtime`` is provided (DC-RS is on), two hooks fire:
    (A) embed the prompt, retrieve the top-k most similar past pairs from
    the domain bank, call the synthesizer to produce a fresh cheatsheet,
    prepend the cheatsheet block to the user-prompt slot; (B) after
    grading, append ``(prompt, deliverable, prompt_embedding)`` to the
    bank. None of the GT data (criteria, scores, expected answer) is
    threaded into the synthesizer — see
    ``test_synthesizer_signature_has_no_outcome``.
    """
    # Lazy imports so module-level import works without the vendor install.
    with vendor_cwd():
        from generation import Attachment as VendorAttachment
        from generation import (
            GenerationTask,
            ModelConfig,
            run_generation_task_async,
        )
        from grading import (
            GradingModelConfig,
            GradingTask,
            run_grading_task_async,
        )

    model_key = sanitize_model_key(profile.model_id)
    prefix = f"{model_key}_1"

    # --- DC-RS Hook A: retrieve + synthesize + prepend cheatsheet block ----
    # Computes the per-task prompt fragment that augments ``task.prompt``.
    # When DC-RS is off ``augmented_user_prompt is task.prompt`` (identity)
    # so the downstream substitution is byte-identical to the baseline.
    augmented_user_prompt = task.prompt
    dc_rs_csv: dict[str, Any] = {}
    q_emb: list[float] = []
    if dc_rs_runtime is not None:
        from apex_bench.dc_rs import (
            augment_user_prompt as dc_rs_augment,
        )
        from apex_bench.dc_rs import (
            format_retrieved_entries as dc_rs_format_entries,
        )
        from apex_bench.dc_rs import (
            retrieve as dc_rs_retrieve,
        )
        from apex_bench.dc_rs import (
            synthesize as dc_rs_synthesize,
        )
        from apex_bench.dc_rs.runtime import dc_rs_csv_fragment_empty

        dc_rs_csv = dc_rs_csv_fragment_empty()
        bank = dc_rs_runtime.bank_for(task.domain)
        dc_rs_csv["dc_rs_bank_size_before"] = len(bank.entries)
        try:
            q_emb = dc_rs_runtime.embed.embed([task.prompt])[0]
            retrieved = dc_rs_retrieve(
                bank,
                query_embedding=q_emb,
                k=dc_rs_runtime.cfg.top_k,
            )
        except Exception as exc:
            log.warning(
                "dc-rs: retrieval failed for task=%s domain=%s (%s); "
                "proceeding without retrieval",
                task.task_id,
                task.domain,
                exc,
            )
            retrieved = []
            q_emb = []
        dc_rs_csv["dc_rs_retrieved_count"] = len(retrieved)
        dc_rs_csv["dc_rs_retrieved_bank_ids"] = json.dumps(
            [r.entry.bank_id for r in retrieved]
        )
        retrieved_block = dc_rs_format_entries(retrieved)
        current_ch = dc_rs_runtime.cheatsheet_for(task.domain)
        try:
            syn = dc_rs_synthesize(
                current_cheatsheet=current_ch,
                retrieved_entries_block=retrieved_block,
                task_prompt=task.prompt,
                cfg=dc_rs_runtime.cfg,
            )
            new_ch = syn.cheatsheet
            dc_rs_runtime.write_cheatsheet(task.domain, new_ch)
            dc_rs_runtime.archive_cheatsheet(task.domain, task.task_id, new_ch)
            dc_rs_runtime.append_synth_log(
                task.domain,
                {
                    "task_id": task.task_id,
                    "retrieved_bank_ids": [r.entry.bank_id for r in retrieved],
                    "retrieved_similarities": [round(r.similarity, 4) for r in retrieved],
                    "prompt_tokens": syn.prompt_tokens,
                    "completion_tokens": syn.completion_tokens,
                    "wall_seconds": syn.wall_seconds,
                    "used_fallback": syn.used_fallback,
                    "cheatsheet_chars": len(new_ch),
                },
            )
            dc_rs_csv["synthesizer_prompt_tokens"] = syn.prompt_tokens
            dc_rs_csv["synthesizer_completion_tokens"] = syn.completion_tokens
            dc_rs_csv["synthesizer_wall_seconds"] = syn.wall_seconds
            dc_rs_csv["synthesizer_cheatsheet_chars"] = len(new_ch)
            dc_rs_csv["synthesizer_used_fallback"] = syn.used_fallback
            augmented_user_prompt = dc_rs_augment(task.prompt, cheatsheet=new_ch)
        except Exception as exc:
            log.warning(
                "dc-rs: synthesizer failed for task=%s domain=%s (%s); "
                "proceeding with the un-augmented prompt",
                task.task_id,
                task.domain,
                exc,
            )

    # --- TRACE Hook A: retrieve + augment user prompt ----------------------
    trace_csv: dict[str, Any] = {}
    retrieved_bullets: list[Any] = []
    trace_snapshot_index_before = 0
    if trace_runtime is not None:
        from apex_bench.trace import augment_user_prompt as trace_augment
        from apex_bench.trace import retrieve as trace_retrieve
        from apex_bench.trace.runtime import trace_csv_fragment_empty

        trace_csv = trace_csv_fragment_empty()
        tstore = trace_runtime.store_for(task.domain)
        trace_snapshot_index_before = trace_runtime.next_ordinal.get(task.domain, 0)
        trace_csv["trace_snapshot_index_before"] = trace_snapshot_index_before
        try:
            q_emb = trace_runtime.embed.embed([task.prompt])[0]
            retrieved_bullets = trace_retrieve(
                tstore, query_embedding=q_emb, k=trace_runtime.cfg.top_k_per_axis
            )
        except Exception as exc:
            log.warning(
                "trace: retrieval failed for task=%s domain=%s (%s); proceeding without retrieval",
                task.task_id,
                task.domain,
                exc,
            )
            retrieved_bullets = []
        trace_csv["retrieved_bullet_count"] = len(retrieved_bullets)
        trace_csv["retrieved_bullet_ids"] = json.dumps([b.bullet_id for b in retrieved_bullets])
        if retrieved_bullets:
            augmented_user_prompt = trace_augment(task.prompt, bullets=retrieved_bullets)

    # --- Build prompt + attachments (same as upstream) ---
    prompt = response_template.replace("{{Domain}}", task.domain).replace(
        "{{Prompt}}", augmented_user_prompt
    )
    attachments = [
        VendorAttachment(filename=a.path.name, url=f"file://{a.path}")
        for a in task.attachments
        if a.exists
    ]
    missing = [a for a in task.attachments if not a.exists]
    if missing:
        log.warning(
            "task %s: %d attachment file(s) missing on disk: %s",
            task.task_id,
            len(missing),
            [a.rel_path for a in missing],
        )
        return None, f"attachment file(s) missing on disk: {[a.rel_path for a in missing]}"

    started = time.time()

    # --- Generate ---
    azure_eff = azure_cfg or AzureConfig()
    try:
        gen_kwargs = profile.to_model_config_kwargs()
        # Route the test-model id through Azure when enabled.
        gen_kwargs["model_id"] = route_model_id(gen_kwargs["model_id"], cfg=azure_eff)
        gen_task = GenerationTask(
            prompt=prompt,
            models=[ModelConfig(**gen_kwargs)],
            attachments=attachments or None,
        )
        gen_result = await run_generation_task_async(gen_task)
    except Exception as exc:
        return None, f"generation raised: {type(exc).__name__}: {exc}"

    if not gen_result.results or not gen_result.results[0].get("success"):
        err = (
            gen_result.results[0].get("error_message", "unknown error")
            if gen_result.results
            else "no results"
        )
        return None, f"generation failed: {err}"
    gen_row = gen_result.results[0]
    response = gen_row.get("response", "") or ""

    # DC-RS does not rewrite the deliverable. TRACE parses and strips
    # a `<citations>` tag on the last line of the response.
    cited_bullet_ids: list[str] = []
    response_for_grading = response
    if trace_runtime is not None:
        from apex_bench.trace import extract_and_strip_citations

        extract = extract_and_strip_citations(response)
        trace_csv["citations_present"] = extract.citations_present
        trace_csv["citations_count"] = len(extract.cited_bullet_ids)
        trace_csv["citations_malformed_count"] = extract.citations_malformed_count
        trace_csv["trailing_chars_after_citations"] = extract.trailing_chars_after_citations
        cited_bullet_ids = list(extract.cited_bullet_ids)
        if extract.citations_present:
            response_for_grading = extract.stripped_response

    if not response_for_grading.strip():
        return None, "generation returned empty response"
    if not task.rubric_json.strip():
        return None, "task has empty rubric — skip"

    final_prompt = str(gen_row.get("final_prompt") or "")
    parsed_attachments = _parsed_attachment_text_from_prompt(final_prompt)
    if attachments and not parsed_attachments:
        return None, "attachment parsing produced no text; refusing to score prompt-only run"
    if attachments and ATTACHMENT_BLOCK_MARKER not in final_prompt:
        return None, "final prompt is missing the vendor attachment-content block"
    missing_sections = _missing_attachment_sections(
        final_prompt,
        [attachment.filename for attachment in attachments],
    )
    if missing_sections:
        return None, f"attachment parsing missing section(s): {missing_sections}"

    # --- Grade ---
    judge_cfg = GradingModelConfig(
        model_id=route_model_id(judge.model_id, cfg=azure_eff),
        max_tokens=judge.max_tokens,
        temperature=_safe_judge_temperature(judge.model_id, judge.temperature),
    )
    # Pass the PATH (not the content) -- see _grading_template_path() for why.
    grading_task = GradingTask(
        solution=response_for_grading,
        rubric=task.rubric_json,
        grading_model=judge_cfg,
        grading_prompt_template=grading_template_path,
    )
    try:
        grade_result = await run_grading_task_async(grading_task)
    except Exception as exc:
        return None, f"grading raised: {type(exc).__name__}: {exc}"
    if grade_result.grading_error:
        return None, f"grading failed: {grade_result.grading_error}"
    if not grade_result.criteria_results:
        return None, "grading returned no criteria"
    failed_criteria = [
        cr for cr in grade_result.criteria_results if cr.get("grading_success") is False
    ]
    if failed_criteria:
        labels = [
            str(cr.get("criterion_key") or cr.get("criteria") or "<unknown>")
            for cr in failed_criteria[:5]
        ]
        suffix = "" if len(failed_criteria) <= 5 else f" (+{len(failed_criteria) - 5} more)"
        return None, f"grading failed for criterion call(s): {labels}{suffix}"

    # --- Attach per-criterion autorating into the rubric for score_summary ---
    rubric_dict = json.loads(task.rubric_json)
    if isinstance(rubric_dict, list):
        rubric_flat: dict = {}
        for entry in rubric_dict:
            if isinstance(entry, dict):
                rubric_flat.update(entry)
        rubric_dict = rubric_flat
    for cr in grade_result.criteria_results:
        key = cr.get("criterion_key")
        if isinstance(key, str) and key in rubric_dict and isinstance(rubric_dict[key], dict):
            rubric_dict[key]["autorating"] = bool(cr.get("autorating"))
            rubric_dict[key]["reason"] = cr.get("reason", "")

    elapsed = time.time() - started

    # Agent token usage is copied from the provider response as surfaced by
    # LiteLLM through the vendored harness. Cost is intentionally omitted:
    # this path only exposes LiteLLM's local price-map estimate, not an exact
    # provider-billed charge. Judge usage is also omitted because it is shared
    # evaluation overhead, not a model-output metric for these comparisons.
    usage_fields = _agent_usage_fields(gen_row, gen_result)

    row = {
        "task_id": task.task_id,
        "domain": task.domain,
        "status": "completed",
        f"{prefix}_response": response,
        f"{prefix}_score": round(grade_result.percentage_score, 2),
        f"{prefix}_score_summary": json.dumps(rubric_dict, ensure_ascii=False),
        "generation_chars": len(response),
        "wall_time_seconds": round(elapsed, 2),
        "attachments_expected": len(task.attachments),
        "attachments_sent": len(attachments),
        "parsed_attachment_chars": len(parsed_attachments),
        "final_prompt_chars": len(final_prompt),
        "final_prompt_sha256": _sha256_text(final_prompt),
        **usage_fields,
        "judge_model": judge.model_id,
        "test_model_profile": profile.name,
        "test_model_id": profile.model_id,
    }

    # --- DC-RS Hook B: append the new (prompt, deliverable) pair to the
    # per-domain bank. NO ground-truth signal is consumed. Per the
    # test_synthesizer_signature_has_no_outcome fidelity test.
    if dc_rs_runtime is not None:
        if not q_emb:
            # Hook A failed to embed the prompt; nothing to append.
            dc_rs_csv["dc_rs_bank_size_after"] = len(
                dc_rs_runtime.bank_for(task.domain).entries
            )
        else:
            try:
                bank_id = dc_rs_runtime.append_entry(
                    domain=task.domain,
                    task_id=task.task_id,
                    task_prompt=task.prompt,
                    deliverable=response_for_grading,
                    prompt_embedding=q_emb,
                )
                dc_rs_csv["dc_rs_appended_bank_id"] = bank_id
            except Exception as exc:
                log.warning(
                    "dc-rs: bank append failed for task=%s domain=%s (%s); "
                    "the cheatsheet was already written for this task but the "
                    "pair will not contribute to retrieval on later tasks",
                    task.task_id,
                    task.domain,
                    exc,
                )
            dc_rs_csv["dc_rs_bank_size_after"] = len(
                dc_rs_runtime.bank_for(task.domain).entries
            )
        row.update(dc_rs_csv)

    # --- TRACE Hook B: bump counters, reflect, curate, apply, persist ------
    if trace_runtime is not None:
        from apex_bench.trace import (
            apply_ops as trace_apply_ops,
        )
        from apex_bench.trace import (
            curate as trace_curate,
        )
        from apex_bench.trace import (
            reflect as trace_reflect,
        )

        tstore = trace_runtime.store_for(task.domain)
        gt_correct = grade_result.percentage_score >= 99.0
        trace_csv["gt_correct_bit"] = gt_correct
        trace_runtime.record_citations(task.domain, cited=cited_bullet_ids, gt_correct=gt_correct)
        ordinal = trace_runtime.current_ordinal_for(task.domain)
        # Persist the citation counter update even if the downstream
        # reflector/curator call fails. A successful curator pass writes
        # the same snapshot index again with the final edits applied.
        trace_runtime.persist(task.domain)
        try:
            refl = trace_reflect(
                tstore,
                task.prompt,
                response_for_grading,
                cited_bullet_ids,
                gt_correct,
                cfg=trace_runtime.cfg,
            )
            trace_csv["reflector_proposal_count"] = len(refl.proposals)
            trace_csv["reflector_prompt_tokens"] = refl.prompt_tokens
            trace_csv["reflector_completion_tokens"] = refl.completion_tokens
            trace_csv["reflector_wall_seconds"] = refl.wall_seconds

            cur = trace_curate(
                tstore,
                task.prompt,
                response_for_grading,
                cited_bullet_ids,
                gt_correct,
                refl.proposals,
                cfg=trace_runtime.cfg,
            )
            stats = trace_apply_ops(
                store=tstore,
                ops=cur.ops,
                retrieved=retrieved_bullets,
                embed=trace_runtime.embed,
                cfg=trace_runtime.cfg,
                current_ordinal=ordinal,
            )
            trace_runtime.persist(task.domain)
            trace_runtime.snapshot_stores[task.domain].append_curator_log(
                {
                    "task_id": task.task_id,
                    "ordinal": ordinal,
                    "gt_correct": gt_correct,
                    "reflector_proposals": len(refl.proposals),
                    "create": stats.create_committed,
                    "create_blocked": stats.create_blocked,
                    "update": stats.update,
                    "delete": stats.delete,
                    "consolidate": stats.consolidate,
                    "no_op": stats.no_op,
                    "reflector_parse_error": refl.parse_error,
                    "curator_parse_error": cur.parse_error,
                    "reflector_prompt_tokens": refl.prompt_tokens,
                    "reflector_completion_tokens": refl.completion_tokens,
                    "reflector_wall_seconds": refl.wall_seconds,
                    "curator_prompt_tokens": cur.prompt_tokens,
                    "curator_completion_tokens": cur.completion_tokens,
                    "curator_wall_seconds": cur.wall_seconds,
                }
            )
            trace_csv["curator_create_count"] = stats.create_committed
            trace_csv["curator_create_blocked_count"] = stats.create_blocked
            trace_csv["curator_update_count"] = stats.update
            trace_csv["curator_delete_count"] = stats.delete
            trace_csv["curator_consolidate_count"] = stats.consolidate
            trace_csv["curator_no_op"] = stats.no_op
            trace_csv["curator_prompt_tokens"] = cur.prompt_tokens
            trace_csv["curator_completion_tokens"] = cur.completion_tokens
            trace_csv["curator_wall_seconds"] = cur.wall_seconds
        except Exception as exc:
            log.warning(
                "trace: reflector/curator failed for task=%s domain=%s (%s); leaving ledger unchanged",
                task.task_id,
                task.domain,
                exc,
            )
        active = tstore.active_bullets()
        trace_csv["trace_active_bullet_count_after"] = len(active)
        trace_csv["trace_total_bullet_count_after"] = len(tstore.bullets)
        trace_csv["trace_total_active_chars_after"] = sum(len(b.content) for b in active)
        row.update(trace_csv)

    return "completed", row


# -----------------------------------------------------------------------------
# Filter + order tasks
# -----------------------------------------------------------------------------


def _select_tasks(all_tasks: list[Task], opts: RunOptions) -> list[Task]:
    """Apply --task-ids / --domain / --start-index / --limit, in upstream order.

    Upstream applies domain → start_index/limit. We add `--task-ids` as the
    most-explicit override; when given it takes precedence over domain
    filtering and ordering.
    """
    if opts.task_ids:
        wanted = set(opts.task_ids)
        # Preserve dataset order, but only keep wanted ids
        return [t for t in all_tasks if t.task_id in wanted]

    pool = all_tasks
    if opts.domain:
        pool = [t for t in pool if t.domain == opts.domain]
    end = len(pool) if opts.limit is None else opts.start_index + opts.limit
    return pool[opts.start_index : end]


# -----------------------------------------------------------------------------
# Stats — direct port of upstream calculate_stats(), at run_with_hf.py:196-252
# -----------------------------------------------------------------------------


def calculate_stats(output_csv: Path, model_key: str) -> dict:
    """Per-domain + overall mean of per-task scores. NUMBER_OF_RUNS=1, so the
    per-task median across runs is just the single run's score."""
    if not output_csv.is_file():
        return {}
    with output_csv.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("status") == "completed"]
    if not rows:
        return {}

    domain_scores: dict[str, list[float]] = {}
    all_scores: list[float] = []
    score_col = f"{model_key}_1_score"
    for r in rows:
        try:
            s = float(r.get(score_col, 0) or 0)
        except (TypeError, ValueError):
            s = 0.0
        domain_scores.setdefault(r.get("domain", "Unknown"), []).append(s)
        all_scores.append(s)

    return {
        "total_completed": len(rows),
        "overall_mean": round(statistics.mean(all_scores), 2) if all_scores else 0.0,
        "by_domain": {
            d: {"n": len(scores), "mean": round(statistics.mean(scores), 2)}
            for d, scores in sorted(domain_scores.items())
        },
    }


# -----------------------------------------------------------------------------
# Driver
# -----------------------------------------------------------------------------


def run(opts: RunOptions) -> dict:
    """Synchronous entry point used by the CLI."""
    return asyncio.run(run_async(opts))


async def run_async(opts: RunOptions) -> dict:
    validate(opts.dataset_dir)

    # Ensure vendor's parser registry is initialised before any GenerationTask.
    # (Importing the parser package runs initialize_parsers(); we import it
    # here so a fresh `apex-bench run` doesn't depend on prior imports.)
    with vendor_cwd():
        import parser  # noqa: F401 — side-effect: registers ReductoParser

    response_template = _read_response_generation_template()
    grading_template_path = _grading_template_path()

    all_tasks = load_tasks(opts.dataset_dir)
    selected = _select_tasks(all_tasks, opts)
    if not selected:
        log.warning("no tasks matched filters; nothing to run")
        return {"total_completed": 0, "overall_mean": 0.0, "by_domain": {}}

    # Resume — skip tasks already completed in the same output CSV
    completed = load_completed_task_ids(opts.output_csv)
    pending = [t for t in selected if t.task_id not in completed]
    log.info(
        "selected=%d already_completed=%d pending=%d", len(selected), len(completed), len(pending)
    )

    if opts.dc_rs.enabled and opts.trace.enabled:
        raise ValueError(
            "--dc-rs and --trace are mutually exclusive; pick one memory subsystem."
        )
    model_key = sanitize_model_key(opts.profile.model_id)
    headers = csv_headers(
        model_key,
        with_dc_rs=opts.dc_rs.enabled,
        with_trace=opts.trace.enabled,
    )

    # --- DC-RS: build per-run runtime (when enabled) -------------------------
    dc_rs_runtime: Any | None = None
    if opts.dc_rs.enabled:
        import dataclasses

        from apex_bench.dc_rs.runtime import DCRSRuntime

        run_dir = opts.output_csv.parent

        # The synthesizer runs on the SAME model as the agent under test,
        # with the same thinking effort. Only the judge model is fixed
        # (gpt-5.5 medium). Fill the synthesizer model in from the active
        # TestModelProfile here unless the user has set it explicitly.
        cfg_dc_rs_in = opts.dc_rs
        if cfg_dc_rs_in.synthesizer_model is None:
            extra_args: dict[str, Any] = {}
            # Flatten model_configs into kwargs so LiteLLM accepts them.
            if opts.profile.model_configs:
                extra_args.update(opts.profile.model_configs)
            if opts.profile.enable_thinking is not None:
                extra_args["enable_thinking"] = opts.profile.enable_thinking
            if opts.profile.thinking_tokens is not None:
                extra_args["thinking_tokens"] = opts.profile.thinking_tokens
            # Prepend provider prefix when model_id is bare. Without this
            # LiteLLM raises "LLM Provider NOT provided" and the runner's
            # outer except silently aborts the synthesizer call.
            bare = opts.profile.model_id
            routed_bare = (
                bare if "/" in bare or not opts.profile.provider
                else f"{opts.profile.provider}/{bare}"
            )
            cfg_dc_rs_in = dataclasses.replace(
                cfg_dc_rs_in,
                synthesizer_model=routed_bare,
                synthesizer_extra_args=extra_args or None,
            )
        # Apply Azure routing AFTER profile fill-in so gpt-5.5 → azure.
        cfg_dc_rs_in = dataclasses.replace(
            cfg_dc_rs_in,
            synthesizer_model=route_model_id(cfg_dc_rs_in.synthesizer_model, cfg=opts.azure),
        )

        dc_rs_runtime = DCRSRuntime.create(
            cfg=cfg_dc_rs_in,
            run_dir=run_dir,
        )
        log.info(
            "dc-rs: enabled (embedding=%s top_k=%d bank_root=%s)",
            cfg_dc_rs_in.embedding_model,
            cfg_dc_rs_in.top_k,
            run_dir / "dc_rs",
        )

    # --- TRACE: build per-run runtime (when enabled) -------------------------
    trace_runtime: Any | None = None
    if opts.trace.enabled:
        import dataclasses

        from apex_bench.trace.runtime import TraceRuntime

        run_dir = opts.output_csv.parent
        trace_completed_per_domain: dict[str, int] = {}
        if opts.output_csv.is_file():
            try:
                with opts.output_csv.open("r", encoding="utf-8") as fh:
                    rdr = csv.DictReader(fh)
                    for r in rdr:
                        d = r.get("domain", "")
                        if r.get("status") == "completed" and d:
                            trace_completed_per_domain[d] = trace_completed_per_domain.get(d, 0) + 1
            except Exception:
                trace_completed_per_domain = {}

        cfg_trace_in = opts.trace
        if cfg_trace_in.reflector_model is None or cfg_trace_in.curator_model is None:
            extra_args: dict[str, Any] = {}
            # Flatten model_configs into kwargs so LiteLLM accepts them
            # (mirrors the Dynamic-Ledger setup just above).
            if opts.profile.model_configs:
                extra_args.update(opts.profile.model_configs)
            if opts.profile.enable_thinking is not None:
                extra_args["enable_thinking"] = opts.profile.enable_thinking
            if opts.profile.thinking_tokens is not None:
                extra_args["thinking_tokens"] = opts.profile.thinking_tokens
            # Prepend provider prefix when model_id is bare (e.g.
            # "grok-4.3" → "xai/grok-4.3"). Without this LiteLLM raises
            # "LLM Provider NOT provided" and the runner's outer except
            # silently aborts the reflector/curator call.
            bare = opts.profile.model_id
            routed_bare = (
                bare if "/" in bare or not opts.profile.provider
                else f"{opts.profile.provider}/{bare}"
            )
            cfg_trace_in = dataclasses.replace(
                cfg_trace_in,
                reflector_model=cfg_trace_in.reflector_model or routed_bare,
                curator_model=cfg_trace_in.curator_model or routed_bare,
                model_extra_args=extra_args or None,
            )
        cfg_trace_in = dataclasses.replace(
            cfg_trace_in,
            reflector_model=route_model_id(cfg_trace_in.reflector_model, cfg=opts.azure),
            curator_model=route_model_id(cfg_trace_in.curator_model, cfg=opts.azure),
        )

        trace_runtime = TraceRuntime.create(
            cfg=cfg_trace_in,
            run_dir=run_dir,
            completed_per_domain=trace_completed_per_domain,
        )
        log.info(
            "trace: enabled (embedding=%s top_k=%d snapshot_root=%s)",
            cfg_trace_in.embedding_model,
            cfg_trace_in.top_k_per_axis,
            run_dir / "trace",
        )

    write_manifest(
        opts.output_csv,
        build_run_manifest(opts, selected, pending, headers, status="starting"),
    )
    try:
        _preflight_credentials(opts, pending)
    except RuntimeError as exc:
        append_failure(
            opts.output_csv,
            {
                "scope": "run",
                "status": "failed_preflight",
                "profile": opts.profile.name,
                "model_id": opts.profile.model_id,
                "judge_model": opts.judge.model_id,
                "error": str(exc),
            },
        )
        write_manifest(
            opts.output_csv,
            build_run_manifest(opts, selected, pending, headers, status="failed_preflight"),
        )
        raise

    saved = 0
    skipped = 0
    for idx, task in enumerate(pending, start=1):
        log.info(
            "[%d/%d] task_id=%s domain=%s profile=%s",
            idx,
            len(pending),
            task.task_id,
            task.domain,
            opts.profile.name,
        )
        try:
            status, payload = await _process_task(
                task,
                opts.profile,
                opts.judge,
                response_template,
                grading_template_path,
                dc_rs_runtime=dc_rs_runtime,
                trace_runtime=trace_runtime,
                azure_cfg=opts.azure,
            )
        except KeyboardInterrupt:
            log.warning("interrupted; %d tasks completed before stop", saved)
            raise
        if status is None or not isinstance(payload, dict):
            log.error("task %s SKIPPED: %s", task.task_id, payload)
            append_failure(
                opts.output_csv,
                {
                    "scope": "task",
                    "status": "skipped",
                    "task_id": task.task_id,
                    "domain": task.domain,
                    "profile": opts.profile.name,
                    "model_id": opts.profile.model_id,
                    "judge_model": opts.judge.model_id,
                    "error": str(payload),
                },
            )
            skipped += 1
            continue
        append_row(opts.output_csv, headers, payload)
        saved += 1
        log.info(
            "[%d/%d] task_id=%s score=%.1f%%",
            idx,
            len(pending),
            task.task_id,
            payload[f"{model_key}_1_score"],
        )

    stats = calculate_stats(opts.output_csv, model_key)
    log.info(
        "run complete: saved=%d skipped=%d overall_mean=%.2f%%",
        saved,
        skipped,
        stats.get("overall_mean", 0.0),
    )
    write_manifest(
        opts.output_csv,
        build_run_manifest(
            opts,
            selected,
            pending,
            headers,
            status="complete",
            saved=saved,
            skipped=skipped,
            stats=stats,
        ),
    )
    return stats
