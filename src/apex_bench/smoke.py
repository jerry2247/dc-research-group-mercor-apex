"""Single-task smoke runner.

A minimal end-to-end run: pick one task, generate with one test model, grade
with the configured judge. The point is twofold:

  1. Fail loudly if any seam in the pipeline is broken, before we spend real
     budget on a multi-task run.
  2. Produce a presentable single-task artifact (the full prompt, attachments,
     model response, per-criterion judge rationales, and aggregate score)
     persisted as JSON next to the timestamped run directory.

Imports from the vendored harness lazily so `apex-bench --help` works even
when the vendor has not yet been installed.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apex_bench.config import Settings
from apex_bench.dataset import Task, load_tasks
from apex_bench.test_models import TestModelProfile
from apex_bench.vendor_imports import vendor_cwd

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmokeResult:
    """End-to-end smoke result. Persisted as JSON next to the run directory."""

    task_id: str
    domain: str
    profile_name: str
    model_id: str
    judge_model: str
    percentage_score: float
    points_earned: float
    points_possible: int

    # Token telemetry matching the runner CSV columns:
    agent_tokens: int = 0

    # Full content fields -- the bits that make this artifact present-able:
    prompt: str = ""
    attachments: tuple[str, ...] = ()
    response: str = ""
    score_summary: dict[str, Any] = field(default_factory=dict)
    wall_time_seconds: float = 0.0

    # Where the JSON artifact lives on disk.
    result_path: str = ""

    @property
    def generated_chars(self) -> int:
        return len(self.response)


# -----------------------------------------------------------------------------


def pick_smoke_task(
    tasks: list[Task],
    *,
    domain: str | None = None,
    require_no_attachments: bool = False,
) -> Task:
    """Pick a single task to smoke against.

    Defaults to the first task in the (filtered) dataset. The
    ``require_no_attachments`` flag exists for forward compatibility but
    defaults to False because the APEX-v1-extended public split has ZERO
    no-attachment tasks (verified live: every one of the 100 tasks ships
    1-9 attachments). Setting it to True would make the smoke fail with
    'no tasks match smoke criteria'.
    """
    pool = tasks
    if domain is not None:
        pool = [t for t in pool if t.domain == domain]
    if require_no_attachments:
        pool = [t for t in pool if not t.has_attachments]
    if not pool:
        raise RuntimeError(
            f"No tasks match smoke criteria "
            f"(domain={domain!r}, require_no_attachments={require_no_attachments}). "
            "Run `apex-bench catalog` first to see what's available."
        )
    return pool[0]


# -----------------------------------------------------------------------------


def run_smoke(
    settings: Settings,
    *,
    test_model_profile: TestModelProfile,
    domain: str | None = None,
    require_no_attachments: bool = False,
    output_dir: Path | None = None,
) -> SmokeResult:
    """Synchronous wrapper around the async smoke loop.

    Persists a JSON artifact under
    ``runs/smoke/<UTC-timestamp>__<profile>__<task_id>/result.json``
    (override with ``output_dir``). The JSON contains the full prompt,
    attachment filenames, model response, per-criterion judge rationales,
    and aggregate score -- everything you'd want to inspect or present
    after the smoke completes.
    """
    tasks = load_tasks(settings.dataset_dir)
    task = pick_smoke_task(tasks, domain=domain, require_no_attachments=require_no_attachments)
    log.info(
        "smoke task selected: task_id=%s domain=%s prompt_chars=%d attachments=%d",
        task.task_id,
        task.domain,
        task.prompt_chars,
        len(task.attachments),
    )
    log.info(
        "smoke test model: profile=%s model_id=%s",
        test_model_profile.name,
        test_model_profile.model_id,
    )

    if output_dir is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        output_dir = (
            settings.runs_dir / "smoke" / f"{stamp}__{test_model_profile.name}__{task.task_id}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    result = asyncio.run(
        _run_smoke_async(
            settings,
            task=task,
            test_model_profile=test_model_profile,
        )
    )

    # Persist the artifact.
    artifact_path = output_dir / "result.json"
    payload = {
        "task_id": result.task_id,
        "domain": result.domain,
        "profile": result.profile_name,
        "test_model_id": result.model_id,
        "judge_model": result.judge_model,
        "percentage_score": round(result.percentage_score, 2),
        "points_earned": result.points_earned,
        "points_possible": result.points_possible,
        "agent_tokens": result.agent_tokens,
        "wall_time_seconds": round(result.wall_time_seconds, 2),
        "generated_chars": result.generated_chars,
        "prompt": result.prompt,
        "attachments": list(result.attachments),
        "response": result.response,
        "score_summary": result.score_summary,
    }
    artifact_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log.info("smoke result written to %s", artifact_path)

    # Return a copy of result with the path populated.
    from dataclasses import replace

    return replace(result, result_path=str(artifact_path))


async def _run_smoke_async(
    settings: Settings,
    *,
    task: Task,
    test_model_profile: TestModelProfile,
) -> SmokeResult:
    import time

    # Imported lazily so module import does not require the vendor install.
    with vendor_cwd():
        from generation import (
            Attachment as VendorAttachment,
        )
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

    started = time.time()

    # --- Build the generation prompt ----------------------------------------
    prompt_template = _read_prompt_template(settings)
    prompt = prompt_template.replace("{{Domain}}", task.domain).replace("{{Prompt}}", task.prompt)

    attachments = [
        VendorAttachment(filename=a.path.name, url=f"file://{a.path}")
        for a in task.attachments
        if a.exists
    ]
    attachment_filenames = tuple(a.path.name for a in task.attachments if a.exists)

    model_kwargs = test_model_profile.to_model_config_kwargs()
    gen_task = GenerationTask(
        prompt=prompt,
        models=[ModelConfig(**model_kwargs)],
        attachments=attachments or None,
    )
    log.info("smoke: starting generation (model=%s)", test_model_profile.model_id)
    gen_result = await run_generation_task_async(gen_task)
    if not gen_result.results or not gen_result.results[0].get("success"):
        err = (
            gen_result.results[0].get("error_message", "unknown error")
            if gen_result.results
            else "no results returned"
        )
        raise RuntimeError(f"smoke generation failed: {err}")
    response = gen_result.results[0].get("response", "")
    log.info("smoke: generation complete (chars=%d)", len(response))

    # --- Grade --------------------------------------------------------------
    from apex_bench.runner import _safe_judge_temperature

    judge_cfg = GradingModelConfig(
        model_id=settings.judge.model_id,
        max_tokens=settings.judge.max_tokens,
        temperature=_safe_judge_temperature(settings.judge.model_id, settings.judge.temperature),
    )
    # Pass the ABSOLUTE PATH (not the file content) -- see
    # _grading_template_path() docstring for the macOS ENAMETOOLONG vendor
    # bug it works around.
    grading_template_path = _grading_template_path()
    grading_task = GradingTask(
        solution=response,
        rubric=task.rubric_json,
        grading_model=judge_cfg,
        grading_prompt_template=grading_template_path,
    )
    log.info("smoke: starting grading (judge=%s)", settings.judge.model_id)
    grade_result = await run_grading_task_async(grading_task)
    if grade_result.grading_error:
        raise RuntimeError(f"smoke grading failed: {grade_result.grading_error}")

    # Build per-criterion score_summary: rubric_json with each criterion's
    # autorating + judge reason merged in. Same shape as runner.py.
    rubric_dict: dict[str, Any] = {}
    try:
        rubric_parsed = json.loads(task.rubric_json)
        if isinstance(rubric_parsed, list):
            for entry in rubric_parsed:
                if isinstance(entry, dict):
                    rubric_dict.update(entry)
        elif isinstance(rubric_parsed, dict):
            rubric_dict.update(rubric_parsed)
    except json.JSONDecodeError:
        pass
    for cr in grade_result.criteria_results:
        key = cr.get("criterion_key")
        if isinstance(key, str) and key in rubric_dict and isinstance(rubric_dict[key], dict):
            rubric_dict[key]["autorating"] = bool(cr.get("autorating"))
            rubric_dict[key]["reason"] = cr.get("reason", "")

    elapsed = time.time() - started

    agent_tokens = int(getattr(gen_result, "total_tokens", 0) or 0)
    return SmokeResult(
        task_id=task.task_id,
        domain=task.domain,
        profile_name=test_model_profile.name,
        model_id=test_model_profile.model_id,
        judge_model=settings.judge.model_id,
        percentage_score=grade_result.percentage_score,
        points_earned=grade_result.points_earned,
        points_possible=grade_result.points_possible,
        agent_tokens=agent_tokens,
        prompt=prompt,
        attachments=attachment_filenames,
        response=response,
        score_summary=rubric_dict,
        wall_time_seconds=elapsed,
    )


# -----------------------------------------------------------------------------


def _read_prompt_template(settings: Settings) -> str:
    """Read the upstream response-generation prompt template, verbatim."""
    from apex_bench.paths import vendor_dir

    p = vendor_dir() / "prompt" / "response_generation_prompt.txt"
    if not p.is_file():
        raise RuntimeError(
            f"missing vendor prompt template at {p}. "
            "Did `make install` (or `pip install -e ./vendor/apex_evals`) succeed?"
        )
    return p.read_text(encoding="utf-8")


def _grading_template_path() -> str:
    """Return the ABSOLUTE PATH to the vendor grading template, as a string.

    The vendor's GradingTask.grading_prompt_template field is documented as
    Optional[str], with _resolve_prompt_template() doing:
        candidate = Path(template); if candidate.exists(): return candidate.read_text(); else return template

    That branch is unguarded against macOS ENAMETOOLONG: passing the template
    *content* (>255 chars) triggers OSError on Path.exists() instead of the
    intended False-fallthrough. So we pass the path and let the vendor read
    the file itself. Confirmed against a real run on 2026-05-19.
    """
    from apex_bench.paths import vendor_dir

    p = vendor_dir() / "prompt" / "grading_prompt.txt"
    if not p.is_file():
        raise RuntimeError(
            f"missing vendor grading template at {p}. "
            "Did `make install` (or `pip install -e ./vendor/apex_evals`) succeed?"
        )
    return str(p)


# -----------------------------------------------------------------------------


def render_result(result: SmokeResult) -> str:
    """Compact stdout view; the full content lives in the result.json file."""
    return json.dumps(
        {
            "task_id": result.task_id,
            "domain": result.domain,
            "profile": result.profile_name,
            "test_model_id": result.model_id,
            "judge_model": result.judge_model,
            "percentage_score": round(result.percentage_score, 2),
            "criteria_passed": int(result.points_earned),
            "criteria_total": int(result.points_possible),
            "generated_chars": result.generated_chars,
            "agent_tokens": result.agent_tokens,
            "wall_time_seconds": round(result.wall_time_seconds, 1),
            "result_path": result.result_path,
        },
        indent=2,
    )
