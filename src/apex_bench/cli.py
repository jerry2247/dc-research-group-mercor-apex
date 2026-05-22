"""apex-bench CLI.

Commands:
  apex-bench info       — environment + repo layout sanity check
  apex-bench models     — list available test-model profiles
  apex-bench catalog    — characterize the dataset, write JSON
  apex-bench list       — browse tasks by domain
  apex-bench show       — print one task in full
  apex-bench smoke      — single-task end-to-end smoke run
  apex-bench run        — multi-task baseline run (production entry point)
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from apex_bench import __version__
from apex_bench.config import (
    DEFAULT_JUDGE_MAX_TOKENS,
    DEFAULT_JUDGE_MODEL,
    DEFAULT_JUDGE_TEMPERATURE,
    RUNS_PER_TASK,
    VALID_DOMAINS,
    JudgeConfig,
    Settings,
)
from apex_bench.paths import default_dataset_dir, repo_root, runs_dir, vendor_dir
from apex_bench.vendor_imports import vendor_cwd

app = typer.Typer(
    name="apex-bench",
    help="Reproducible runner around the Mercor APEX-v1-extended harness.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        datefmt="%H:%M:%S",
    )


# -----------------------------------------------------------------------------


@app.callback()
def _main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable DEBUG logs."),
) -> None:
    _setup_logging(verbose)


@app.command()
def version() -> None:
    """Print the apex-bench package version."""
    console.print(__version__)


# -----------------------------------------------------------------------------


@app.command()
def info() -> None:
    """Show repo layout and resolved paths. Useful as a first sanity check."""
    table = Table(show_header=False, box=None)
    table.add_row("[bold]apex-bench version[/bold]", __version__)
    table.add_row("[bold]repo root[/bold]", str(repo_root()))
    table.add_row("[bold]vendor[/bold]", str(vendor_dir()))
    table.add_row("[bold]dataset dir (default)[/bold]", str(default_dataset_dir()))
    table.add_row("[bold]runs dir[/bold]", str(runs_dir()))
    table.add_row("[bold]default judge[/bold]", DEFAULT_JUDGE_MODEL)
    table.add_row("[bold]runs per task (policy)[/bold]", str(RUNS_PER_TASK))
    console.print(table)

    # Light environment probe.
    try:
        with vendor_cwd():
            from generation import GenerationTask  # noqa: F401
            from grading import GradingTask  # noqa: F401

        console.print("[green]✓[/green] vendored harness imports OK")
    except ImportError as e:
        console.print(
            f"[yellow]![/yellow] vendored harness not importable: {e}. "
            "Run [bold]make install[/bold]."
        )


# -----------------------------------------------------------------------------


@app.command()
def catalog(
    input_dir: Path = typer.Option(
        default_dataset_dir(),
        "--input-dir",
        "-i",
        help="Path to a clone of mercor/APEX-v1-extended.",
        exists=False,  # we validate inside so the error message is clear
        resolve_path=True,
    ),
    output: Path = typer.Option(
        Path("data") / "catalog.json",
        "--output",
        "-o",
        help="Where to write the catalog JSON. Parent dirs are created.",
        resolve_path=True,
    ),
    no_timestamp: bool = typer.Option(
        False,
        "--no-timestamp",
        help="Omit `generated_at` for strict bytes-stable output.",
    ),
) -> None:
    """Characterize the dataset; produce a deterministic JSON snapshot."""
    from apex_bench.catalog import build_report, write_report
    from apex_bench.dataset import DatasetError

    try:
        report = build_report(input_dir, include_timestamp=not no_timestamp)
    except DatasetError as e:
        console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=2) from e

    write_report(report, output)

    table = Table(title="APEX-v1-extended catalog", show_header=False, box=None)
    table.add_row("[bold]dataset dir[/bold]", report.dataset_dir)
    table.add_row("[bold]total tasks[/bold]", str(report.total_tasks))
    table.add_row(
        "[bold]domains[/bold]",
        ", ".join(f"{k}={v}" for k, v in report.domains.items()),
    )
    table.add_row(
        "[bold]prompt chars (min/med/max)[/bold]",
        f"{report.prompt_chars.min} / {report.prompt_chars.median} / {report.prompt_chars.max}",
    )
    table.add_row(
        "[bold]rubric chars (min/med/max)[/bold]",
        f"{report.rubric_chars.min} / {report.rubric_chars.median} / {report.rubric_chars.max}",
    )
    table.add_row(
        "[bold]rubric criteria (min/med/max)[/bold]",
        f"{report.rubric_criteria.min} / {report.rubric_criteria.median} / {report.rubric_criteria.max}",
    )
    table.add_row("[bold]tasks with attachments[/bold]", str(report.tasks_with_attachments))
    table.add_row(
        "[bold]tasks w/ missing attachments[/bold]",
        str(report.tasks_with_missing_attachments),
    )
    table.add_row("[bold]wrote[/bold]", str(output))
    console.print(table)


# -----------------------------------------------------------------------------


@app.command()
def models() -> None:
    """List the available test-model profiles. The judge is fixed by policy."""
    from apex_bench.test_models import profiles_by_family

    console.print(
        f"[bold]Judge (fixed):[/bold] {DEFAULT_JUDGE_MODEL}  "
        "(OpenAI default reasoning_effort=medium)"
    )
    console.print()
    table = Table(title="Test-model profiles", show_lines=False)
    table.add_column("profile name", style="bold", no_wrap=True)
    table.add_column("provider", no_wrap=True)
    table.add_column("model id", no_wrap=True)
    table.add_column("max_tokens", justify="right")
    table.add_column("notes", overflow="fold")
    for _family, ps in profiles_by_family().items():
        for p in ps:
            table.add_row(
                p.name,
                p.provider,
                p.model_id,
                str(p.max_tokens),
                p.notes,
            )
        # Visual separator between families
        table.add_section()
    console.print(table)


# -----------------------------------------------------------------------------


@app.command(name="list")
def list_tasks(
    input_dir: Path = typer.Option(
        default_dataset_dir(),
        "--input-dir",
        "-i",
        help="Path to a clone of mercor/APEX-v1-extended.",
        resolve_path=True,
    ),
    domain: list[str] | None = typer.Option(
        None,
        "--domain",
        "-d",
        help=f"Filter to one or more domains (repeatable). One of: {', '.join(VALID_DOMAINS)}.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Show only the first N tasks after filtering.",
    ),
    full_prompt: bool = typer.Option(
        False,
        "--full-prompt",
        help="Print the entire prompt of each shown task instead of the first-sentence summary.",
    ),
) -> None:
    """Browse the 100 public APEX tasks. Read-only; no API calls."""
    from apex_bench.dataset import DatasetError
    from apex_bench.task_index import build_index

    if domain:
        invalid = [d for d in domain if d not in VALID_DOMAINS]
        if invalid:
            console.print(
                f"[red]error:[/red] --domain values must be in {VALID_DOMAINS}; got {invalid!r}"
            )
            raise typer.Exit(code=2)

    try:
        summaries = build_index(input_dir)
    except DatasetError as e:
        console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=2) from e

    if domain:
        summaries = [s for s in summaries if s.domain in set(domain)]
    if limit is not None:
        summaries = summaries[:limit]

    if not summaries:
        console.print("[yellow]no tasks match the filter[/yellow]")
        return

    if full_prompt:
        # One block per task — readable, copy-pasteable.
        from apex_bench.dataset import load_tasks

        tasks_by_id = {t.task_id: t for t in load_tasks(input_dir)}
        for s in summaries:
            console.print()
            console.rule(f"[bold]{s.domain} · Task {s.task_id}[/bold]")
            console.print(
                f"prompt_chars={s.prompt_chars}  rubric_chars={s.rubric_chars}  "
                f"attachments={s.n_attachments} ({', '.join(s.attachment_exts) or '-'})"
            )
            console.print()
            console.print(tasks_by_id[s.task_id].prompt)
        return

    # Default: one row per task in a Rich table.
    table = Table(
        title=f"APEX-v1-extended tasks ({len(summaries)} shown)",
        show_lines=False,
    )
    table.add_column("task_id", style="bold", no_wrap=True, justify="right")
    table.add_column("domain", no_wrap=True)
    table.add_column("attach")
    table.add_column("prompt_chars", justify="right")
    table.add_column("rubric_chars", justify="right")
    table.add_column("first sentence", overflow="fold")

    for s in summaries:
        exts = ",".join(s.attachment_exts) if s.attachment_exts else "-"
        table.add_row(
            s.task_id,
            s.domain,
            f"{s.n_attachments} ({exts})",
            str(s.prompt_chars),
            str(s.rubric_chars),
            s.first_sentence,
        )
    console.print(table)


# -----------------------------------------------------------------------------


@app.command()
def show(
    task_id: str = typer.Argument(..., help="Task ID to print in full."),
    input_dir: Path = typer.Option(
        default_dataset_dir(),
        "--input-dir",
        "-i",
        resolve_path=True,
    ),
) -> None:
    """Print one task in full: prompt, rubric criteria, attachment list."""
    import json

    from apex_bench.dataset import load_tasks

    tasks = {t.task_id: t for t in load_tasks(input_dir)}
    if task_id not in tasks:
        console.print(
            f"[red]error:[/red] task_id {task_id!r} not found. "
            "Run `apex-bench list` to see valid ids."
        )
        raise typer.Exit(code=2)
    t = tasks[task_id]

    console.rule(f"[bold]{t.domain} · Task {t.task_id}[/bold]")
    console.print(f"prompt_chars={t.prompt_chars}  rubric_chars={t.rubric_chars}")
    console.print()
    console.print("[bold]PROMPT[/bold]")
    console.print(t.prompt)
    console.print()
    console.print("[bold]ATTACHMENTS[/bold]")
    if not t.attachments:
        console.print("  (none)")
    else:
        for a in t.attachments:
            size = a.path.stat().st_size if a.path.is_file() else 0
            present = "✓" if a.exists else "✗"
            console.print(f"  {present}  {a.rel_path}   ({size / 1024:.1f} KB)")
    console.print()
    console.print("[bold]RUBRIC CRITERIA[/bold]")
    try:
        rubric = json.loads(t.rubric_json)
    except json.JSONDecodeError:
        console.print("  (rubric JSON did not parse)")
        return
    if isinstance(rubric, list):
        crits = [(k, v) for d in rubric if isinstance(d, dict) for k, v in d.items()]
    elif isinstance(rubric, dict):
        crits = list(rubric.items())
    else:
        crits = []
    for k, v in crits:
        if not isinstance(v, dict):
            continue
        desc = v.get("description", "")
        weight = v.get("weight", "")
        ctype = v.get("criterion_type", "")
        console.print(f"  [bold]{k}[/bold]  weight={weight!r}  type={ctype!r}")
        console.print(f"     {desc}")


# -----------------------------------------------------------------------------


@app.command()
def smoke(
    model: str = typer.Option(
        ...,
        "--model",
        "-m",
        help="Test-model profile name. Run `apex-bench models` for the list.",
    ),
    judge_model: str = typer.Option(
        DEFAULT_JUDGE_MODEL,
        "--judge-model",
        help="Judge model id. Overrides the project default (gpt-5.5 medium-by-default).",
    ),
    judge_temperature: float = typer.Option(DEFAULT_JUDGE_TEMPERATURE, "--judge-temperature"),
    judge_max_tokens: int = typer.Option(DEFAULT_JUDGE_MAX_TOKENS, "--judge-max-tokens", min=1024),
    input_dir: Path = typer.Option(
        default_dataset_dir(),
        "--input-dir",
        "-i",
        help="Path to the dataset clone.",
        resolve_path=True,
    ),
    domain: str | None = typer.Option(
        None,
        "--domain",
        help=f"Restrict to one domain. One of: {', '.join(VALID_DOMAINS)}.",
    ),
    require_no_attachments: bool = typer.Option(
        False,
        "--require-no-attachments",
        help="If set, only smoke against a task with NO attachments. The "
        "APEX-v1-extended public split has zero such tasks; this flag exists "
        "only for forward compatibility. Default: False (pick the first task; "
        "Reducto handles attachments).",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Per-task output dir. Defaults to runs/smoke/<UTC-timestamp>__<profile>__<task_id>/.",
        resolve_path=True,
    ),
) -> None:
    """Run ONE task end-to-end. Verifies generation + grading + scoring.

    Writes the full prompt, attachment filenames, model response,
    per-criterion judge rationales, and aggregate score to
    ``<output_dir>/result.json``.
    """
    from apex_bench.smoke import render_result, run_smoke
    from apex_bench.test_models import get_profile

    if domain is not None and domain not in VALID_DOMAINS:
        console.print(f"[red]error:[/red] --domain must be one of {VALID_DOMAINS}, got {domain!r}")
        raise typer.Exit(code=2)

    try:
        profile = get_profile(model)
    except KeyError as e:
        console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=2) from e

    settings = (
        Settings.defaults()
        .with_dataset_dir(input_dir)
        .with_judge(
            JudgeConfig(
                model_id=judge_model,
                temperature=judge_temperature,
                max_tokens=judge_max_tokens,
            )
        )
    )

    try:
        result = run_smoke(
            settings,
            test_model_profile=profile,
            domain=domain,
            require_no_attachments=require_no_attachments,
            output_dir=output_dir,
        )
    except Exception as e:
        console.print(f"[red]smoke failed:[/red] {e}")
        raise typer.Exit(code=1) from e

    console.print("[green]smoke OK[/green]")
    console.print(render_result(result))
    sys.exit(0)


# -----------------------------------------------------------------------------


@app.command()
def run(
    model: str = typer.Option(
        ...,
        "--model",
        "-m",
        help="Test-model profile name. Run `apex-bench models` for the list.",
    ),
    domain: str | None = typer.Option(
        None,
        "--domain",
        "-d",
        help=f"Restrict to one domain. One of: {', '.join(VALID_DOMAINS)}.",
    ),
    task_ids: str | None = typer.Option(
        None,
        "--task-ids",
        help="Comma-separated task ids (overrides --domain / --start-index / --limit).",
    ),
    start_index: int = typer.Option(
        0, "--start-index", help="Skip the first N tasks after domain filter.", min=0
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Run at most N tasks (after start-index). E.g. 25 = whole domain.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output CSV path. Defaults to runs/<timestamp>__<profile>__<domain>/results.csv.",
        resolve_path=True,
    ),
    input_dir: Path = typer.Option(
        default_dataset_dir(),
        "--input-dir",
        "-i",
        help="Path to the dataset clone.",
        resolve_path=True,
    ),
    judge_model: str = typer.Option(
        DEFAULT_JUDGE_MODEL,
        "--judge-model",
        help="Override the project-default judge (gpt-5.5 medium-by-default).",
    ),
    judge_temperature: float = typer.Option(DEFAULT_JUDGE_TEMPERATURE, "--judge-temperature"),
    judge_max_tokens: int = typer.Option(DEFAULT_JUDGE_MAX_TOKENS, "--judge-max-tokens", min=1024),
    dynamic_ledger: bool = typer.Option(
        False,
        "--dynamic-ledger/--no-dynamic-ledger",
        help="Enable the Dynamic Ledger (no-ground-truth) subsystem. Default: "
        "off. When on, each task is preceded by a dual-embedding retrieval "
        "into the per-domain ledger; after grading, the curator examines the "
        "work and emits <memory_updates> JSON ops that the wrapper applies to "
        "the ledger. The curator runs on the same model as the selected "
        "agent profile (only the judge is fixed at gpt-5.5). See "
        "docs/DYNAMIC_LEDGER_PRD.md.",
    ),
    dynamic_ledger_top_k: int = typer.Option(
        5,
        "--dynamic-ledger-top-k",
        min=0,
        help="Top-k per retrieval axis when the Dynamic Ledger is on.",
    ),
    trace: bool = typer.Option(
        False,
        "--trace/--no-trace",
        help="Enable the TRACE (uses-ground-truth) subsystem. Default: off. "
        "Mutually exclusive with --dynamic-ledger. When on, each task is "
        "preceded by a dual-embedding retrieval into the per-domain "
        "cheatsheet; the agent emits a <citations>[...] tag stripped "
        "before grading; after grading the boolean criteria_passed==total "
        "is threaded into a reflector + curator pair (both same model as "
        "the agent) that emit <cheatsheet_updates> ops applied to the "
        "ledger. See docs/TRACE_PRD.md.",
    ),
    trace_top_k: int = typer.Option(
        8,
        "--trace-top-k",
        min=0,
        help="Top-k per retrieval axis when TRACE is on.",
    ),
    azure: bool = typer.Option(
        False,
        "--azure/--no-azure",
        help="Route GPT-5.5 chat completions (judge + test profile + DL "
        "curator + TRACE reflector/curator) through Azure-OpenAI. "
        "Requires AZURE_API_KEY (or AZURE_OPENAI_API_KEY), AZURE_API_BASE "
        "(or AZURE_OPENAI_ENDPOINT), and AZURE_API_VERSION; the Azure "
        "deployment name is AZURE_GPT55_DEPLOYMENT_NAME (default `gpt-5.5`). "
        "The embedding model (text-embedding-3-large) is always served by "
        "OpenAI regardless of this flag.",
    ),
) -> None:
    """Run the APEX baseline on a slice of tasks. ONE run per (task, model).

    Examples:
      # Finance, all 25 tasks, Grok 4.3 high reasoning
      apex-bench run --domain Finance --limit 25 --model grok-4.3-high

      # 5 Consulting tasks, GPT-5.5 medium
      apex-bench run --domain Consulting --limit 5 --model gpt-5.5-medium

      # Specific task ids only
      apex-bench run --task-ids 145,283,352 --model grok-4.3-low
    """
    from datetime import datetime

    from apex_bench.azure_routing import AzureConfig
    from apex_bench.dynamic_ledger.config import DynamicLedgerConfig
    from apex_bench.runner import JudgeOverride, RunOptions
    from apex_bench.trace.config import TraceConfig

    if dynamic_ledger and trace:
        console.print(
            "[red]error:[/red] --dynamic-ledger and --trace are mutually exclusive; pick one."
        )
        raise typer.Exit(code=2)
    from apex_bench.runner import run as run_runner
    from apex_bench.test_models import get_profile

    if domain is not None and domain not in VALID_DOMAINS:
        console.print(f"[red]error:[/red] --domain must be one of {VALID_DOMAINS}, got {domain!r}")
        raise typer.Exit(code=2)
    try:
        profile = get_profile(model)
    except KeyError as e:
        console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=2) from e

    ids_tuple: tuple[str, ...] | None = None
    if task_ids:
        ids_tuple = tuple(s.strip() for s in task_ids.split(",") if s.strip())
        if not ids_tuple:
            console.print("[red]error:[/red] --task-ids was empty after parsing.")
            raise typer.Exit(code=2)

    if output is None:
        from apex_bench.paths import runs_dir

        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        slug = profile.name + "__" + (domain or ("ids" if ids_tuple else "all"))
        output = runs_dir() / f"{stamp}__{slug}" / "results.csv"

    opts = RunOptions(
        profile=profile,
        judge=JudgeOverride(
            model_id=judge_model,
            temperature=judge_temperature,
            max_tokens=judge_max_tokens,
        ),
        dataset_dir=input_dir,
        output_csv=output,
        domain=domain,
        task_ids=ids_tuple,
        start_index=start_index,
        limit=limit,
        dynamic_ledger=DynamicLedgerConfig(
            enabled=dynamic_ledger,
            top_k_per_axis=dynamic_ledger_top_k,
        ),
        trace=TraceConfig(
            enabled=trace,
            top_k_per_axis=trace_top_k,
        ),
        azure=AzureConfig(enabled=azure),
    )

    console.print(
        f"[bold]Starting run[/bold]  profile={profile.name}  domain={domain or '(all)'}  "
        f"limit={limit if limit is not None else 'no-cap'}  "
        f"judge={judge_model}\n  -> output: {output}"
    )
    try:
        stats = run_runner(opts)
    except KeyboardInterrupt:
        console.print(
            "[yellow]interrupted[/yellow] — partial results saved in CSV; "
            "re-run with the same --output to resume."
        )
        raise typer.Exit(code=130) from None
    except Exception as e:
        console.print(f"[red]run failed:[/red] {e}")
        raise typer.Exit(code=1) from e

    table = Table(title="APEX run summary", show_header=False)
    table.add_row("[bold]profile[/bold]", profile.name)
    table.add_row("[bold]judge[/bold]", judge_model)
    table.add_row("[bold]tasks completed[/bold]", str(stats.get("total_completed", 0)))
    table.add_row("[bold]overall mean %[/bold]", f"{stats.get('overall_mean', 0.0):.2f}")
    for dom, info in (stats.get("by_domain") or {}).items():
        table.add_row(f"  [bold]{dom}[/bold] (n={info['n']})", f"{info['mean']:.2f}")
    table.add_row("[bold]CSV[/bold]", str(output))
    console.print(table)
