# Reproducibility

> **Read this if you're asking:** "Why one run per task and not eight?
> Why gpt-5.5 as judge and not Gemini? How do I record a run so someone
> else can replicate it? What's the dataset license?"
>
> **TL;DR:** project policies and their reasons, dataset terms, what
> gets recorded per run.

A run of apex-bench is determined by:

1. The **code** — pinned via git SHA of this repo + the vendored upstream
   commit recorded in `vendor/apex_evals/UPSTREAM.md`.
2. The **deps** — pinned via `pyproject.toml` (notably `litellm==1.83.0`,
   which controls which model ids exist).
3. The **dataset** — `mercor/APEX-v1-extended`, fetched at setup time. The HF
   repo is mutable; we record the dataset SHA we used (see below).
4. The **policy** — the `Settings` defaults: judge model, judge temperature,
   `NUMBER_OF_RUNS`. Changing any of these makes the run incomparable to a
   prior one.
5. The **credentials environment** — provider rate limits and model versions
   are *not* under our control. A frontier model "version" is whatever the
   provider's API resolves on the day of the run.

## Recording a run

Every full benchmark run (not a smoke) should write, alongside the results:

- `run.yaml` with: apex-bench git SHA, vendor SHA, `Settings` fields, model
  ids and any provider-specific knobs, dataset SHA (see below).
- The catalog JSON (`apex-bench catalog -o catalog.json`) for the dataset
  state at run time.

We will codify this in `src/apex_bench/runner.py` when we add the full runner;
for now, smoke runs are not meant to be reproducible at this level.

## Pinning the dataset

The dataset is fetched as a working git clone in `data/APEX-v1-extended/`. To
record which dataset SHA you used:

```bash
git -C data/APEX-v1-extended rev-parse HEAD
```

If you fetched via `huggingface-cli` (no .git), use the Hugging Face dataset
page commit listing to record the SHA of the snapshot you downloaded.

## Dataset license and acceptable use

The dataset is `mercor/APEX-v1-extended`, distributed under **CC-BY-4.0** with
an additional clause:

> "APEX-v1-extended is intended exclusively for model evaluation. Any use of
> this dataset for training, fine-tuning, or parameter fitting is forbidden.
> Crawling or scraping the dataset is also forbidden."

> "We ask that:
> - You do *not* crawl, scrape, index, or download this dataset
>   programmatically.
> - You do *not* use this dataset for training models or any automated
>   processing without express permission from the dataset owner."

This repo uses the dataset for evaluation only. The DC2 test-time-learning
methods that read from APEX queries build a **runtime cheatsheet/ledger**
across queries; this is not weight training. Document this distinction in
any internal write-up that uses APEX.

## Project policy: one run per (task, model)

This is the single most consequential reproducibility choice in the project,
and it is intentional rather than budget-imposed.

Every reported number in this project uses **exactly one model call per
(task, model)**. The Mercor leaderboard uses 8 runs/task with a median
aggregator; we do not.

The trade we accept:

- ✅ **Comparability across methods.** With 5 DC2 methods × N models × 100
  tasks, even a single run per cell costs $500–$2000. Eight runs per cell
  would make a five-method comparison infeasible. The point of this project
  is the *cross-method comparison*, not the absolute number — and the
  cross-method signal is what 1 run/task preserves.
- ✅ **Reproducibility floor.** The run surface is fixed: same prompt,
  same attachments, same model profile, same judge, and one call per task.
  Provider-side nondeterminism still exists because these frontier APIs do
  not give us a portable seed guarantee.
- ❌ **No stability CIs from re-runs.** We cannot report "GPT-5.5 scored
  72.3% ± 1.4 across 8 runs". We get one number per cell.
- ❌ **No leaderboard-parity number.** We can report apples-to-apples
  cross-method comparisons but not leaderboard-comparable absolute scores.

Where the variance signal comes from instead:

- **Per-domain breakdown at n=25.** Splitting the 100 tasks into 4 domain
  bins gives four independent cell measurements per method.
- **Per-rubric-criterion granularity.** Each task scores ~10 binary criteria
  independently; with 25 tasks/domain that's ~250 binary judgments per
  (method, domain) cell. Binomial CIs on those are the rigorous stability
  estimate.

This policy is **enforced in code** via `apex_bench.config.RUNS_PER_TASK`
(module-level constant, not a Settings field) and asserted by
`tests/test_imports.py`. There is no CLI flag to override it. Future code
that needs to break this rule must change the constant in a reviewed PR with
a written justification.

## Project policy: judge is gpt-5.5 (medium reasoning by default)

The judge is fixed across every run in this project: **OpenAI `gpt-5.5`** with
no `reasoning_effort` override (OpenAI's default for gpt-5.5 is `medium`).
The vendor's `GradingModelConfig` does not plumb `model_configs` through to
LiteLLM's request, so the medium-effort default is what the API receives —
this is correct and intentional, not a workaround.

We picked GPT-5.5 over the upstream default Gemini 2.5 Flash for quality
reasons. We picked it over Claude Opus 4.6 (Bedrock) to keep judge costs
proportional to test-model costs. The judge stays *fixed* across all test
models so cross-model comparisons (e.g., "GPT-5.5 high vs Grok 4.3 high") are
measured against the same yardstick.

### Self-enhancement bias caveat

Cells where the test model is also `gpt-5.5` (any reasoning effort) have a
**within-family self-judging asymmetry**. The judge is the same model
weights, at a different reasoning effort. Published LLM-as-judge literature
shows ~5–15 percentage-point inflation in pure self-judging; within-family
(same weights, different config) bias is typically smaller but real.

For *cross-method* comparisons within a fixed test model (baseline vs DC on
GPT-5.5), the bias affects both arms equally and the delta is still
meaningful. For *cross-model* comparisons (GPT-5.5 vs Grok vs Claude),
the GPT-5.5 cells may be inflated relative to the others. Read absolute
GPT-5.5 numbers with this in mind.

If at any point a stronger absolute-number guarantee is needed, the
mitigation is to add Bedrock Opus 4.6 as a secondary judge and re-grade a
sample, then report the delta. That is out of scope for the current plan.

## Smoke vs benchmark vs leaderboard

| Mode | Tasks | Runs/task | Judge | Purpose |
|---|---|---|---|---|
| **Smoke** | 1 | 1 | configured judge | Pipeline verification |
| **Benchmark** (us) | 100 (public split) | **1** | gpt-5.5 | Cross-method comparison |
| **Leaderboard (Mercor)** | 400 (heldout) | 8 | Gemini 2.5 Pro Thinking=On | Direct leaderboard parity (not ours to run) |

We do not attempt to reproduce the leaderboard. We compute apples-to-apples
internal numbers across methods. Specifically, we cannot replicate Mercor's
leaderboard methodology in two places that we know of:
  - Number of runs per task (theirs: 8; ours: 1).
  - Judge model (theirs: gemini-2.5-pro Thinking=On per the dataset card;
    ours: gpt-5.5 medium).
We also do not assert that the upstream open-source harness's default parser
(Reducto) is what Mercor uses on the leaderboard — the dataset card does not
state that, and we have not verified it.

## What a result file should carry

When the full runner lands, each result row carries — in addition to
`percentage_score` and the rubric breakdown:

- `task_id`, `domain`
- `model_id`, provider, model version string from the response (if returned)
- `judge_model_id`, judge temperature, judge max-tokens
- `run_index` (1..NUMBER_OF_RUNS)
- `generation_tokens_in`, `generation_tokens_out`, `generation_tokens_total`
- `wall_time_seconds`

This is the row schema DC2 will eventually emit when it integrates.
