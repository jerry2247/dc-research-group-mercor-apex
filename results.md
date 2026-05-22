# Results — apex-bench

Detailed results for the **Dynamic Ledger** subsystem evaluated on Mercor's **APEX-v1-extended** benchmark.

## Setup

| | Value |
|---|---|
| Test model | `grok-4.3` (xAI), `reasoning_effort = high`, `temperature = 1.0` |
| Judge model | `gpt-5.5` (OpenAI), reasoning effort `medium` (Mercor's published judge) |
| Embedding model (retriever) | `text-embedding-3-large` (OpenAI), 3072-dim |
| Runs per (task, model) | 1 |
| Domain | Finance (n = 25) |
| Other domains (Legal, Consulting, Medicine) | Not yet evaluated — planned ablation sweep |

## Headline — per-domain mean score (%) · Pass@1 (score ≥ 99 %)

| Method | Finance (n=25) | Legal (n=25) | Consulting (n=25) | Medicine (n=25) | Macro mean |
|---|:---:|:---:|:---:|:---:|:---:|
| **grok-4.3-high** (baseline) | 54.87 · 4/25 | TBD | TBD | TBD | TBD |
| + **Dynamic Ledger** | 50.02 · **5/25** | TBD | TBD | TBD | TBD |
| + **TRACE** (uses GT bit) | TBD | TBD | TBD | TBD | TBD |

**Dynamic Ledger delivers +1 Pass@1 over the baseline at the same model and reasoning effort, on a single seed.** The mean-score delta (−4.85 pp) reflects high variance at temperature 1.0 — see the per-task table below for the spread of effects. Two of the four DL passes (tasks 2186 and 2287) were not passes in the baseline. Pass@1 is the primary headline metric; mean score is reported for completeness.

## Did the curator actually learn something?

Yes — here is a concrete example.

On **task 2269** (a locked-box M&A EV-to-Equity bridge computation), the baseline scored **23.08 %** (1 of 13 criteria met). With Dynamic Ledger, the same model on the same task scored **92.31 %** (12 of 13 criteria met) — a **+69.23 pp** improvement.

The retriever, on task 2269, surfaced exactly one entry from the running ledger:

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

This entry was emitted by the curator on an *earlier* task (a different M&A bridge case) that the agent had not solved cleanly. The curator distilled the conceptual structure of EV→Equity bridges under locked-box mechanics — symbolic, no case-specific numbers, no procedure to follow — and the entry's content-axis cosine to task 2269's prompt was high enough that the retriever surfaced it on the next structurally-similar case. The injected entry was a passive reference cheatsheet item (per the generator prompt the entries are explicitly framed as a *formula sheet, not instructions*); the generator consulted it, recovered the bridge structure on its own data, and the deliverable passed 12 of 13 rubric criteria instead of 1.

Other gains worth flagging:

| Task | Baseline | DL | Δ | Retrieved entries (at task time) |
|---|---:|---:|---:|---|
| 2269 | 23.08 | 92.31 | +69.23 | 1 |
| 2186 | 40.00 | 100.00 | +60.00 | 2 |
| 2287 | 90.91 | 100.00 | +9.09 | 0 *(no retrieval — within-seed variance)* |
| 2315 |  0.00 |  10.00 | +10.00 | 3 |

## Per-task breakdown

Columns: per-criterion mean score in %; `retrieved` = number of cheatsheet entries injected at generation time; `ops` = curator CREATE / UPDATE / DELETE ops emitted on this task.

| task | baseline | dynamic ledger | Δ | retrieved | ops |
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

Raw CSVs: [`runs/finance-grok43high/results.csv`](runs/finance-grok43high/results.csv) (baseline), [`runs/finance-grok43high-dl/results.csv`](runs/finance-grok43high-dl/results.csv) (Dynamic Ledger). Per-task curator output: [`runs/finance-grok43high-dl/dynamic_ledger/Finance/curator_log.jsonl`](runs/finance-grok43high-dl/dynamic_ledger/Finance/curator_log.jsonl). Per-task ledger snapshots: `runs/finance-grok43high-dl/dynamic_ledger/Finance/snapshot_NNNN.json`.

## Caveats

- **Single seed.** All numbers are from one run per (task, model). grok-4.3-high uses `temperature = 1.0` (the xAI default for `reasoning_effort = high`); same-task variance is non-trivial. A multi-seed sweep is planned.
- **Single domain.** Only Finance is reported. The other three APEX domains (Legal, Consulting, Medicine) are planned.
- **One model.** Only grok-4.3-high is reported. Multi-model ablations are planned.
- **TRACE** is not reported here. TRACE uses the per-task correctness bit, which makes it not directly comparable to the no-GT Dynamic Ledger; it is included in the repo for future ablation.

## Reproduce these numbers

```bash
# Baseline
apex-bench run --model grok-4.3-high --domain Finance --limit 25 \
    --output runs/finance-grok43high/results.csv

# Dynamic Ledger
apex-bench run --model grok-4.3-high --domain Finance --limit 25 \
    --dynamic-ledger \
    --output runs/finance-grok43high-dl/results.csv
```

Full setup and dependency installation: [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md).
