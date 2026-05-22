# Evaluation plan — apex-bench

This document fixes the execution order for every (domain, method) cell on Mercor's APEX-v1-extended benchmark. The order is pre-registered so that rollout decisions cannot drift in response to interim results.

## Ordering rules

1. **Domains** are scheduled in **lexicographic ascending order of domain name** — Consulting, Finance, Legal, Medicine. The rule takes zero parameters; the order is recoverable from the dataset alone.
2. APEX-v1-extended has 25 tasks per domain in a single batch; there is no within-domain "world" to order across. Each domain is run as one slice of 25 tasks.
3. **Per domain, the three methods** are run in this order: **baseline (no memory) → DC-RS → TRACE**. All three share the same task slice, the same test profile, and the same judge; relative order is fixed only for reproducibility.
4. **Resume**: each method has a single CSV per repo (one for baseline, one for DC-RS, one for TRACE) and the runner appends to it. The DC-RS bank and the TRACE cheatsheet carry forward across domains within the same method-CSV through their respective per-domain directories (`runs/<run>/dc_rs/<Domain>/`, `runs/<run>/trace/<Domain>/`).

## Status

| Domain (lex order) | n | baseline | DC Retrieval Synthesis | TRACE |
|---|---:|:---:|:---:|:---:|
| Consulting | 25 | — | — | — |
| Finance | 25 | ✓ | — | — |
| Legal | 25 | — | — | — |
| Medicine | 25 | — | — | — |

## Continue the rollout

Each method has a single CSV per repo. Continuing extends that CSV; per-domain state directories are written under the same run directory.

**Next domain (DC-RS):**

```bash
apex-bench run --model grok-4.3-high --domain Consulting --limit 25 \
    --dc-rs \
    --output runs/grok43high-dc-rs/results.csv
```

**Next domain (baseline):**

```bash
apex-bench run --model grok-4.3-high --domain Consulting --limit 25 \
    --output runs/grok43high-baseline/results.csv
```

When all four domains are complete on baseline + DC-RS, run TRACE against a fresh CSV at `runs/grok43high-trace/results.csv` (its own per-domain cheatsheet starts empty for each domain).

## Pre-registered, not post-hoc

This file is the source of truth for the rollout order. Any deviation from it must be noted alongside the corresponding run in [`results.md`](../results.md).
