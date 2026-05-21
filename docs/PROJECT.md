# Project: test-time learning methods on Mercor's APEX benchmarks

This document explains the broader research project and how this
repository fits into it. It is intentionally short — see the per-method
PRDs and the README for details.

## Goal

Compare three test-time-learning configurations on Mercor's APEX
benchmarks at constant generator-side compute:

1. **Baseline** — vendor harness, no memory subsystem.
2. **memory subsystem** — no-ground-truth, dual-retrieval, single-curator
   playbook adapted from Suzgun et al., *Dynamic Cheatsheet: Test-Time
   Learning with Adaptive Memory* (2025). See
   [`DYNAMIC_LEDGER_PRD.md`](DYNAMIC_LEDGER_PRD.md).
3. **TRACE** — reflector + curator with GT-bit feedback, atomic-bullet
   cheatsheet adapted from Liao, Nair & Yang's *TRACE: Tool-augmented
   Reasoning via Atomic Cheatsheet Editing* (Stanford CS224N final
   project). See [`TRACE_PRD.md`](TRACE_PRD.md).

For both subsystems the curator (and, in TRACE, the reflector) runs on
**the same model as the test profile**. Only the **judge** model is
fixed (gpt-5.5 medium). Embeddings always use OpenAI
`text-embedding-3-large`.

## Sister repositories

The project ships two parallel harnesses, one per benchmark:

| Repository                                           | Benchmark                  | Surface                                | Domains |
|------------------------------------------------------|----------------------------|----------------------------------------|---------|
| **apex-bench** (this repo)                           | Mercor APEX-v1-extended    | Single-shot prose deliverable          | Finance, Legal, Consulting, Medicine            |
| **apex-agents-bench** (sister)                       | Mercor APEX-Agents         | Multi-turn ReAct toolbelt agent in a Dockerized environment (Archipelago) | Investment Banking, Law, Management Consulting |

Both repositories implement the same three configurations (Baseline,
memory subsystem, TRACE) on top of their respective vendor harnesses.
Where possible, structurally identical components (the dual-axis
retriever, the cosine-block dedup, the per-domain snapshot store, the
op contract) are mirrored line-for-line so cross-benchmark results are
genuinely comparable.

## What's in this repo

- `src/apex_bench/` — the baseline runner wrapper around Mercor's
  apex_evals, plus the `memory/` and `trace/` subpackages.
- `docs/DYNAMIC_LEDGER_PRD.md` — the memory subsystem specification.
- `docs/TRACE_PRD.md` — the TRACE specification.
- `tests/` — unit + fidelity tests; the baseline schema is byte-
  identical when neither subsystem is enabled.
- `vendor/apex_evals/` — pristine vendored apex_evals at the pinned
  commit (6cbf3f43).

## CLI surface, at a glance

```
apex-bench run --model <profile> [--domain D] [--limit N] [--task-ids …]
                 [--memory | --trace]
                 [--azure]
```

`--memory` and `--trace` are mutually exclusive. `--azure`
routes any GPT-5.5 chat completion (judge + test profile + curator)
through Azure-OpenAI; embeddings always use OpenAI.

## Reading the results

The baseline CSV columns are pinned by the
`test_dynamic_ledger_off_csv_schema_unchanged` fidelity test. The two
memory subsystems each append a known set of columns when enabled.
The README's *Results* table summarises Pass@1 (per-criterion score
≥ 99%) and mean score across configurations.
