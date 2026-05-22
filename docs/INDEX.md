# Documentation index

Every doc in this folder, with a one-line purpose and a "read this if…"
column. Start here if you're new.

## Operational docs (read in this order)

| # | Doc | What it answers | Read this if you're asking… |
|---|---|---|---|
| 1 | [`../README.md`](../README.md) | **Start here.** First-time setup, how to run the benchmark, troubleshooting, project policies, doc index | "I just cloned this repo — what do I do?" |
| 2 | [`BENCHMARK_STRUCTURE.md`](BENCHMARK_STRUCTURE.md) | What the 100 APEX tasks look like, per-domain characterization, full per-task index with one-line summaries | "What's in the Finance domain?" / "What does task 1588 ask?" |
| 3 | [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) | The phased project plan: what we're doing in what order, with what budget and verification gates | "What's the project roadmap?" / "When do Claude profiles get wired?" |

## Reference / methodology docs

| Doc | What it answers | Read this if you're asking… |
|---|---|---|
| [`DYNAMIC_LEDGER_PRD.md`](DYNAMIC_LEDGER_PRD.md) | Specification of the memory subsystem subsystem — pipeline, entry shape, curator prompt design, CSV columns | "How does `--memory` actually work?" |
| [`TRACE_PRD.md`](TRACE_PRD.md) | Specification of the TRACE subsystem — pipeline, bullet shape, GT-bit threading, citation parsing | "How does `--trace` actually work?" |
| [`AUDIT.md`](AUDIT.md) | Line-by-line confirmation we match Mercor's harness behavior. Records every fidelity check with the regression test that protects it. | "Are we really running Mercor's harness?" / "What did we change?" |
| [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) | The 1-run/task policy, dataset license, self-bias caveats, what gets recorded per run | "Why one run, not eight?" / "Why isn't this leaderboard-comparable?" |
| [`HARNESS_NOTES.md`](HARNESS_NOTES.md) | How the vendored harness works internally — generation/grading flow, model id surface, known vendor bugs we work around | "What does the harness actually do under the hood?" / "Why are we passing `grading_prompt_template` explicitly?" |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | The wrapper-vs-vendor design split and our diff policy | "Why is this code in `src/` and not `vendor/`?" / "How do I resync upstream?" |
| [`../results.md`](../results.md) | Per-domain × per-method results table, per-task breakdown, and a worked example of an additive memory subsystem entry | "What numbers have we got so far?" |

## Provenance docs (in `vendor/apex_evals/`)

| Doc | What it answers |
|---|---|
| [`../vendor/apex_evals/UPSTREAM.md`](../vendor/apex_evals/UPSTREAM.md) | Pinned upstream commit SHA, when we vendored, resync procedure |
| [`../vendor/apex_evals/PATCHES.md`](../vendor/apex_evals/PATCHES.md) | Every vendor-source edit with diff and rationale (currently: 2-line addition to `MODEL_MAPPINGS`) |
| [`../vendor/apex_evals/LICENSE_UPSTREAM`](../vendor/apex_evals/LICENSE_UPSTREAM) | Upstream license (CC-BY-4.0) |

## Quick lookup: where do I find…

| Question | Look here |
|---|---|
| How to run the benchmark on Finance / 25 tasks / Grok 4.3 high | README §3 |
| What credentials I need in `.env` | README §2.2 |
| The cost estimate per profile | README §3 (Cost note) — and per-task example budget |
| Why we use gpt-5.5 as judge instead of Gemini | REPRODUCIBILITY.md §"Project policy: judge is gpt-5.5" |
| Why we don't do 8 runs per task | REPRODUCIBILITY.md §"Project policy: one run per (task, model)" |
| Why Claude/Bedrock isn't available yet | IMPLEMENTATION_PLAN.md §1 + test_models.py `_DEFERRED_CLAUDE_PROFILES_NOTE` |
| What changed in the vendored harness | vendor/apex_evals/PATCHES.md |
| How scoring actually works (per criterion, unweighted) | AUDIT.md §A3 + §A4; HARNESS_NOTES.md |
| What tools / web search / code execution the model has access to | AUDIT.md §A8 — answer: NONE |
| What the rubric JSON structure looks like | BENCHMARK_STRUCTURE.md §"per-domain rubric style" |
| The full list of 100 task IDs | BENCHMARK_STRUCTURE.md §"Full per-task index" |
| How to add a new test-model profile | source: `src/apex_bench/test_models.py` (code change, not a CLI flag — by design) |
| How to resume an interrupted run | README §3.5 |
| Why every task has attachments | catalog output (`data/catalog.json`) and BENCHMARK_STRUCTURE.md §"Attachments" |
