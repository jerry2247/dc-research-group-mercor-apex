# Project: test-time learning methods on Mercor's APEX benchmarks

This document explains the broader research project and how this
repository fits into it. It is intentionally short — see the per-method
PRDs and the README for details.

## Goal

Compare three test-time-learning configurations on Mercor's APEX
benchmarks at constant generator-side compute:

1. **Baseline** — vendor harness, no memory subsystem.
2. **DC Retrieval Synthesis (DC-RS)** — single-synthesizer cheatsheet
   built per task from top-k retrieved past `(prompt, deliverable)`
   pairs. Adapted from the retrieval-synthesis variant of Suzgun et al.,
   *Dynamic Cheatsheet: Test-Time Learning with Adaptive Memory* (2025).
   See [`DC_RS_PRD.md`](DC_RS_PRD.md).
3. **TRACE** — reflector + curator with GT-bit feedback, atomic-bullet
   cheatsheet adapted from Liao, Nair & Yang's *TRACE: Tool-augmented
   Reasoning via Atomic Cheatsheet Editing* (Stanford CS224N final
   project). See [`TRACE_PRD.md`](TRACE_PRD.md).

For both subsystems the synthesizer (DC-RS) / curator + reflector
(TRACE) run on **the same model as the test profile**. Only the
**judge** model is fixed (gpt-5.5 medium). Embeddings always use OpenAI
`text-embedding-3-large`.

## Sister repositories

The project ships two parallel harnesses, one per benchmark:

| Repository                                           | Benchmark                  | Surface                                | Domains |
|------------------------------------------------------|----------------------------|----------------------------------------|---------|
| **apex-bench** (this repo)                           | Mercor APEX-v1-extended    | Single-shot prose deliverable          | Finance, Legal, Consulting, Medicine            |
| **apex-agents-bench** (sister)                       | Mercor APEX-Agents         | Multi-turn ReAct toolbelt agent in a Dockerized environment (Archipelago) | Investment Banking, Law, Management Consulting |

Both repositories implement the same three configurations (Baseline,
DC-RS, TRACE) on top of their respective vendor harnesses. Where
possible, structurally identical components (the cosine retriever, the
per-domain state store) are mirrored so cross-benchmark results are
genuinely comparable.

## What's in this repo

- `src/apex_bench/` — the baseline runner wrapper around Mercor's
  apex_evals, plus the `dc_rs/` and `trace/` subpackages.
- `docs/DC_RS_PRD.md` — the DC-RS specification.
- `docs/TRACE_PRD.md` — the TRACE specification.
- `tests/` — unit + fidelity tests; the baseline schema is byte-
  identical when neither subsystem is enabled.
- `vendor/apex_evals/` — pristine vendored apex_evals at the pinned
  commit (6cbf3f43).

## CLI surface, at a glance

```
apex-bench run --model <profile> [--domain D] [--limit N] [--task-ids …]
                 [--dc-rs | --trace]
                 [--azure]
```

`--dc-rs` and `--trace` are mutually exclusive. `--azure` routes any
GPT-5.5 chat completion (judge + test profile + synthesizer or
curator) through Azure-OpenAI; embeddings always use OpenAI.

## Reading the results

The baseline CSV columns are pinned by the fidelity tests
(`tests/test_dc_rs_fidelity.py` and `tests/test_trace_fidelity.py`).
The two memory subsystems each append a known set of columns when
enabled. The README's *Results* table summarises Pass@1
(per-criterion score ≥ 99%) and mean score across configurations.
