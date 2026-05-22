# Evaluation plan — apex-bench

This document fixes the execution order for every (domain, method) cell on Mercor's APEX-v1-extended benchmark. The order is pre-registered so that rollout decisions cannot drift in response to interim results.

## Ordering rules

1. **Domains** are scheduled in **lexicographic ascending order of domain name** — Consulting, Finance, Legal, Medicine. The rule takes zero parameters; the order is recoverable from the dataset alone.
2. APEX-v1-extended has 25 tasks per domain in a single batch; there is no within-domain "world" to order across. Each domain is run as one slice of 25 tasks.
3. **Per domain, the three methods** are run in this order: **baseline (no memory) → Dynamic Ledger → TRACE**. All three share the same task slice, the same test profile, and the same judge; relative order is fixed only for reproducibility.
4. **Resume**: each method has a single CSV per repo (one for baseline, one for Dynamic Ledger, one for TRACE) and the runner appends to it. The Dynamic Ledger and TRACE ledgers carry forward across domains within the same method-CSV through their respective per-domain snapshot directories (`runs/<run>/dynamic_ledger/<Domain>/`, `runs/<run>/trace/<Domain>/`).

The Finance subset was run first as the project pilot; the rest of the rollout follows the rule above.

## Status

| Domain (lex order) | n | baseline | Dynamic Ledger | TRACE |
|---|---:|:---:|:---:|:---:|
| Consulting | 25 | — | — | — |
| Finance | 25 | ✓ | ✓ | — |
| Legal | 25 | — | — | — |
| Medicine | 25 | — | — | — |

## Continue the rollout

Each method has a single CSV per repo. Continuing extends that CSV; per-domain ledger snapshots are written under the same run directory.

**Next domain (Dynamic Ledger):**

```bash
apex-bench run --model grok-4.3-high --domain Consulting --limit 25 \
    --dynamic-ledger \
    --output runs/grok43high-dl/results.csv
```

**Next domain (baseline):**

```bash
apex-bench run --model grok-4.3-high --domain Consulting --limit 25 \
    --output runs/grok43high-baseline/results.csv
```

When all four domains are complete on baseline + Dynamic Ledger, run TRACE against a fresh CSV at `runs/grok43high-trace/results.csv` (its own per-domain cheatsheet starts empty for each domain).

## Pre-registered, not post-hoc

This file is the source of truth for the rollout order. Any deviation from it must be noted alongside the corresponding run in [`results.md`](../results.md).
