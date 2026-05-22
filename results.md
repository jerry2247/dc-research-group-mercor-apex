# Results — apex-bench

Detailed results for the **memory subsystem** subsystem evaluated on Mercor's **APEX-v1-extended** benchmark. Numbers are headline-only here; the source of truth is the per-task CSV (`runs/<run>/results.csv`) and the per-task ledger snapshots (`runs/<run>/memory/<Domain>/`).

## Setup

| | Value |
|---|---|
| Test model | `grok-4.3` (xAI), `reasoning_effort = high`, `temperature = 1.0` |
| Judge model | `gpt-5.5` (OpenAI), reasoning effort `medium` (Mercor's published judge) |
| Embedding model (retriever) | `text-embedding-3-large` (OpenAI), 3072-dim |
| Runs per (task, model) | 1 |
| Rollout slice run end-to-end so far | Finance, n = 25 |
| Rollout order for remaining cells | see [`docs/EVALUATION_PLAN.md`](docs/EVALUATION_PLAN.md) |

## Headline — per-criterion mean score (%) · Pass@1 (score ≥ 99 %)

| Method | Finance | Legal | Consulting | Medicine | Macro mean |
|---|:---:|:---:|:---:|:---:|:---:|
| `grok-4.3-high` (baseline) | 54.87 · 4/25 | TBD | TBD | TBD | TBD |
| + memory subsystem | 50.02 · **5/25** | TBD | TBD | TBD | TBD |
| + TRACE | TBD | TBD | TBD | TBD | TBD |

Each cell will accumulate as the rollout proceeds. The per-domain memory subsystem is isolated by design — a separate `memory/<Domain>/` snapshot tree per domain — so the Finance ledger does not carry into Legal/Consulting/Medicine.

## Did the curator learn something?

Yes. Concrete worked example.

On **task 2269** (a locked-box M&A EV-to-Equity bridge computation), the baseline scored **23.08 %** (1 of 13 criteria met). With memory subsystem, the same model on the same task scored **92.31 %** (12 of 13 criteria met) — a **+69.23 pp** improvement.

The retriever, on task 2269, surfaced exactly one entry from the running ledger (emitted by the curator on an earlier M&A bridge case):

```
section:         EV to Equity Bridge in Locked Box M&A Transactions
source_problem:  Preparing EV to Equity bridges for locked box M&A deals
                 requiring normalization of working capital against LTM
                 average and classification of excess cash and debt-like items
content:
  Equity Value at Locked Box Date equals Enterprise Value plus Excess Cash
  (cash above minimum requirements) minus Debt and Debt-like items (including
  tax payables) plus Working Capital Adjustments, where the adjustment is
  actual NWC at locked box date minus target NWC defined as the twelve-month
  average ending at the locked box date.
```

This is a symbolic, formula-shape entry — passive reference content, not a procedure. The generator-side injection block frames it as a formula sheet ("treat the cheatsheet the way you'd treat a formula sheet during an exam — do not follow it"), so the generator's own reasoning stayed authoritative; the entry's role was to spare the generator from re-deriving the bridge structure.

Other gains on the Finance slice (single-seed, see Caveats):

| Task | Baseline | memory subsystem | Δ | Retrieved entries (at task time) |
|---|---:|---:|---:|---|
| 2269 | 23.08 | 92.31 | +69.23 | 1 |
| 2186 | 40.00 | 100.00 | +60.00 | 2 |
| 2287 | 90.91 | 100.00 | +9.09 | 0 *(no retrieval at that point — within-seed variance)* |
| 2315 |  0.00 |  10.00 | +10.00 | 3 |

## Per-task breakdown

Rows are listed **in execution order** — the order in which the runner processed each task and the curator's ordinal at the time of its call. This is the order in which the ledger grew, so the `retrieved` column reads coherently across rows.

**Column meanings:**
- `score` — per-criterion mean rubric score on this task (0–100 %), as graded by the gpt-5.5 judge against Mercor's per-criterion rubric.
- `retrieved` — number of cheatsheet entries the retriever injected at task start. Retrieval is dual-axis top-5 cosine (top-5 on the entry's `content_embedding` axis, top-5 on its `source_problem_embedding` axis, deduplicated — so at most 10 candidates) followed by a `retrieval_similarity_threshold = 0.40` floor that drops any candidate whose best-axis cosine to the task prompt is below 0.40. The final count is therefore `min(10, # active entries scoring ≥ 0.40 against this task)` — it varies because the cosine distribution against each task is different, not because retrieval is arbitrary.
- `ops` — what the curator wrote *after* this task: `<N>C/<N>U/<N>D` for CREATE/UPDATE/DELETE counts, or `—` when the curator emitted nothing (the task did not surface a transferable lesson).

| task | baseline | memory | Δ | retrieved | ops |
|---|---:|---:|---:|---:|---:|
| 1588 | 60.00 | 0.00 | −60.00 | 0 | 1C/0U/0D |
| 2107 | 46.67 | 46.67 | +0.00 | 0 | 1C/0U/0D |
| 2108 | 100.00 | 100.00 | +0.00 | 1 | — |
| 2120 | 77.78 | 33.33 | −44.45 | 0 | — |
| 2121 | 0.00 | 0.00 | +0.00 | 0 | — |
| 2145 | 10.00 | 10.00 | +0.00 | 0 | — |
| 2157 | 42.86 | 42.86 | +0.00 | 2 | — |
| 2186 | 40.00 | 100.00 | **+60.00** | 2 | 1C/0U/0D |
| 2192 | 80.00 | 80.00 | +0.00 | 0 | 1C/0U/0D |
| 2205 | 50.00 | 16.67 | −33.33 | 0 | 1C/0U/0D |
| 2217 | 100.00 | 70.00 | −30.00 | 1 | 1C/0U/0D |
| 2228 | 20.00 | 20.00 | +0.00 | 3 | — |
| 2230 | 62.50 | 62.50 | +0.00 | 1 | 1C/0U/0D |
| 2232 | 50.00 | 30.00 | −20.00 | 3 | — |
| 2261 | 100.00 | 100.00 | +0.00 | 0 | — |
| 2266 | 60.00 | 20.00 | −40.00 | 0 | — |
| 2269 | 23.08 | 92.31 | **+69.23** | 1 | 1C/0U/0D |
| 2287 | 90.91 | 100.00 | +9.09 | 0 | — |
| 2288 | 75.00 | 33.33 | −41.67 | 2 | 0C/1U/0D |
| 2294 | 93.75 | 93.75 | +0.00 | 5 | 1C/0U/0D |
| 2302 | 10.00 | 10.00 | +0.00 | 5 | 1C/0U/0D |
| 2308 | 100.00 | 100.00 | +0.00 | 2 | — |
| 2315 | 0.00 | 10.00 | +10.00 | 3 | — |
| 2317 | 70.00 | 70.00 | +0.00 | 0 | 1C/0U/0D |
| 2333 | 9.09 | 9.09 | +0.00 | 6 | 1C/0U/0D |
| **mean** | **54.87** | **50.02** | **−4.85** | | |
| **Pass@1** | **4 / 25** | **5 / 25** | | | |

Raw CSVs: [`runs/grok43high-baseline/results.csv`](runs/grok43high-baseline/results.csv) (baseline), [`runs/grok43high-dl/results.csv`](runs/grok43high-dl/results.csv) (memory subsystem). Per-task curator output: [`runs/grok43high-dl/memory/Finance/curator_log.jsonl`](runs/grok43high-dl/memory/Finance/curator_log.jsonl). Per-task ledger snapshots: `runs/grok43high-dl/memory/Finance/snapshot_NNNN.json`.

## Caveats

- **Single seed.** All numbers are from one run per (task, model). grok-4.3-high uses `temperature = 1.0` (the xAI default for `reasoning_effort = high`); same-task variance is non-trivial. A multi-seed sweep is planned.
- **Single domain.** Only Finance is reported. The other three APEX domains (Legal, Consulting, Medicine) are pre-registered in [`docs/EVALUATION_PLAN.md`](docs/EVALUATION_PLAN.md) and pending.
- **One model.** Only grok-4.3-high is reported. Multi-model ablations are planned.
- **TRACE** is not reported here. TRACE uses the per-task correctness bit, which makes it not directly comparable to the no-GT memory subsystem; it is included in the repo for future ablation.

## Reproduce these numbers

```bash
# Baseline
apex-bench run --model grok-4.3-high --domain Finance --limit 25 \
    --output runs/grok43high-baseline/results.csv

# memory subsystem
apex-bench run --model grok-4.3-high --domain Finance --limit 25 \
    --memory \
    --output runs/grok43high-dl/results.csv
```

Continuing the rollout to the remaining domains uses the same `--output` paths so the per-domain ledger trees keep their own state; see [`docs/EVALUATION_PLAN.md`](docs/EVALUATION_PLAN.md) for the order they are run in. Full setup: [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md).
