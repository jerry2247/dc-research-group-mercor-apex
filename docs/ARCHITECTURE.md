# Architecture

> **Read this if you're asking:** "Why is the code split between
> `src/apex_bench/` and `vendor/apex_evals/`? How do I resync upstream?"
> "Can I edit the vendor?"
>
> **TL;DR:** vendor is pristine Mercor source; our wrapper imports from
> it. Edits to vendor are forbidden by default; documented patches only.

## Two layers

```
┌─────────────────────────────────────────────────┐
│  src/apex_bench/   --- our code (wrapper)       │
│    cli.py        Typer CLI                      │
│    config.py     Settings, JudgeConfig          │
│    paths.py      repo-root resolution           │
│    dataset.py    typed APEX dataset loader      │
│    catalog.py    dataset characterization       │
│    smoke.py      single-task smoke runner       │
└────────────────────────┬────────────────────────┘
                         │ imports
                         ▼
┌─────────────────────────────────────────────────┐
│  vendor/apex_evals/  --- pinned upstream code   │
│    src/generation/    GenerationTask, ...       │
│    src/grading/       GradingTask, ...          │
│    src/call_llm/      LiteLLM-backed client     │
│    src/parser/        Reducto + interfaces      │
│    src/handler/       validation                │
│    src/errors/        typed exceptions          │
│    prompt/            response_generation.txt   │
│    examples/          reference runner          │
└─────────────────────────────────────────────────┘
```

The wrapper is the only thing that gets called from outside. The vendor is a
**library** for the wrapper — never invoked directly from production paths.

## Why vendor at all

Three options were considered:

1. **`pip install` from upstream URL.** Smallest disk footprint. Cannot pin a
   commit reliably across `pip` versions; upstream can change under us without
   warning. Rejected.
2. **Git submodule pinned to a commit.** Pinning is reliable. `git clone
   --recurse-submodules` reproduces the tree exactly. Submodules add a fetch
   step and a layer of indirection that complicates `pip install -e .`.
   Considered.
3. **Fork & vendor (current).** Source lives in our tree; we can read, diff,
   and (if needed) patch the harness in PRs. Reviewers see exactly what we
   ship.

We picked **3** because:
- This is a research project and the harness will probably need surgical
  modifications (different judge default, custom output formats, etc.).
- Vendoring keeps those modifications reviewable instead of hidden in a
  fork's commit history.
- Resyncing upstream is a `rsync` + `git diff` exercise documented in
  `vendor/apex_evals/UPSTREAM.md`, not a long-running merge.

## Wrapper-vs-vendor diff policy

The hard rule: **do not edit files under `vendor/apex_evals/`**. The vendored
copy stays bit-identical to the upstream commit recorded in `UPSTREAM.md`.

If a customization is needed:

| Need | Where it goes |
|---|---|
| Different default judge | `src/apex_bench/config.py:DEFAULT_JUDGE_MODEL` |
| Different output schema | New module in `src/apex_bench/` |
| Different runner loop | New module in `src/apex_bench/`, importing from `generation` and `grading` |
| Different prompt template | Read the vendor template, then transform — never edit in place |
| A bug fix the upstream hasn't released | Patch in `src/apex_bench/`, document workaround |
| A bug fix that genuinely needs to be in vendor | Apply, add `# vendored-patch: <reason>` comment, record in `vendor/apex_evals/PATCHES.md`, plan to upstream |

This rule is what makes the resync workflow tractable. The moment we edit
vendor files without recording the patch, we have a soft fork.

## Settings flow

```
defaults in config.py
        │
        ▼
CLI flags (apex-bench smoke --judge-model ...)
        │
        ▼
Settings dataclass (frozen)
        │
        ▼
smoke.run_smoke(settings, ...)
        │
        ▼
vendor GenerationTask / GradingTask  ← typed, validated by Pydantic upstream
```

`Settings` is frozen so a single run cannot have its config mutated mid-flight.
Every CLI subcommand assembles a `Settings` and hands it off; library code
never reads env vars or paths directly.

## Why `dataset.py` is a separate module from `smoke.py`

`dataset.py` does no I/O against the model providers. It only reads the CSV
and resolves attachment paths. Keeping it free of LiteLLM / OpenAI / Anthropic
deps means:

1. We can run `apex-bench catalog` without any LLM credentials.
2. Unit tests on dataset shape do not need network or API keys.
3. Future DC2 integration can import `apex_bench.dataset` from outside this
   repo's venv and reuse the typed loader without dragging the harness with
   it.

## Future surface (not implemented yet)

- `apex-bench run` — the full N-task × M-model × R-runs loop. The shape will
  mirror the upstream `examples/run_with_hf.py` loop (resume from CSV by
  `status="completed"`, write append-only). When written, it lives in
  `src/apex_bench/runner.py`.
- DC2 method adapters — these live in **DC2**, not here. From DC2's POV, APEX
  is one more `Benchmark` in `src/dc2/benchmarks/`. The integration imports
  `apex_bench.dataset` and `apex_bench.grading` (when extracted) but never the
  CLI.
