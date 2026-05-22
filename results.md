# Results — apex-bench

Detailed results for the **DC Retrieval Synthesis** subsystem evaluated on Mercor's **APEX-v1-extended** benchmark. Numbers are headline-only here; the source of truth is the per-task CSV (`runs/<run>/results.csv`) and the per-domain DC-RS state under `runs/<run>/dc_rs/<Domain>/`.

## Setup

| | Value |
|---|---|
| Test model | `grok-4.3` (xAI), `reasoning_effort = high`, `temperature = 1.0` |
| Judge model | `gpt-5.5` (OpenAI), reasoning effort `medium` (Mercor's published judge) |
| Embedding model (retriever) | `text-embedding-3-large` (OpenAI), 3072-dim |
| Runs per (task, model) | 1 |
| Rollout slice run end-to-end so far | Baseline on Finance, n = 25 |
| Rollout order for remaining cells | see [`docs/EVALUATION_PLAN.md`](docs/EVALUATION_PLAN.md) |

## Headline — per-criterion mean score (%) · Pass@1 (score ≥ 99 %)

| Method | Finance | Legal | Consulting | Medicine | Macro mean |
|---|:---:|:---:|:---:|:---:|:---:|
| `grok-4.3-high` (baseline) | 54.87 · 4/25 | TBD | TBD | TBD | TBD |
| + DC Retrieval Synthesis | TBD | TBD | TBD | TBD | TBD |
| + TRACE | TBD | TBD | TBD | TBD | TBD |

Each cell will accumulate as the rollout proceeds. The per-domain DC-RS state is isolated by design — a separate `dc_rs/<Domain>/` directory with its own `bank.jsonl` and `cheatsheet.txt` per domain — so the Finance bank does not carry into Legal/Consulting/Medicine.

## Per-task breakdown — DC Retrieval Synthesis

Rows are listed **in execution order** — the order in which the runner processed each task and the order in which the bank grew, so the `retrieved` column reads coherently across rows.

**Column meanings:**
- `score` — per-criterion mean rubric score on this task (0–100 %), as graded by the gpt-5.5 judge against Mercor's per-criterion rubric.
- `retrieved` — number of past pairs the retriever passed to the synthesizer at task start. DC-RS retrieves the top-k=3 most similar past pairs by cosine on the prompt embedding; on the first three tasks in a domain the bank has fewer than k entries and `retrieved` is correspondingly smaller.
- `cheatsheet_chars` — length of the synthesizer's output for this task. The synthesizer is run on every task; an unusually short value with `used_fallback = true` indicates the synthesizer omitted the `<cheatsheet>` wrapper and the runtime fell back to the raw retrieved-pairs block.

| task | baseline | DC Retrieval Synthesis | Δ | retrieved | cheatsheet_chars |
|---|---:|---:|---:|---:|---:|
| _Pending — fill in after the DC-RS Finance run completes._ | | | | | |
| **mean** | **54.87** | **TBD** | **TBD** | | |
| **Pass@1** | **4 / 25** | **TBD** | | | |

Raw CSVs (when populated): [`runs/grok43high-baseline/results.csv`](runs/grok43high-baseline/results.csv) (baseline), `runs/grok43high-dc-rs/results.csv` (DC Retrieval Synthesis). Per-task synthesizer diagnostics: `runs/grok43high-dc-rs/dc_rs/Finance/synthesizer_log.jsonl`. Per-task cheatsheet archive: `runs/grok43high-dc-rs/dc_rs/Finance/cheatsheets/task_<task_id>.txt`. Persistent bank: `runs/grok43high-dc-rs/dc_rs/Finance/bank.jsonl`.

## Caveats

- **Single seed.** Numbers will be from one run per (task, model). grok-4.3-high uses `temperature = 1.0` (the xAI default for `reasoning_effort = high`); same-task variance is non-trivial. A multi-seed sweep is planned.
- **Single domain in flight.** Only Finance is currently run end-to-end on baseline. The other three APEX domains (Legal, Consulting, Medicine) are pre-registered in [`docs/EVALUATION_PLAN.md`](docs/EVALUATION_PLAN.md) and pending.
- **One model.** Only grok-4.3-high is reported. Multi-model ablations are planned.
- **TRACE.** TRACE uses the per-task correctness bit, which makes it less directly comparable to the no-GT DC-RS; it is included in the repo for separate analysis.

## Reproduce these numbers

```bash
# Baseline
apex-bench run --model grok-4.3-high --domain Finance --limit 25 \
    --output runs/grok43high-baseline/results.csv

# DC Retrieval Synthesis
apex-bench run --model grok-4.3-high --domain Finance --limit 25 \
    --dc-rs \
    --output runs/grok43high-dc-rs/results.csv

# TRACE
apex-bench run --model grok-4.3-high --domain Finance --limit 25 \
    --trace \
    --output runs/grok43high-trace/results.csv
```

Continuing the rollout to the remaining domains uses the same `--output` paths so the per-domain DC-RS state keeps growing; see [`docs/EVALUATION_PLAN.md`](docs/EVALUATION_PLAN.md) for the order they are run in. Full setup: [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md).
