# APEX-v1 implementation plan

> **Status note (2026-05-19):** this is a historical planning document. The
> current executable policy is in `README.md`, `docs/AUDIT.md`, and
> `docs/REPRODUCIBILITY.md`. In particular, the active judge is `gpt-5.5`,
> judge token/cost columns are intentionally not saved, and exact provider
> billing cost is not derived from LiteLLM's local estimate.

> **Read this if you're asking:** "What is the overall project
> roadmap? When do Claude profiles get wired? When do we start the
> DC-vs-baseline comparison? What needs to happen before a full run?"
>
> **TL;DR:** phase-by-phase plan from setup → no-DC baseline → DC
> integration, with budget estimates and verification gates per phase.

A senior-scientist plan for getting from "setup done" to "DC-vs-baseline
numbers on the public split". The order is deliberate; each phase has
explicit exit criteria so a failed phase blocks the next one.

---

## 0. State as of this plan

**Harness integrity (verified):**

```
$ diff -rq vendor/apex_evals /tmp/apex-evals/apex-evals/apex-evals-v1-extended
Only in vendor/apex_evals: LICENSE_UPSTREAM
Only in vendor/apex_evals: UPSTREAM.md
```

Vendor code is **bit-identical** to upstream commit
`6cbf3f43156bf332329abe76ed4a695fc71ec5b0` (2026-04-09). The only files we
added are provenance (a copy of the upstream LICENSE renamed for clarity, and
a UPSTREAM.md recording the SHA and our diff policy). Zero harness source has
been touched.

The vendor has one known bug — `grading/executor.py:18` loads the grading
prompt from a CWD-relative path. We work around it **in our wrapper** by
passing `grading_prompt_template=` explicitly on every `GradingTask`. The
text we pass is read verbatim from the vendor's own `prompt/grading_prompt.txt`,
so the judge sees exactly what the upstream runner would have shown it.
This is documented in `docs/HARNESS_NOTES.md`.

**Wrapper additions** (live in `src/apex_bench/`, never in `vendor/`):
- `config.py` — sets default judge = `claude-opus-4-5-20251101`. This plan
  changes the judge again (to Opus 4.6 via Bedrock, see Phase 1).
- `dataset.py`, `catalog.py` — read-only typed loader + dataset characterization.
- `smoke.py` — single-task end-to-end runner using the vendor's
  `GenerationTask` / `GradingTask` exactly as the upstream API exposes them.
- `cli.py` — Typer CLI: `info`, `catalog`, `smoke`.

**Catalog ran cleanly** (`data/catalog.json`):

| | |
|---|---|
| Total tasks | 100 |
| Domains | Consulting=25, Finance=25, Legal=25, Medicine=25 |
| Prompt chars (min / median / max) | 197 / 1,276 / 5,239 |
| Rubric chars (min / median / max) | 3,552 / 10,810 / 28,369 |
| Rubric criteria (min / median / max) | 5 / 10 / 25 |
| Tasks with attachments | **100 / 100** |
| Tasks with missing attachments | 0 |

**The implication:** every single public task has PDF attachments. This is the
single most important fact for sequencing the next steps. We cannot smoke-test
without a working PDF parsing path. We will not pretend otherwise.

---

## 1. Phase 1 — Lock the model surface

The user-supplied evaluation surface:

| Role | Model (intended) | Resolved API ID | Provider/route |
|---|---|---|---|
| **Judge** | Claude Opus 4.6 via AWS Bedrock | `bedrock/us.anthropic.claude-opus-4-6-v1:0` (cross-region inference profile) | Bedrock |
| **Test model A** | GPT-5.5 (NOT 5.5-pro), reasoning_effort = xhigh | `gpt-5.5` with `model_configs={"reasoning_effort": "xhigh"}` | OpenAI |
| **Test model B** | Grok 4.3, top-tier reasoning | `grok-4.3` with `model_configs={"reasoning_effort": "high"}` | xAI |

**Explicit note on test model A:** the model id is the base `gpt-5.5`, not
`gpt-5.5-pro`. The two are separate OpenAI SKUs with separate price tiers.
We chose plain `gpt-5.5` at `xhigh` reasoning over `gpt-5.5-pro` at any
tier — the reasoning escalation gets us most of the way to flagship quality
at substantially lower per-token cost. Do not silently substitute `-pro`
into the MODELS list later.

### 1.1 Bedrock Opus 4.6 — the precise gotcha

> "Claude Opus 4.6 (anthropic.claude-opus-4-6-v1) still requires an inference
> profile ARN and cannot be used as a direct model ID." — LiteLLM Bedrock docs

The bare model id `bedrock/anthropic.claude-opus-4-6-v1` will fail. We must use
one of:

- `bedrock/us.anthropic.claude-opus-4-6-v1:0` — US cross-region inference profile.
- `bedrock/eu.anthropic.claude-opus-4-6-v1:0` — EU profile.
- `bedrock/global.anthropic.claude-opus-4-6-v1:0` — Global profile.
- `bedrock/converse/arn:aws:bedrock:<region>:<acct>:application-inference-profile/...`
  — application-defined profile (for cost tracking per project; uses the
  `converse/` route).

Default plan: **`us.anthropic.claude-opus-4-6-v1:0`** unless we explicitly
need EU/global. AWS-side prerequisites that have to be done *outside this
repo*:

1. **Bedrock model access requested and approved** for the chosen profile in
   the chosen AWS account, in *every* region the cross-region profile spans
   (for `us.`, that's us-east-1, us-east-2, us-west-2 at minimum — check
   AWS's Supported Regions for Inference Profiles table at run time).
2. **AWS credentials available to the venv.** Three options, ordered by
   robustness:
   - `AWS_PROFILE=<profile-name>` in `.env` with `~/.aws/credentials`
     configured — preferred for local work.
   - `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + `AWS_REGION` in `.env`
     — works for headless / CI.
   - `AWS_BEARER_TOKEN_BEDROCK` — newer short-lived token option; supported
     by LiteLLM 1.83.

   LiteLLM picks up these env vars automatically through boto3.
3. **Service quotas.** Check Bedrock console → Service Quotas → the
   `Anthropic Claude Opus 4.6` TPM / RPM line for your region. APEX rubric
   grading is bursty (one judge call per task; many tokens per call). Default
   account quotas can throttle. If hitting a wall, request a quota raise.

**Exit criterion for Phase 1.1.** A one-liner that proves Opus 4.6 routes:

```bash
python -c "
import os
from dotenv import load_dotenv; load_dotenv()
import litellm
resp = litellm.completion(
    model='bedrock/us.anthropic.claude-opus-4-6-v1:0',
    messages=[{'role':'user','content':'reply with the single word: ok'}],
    max_tokens=10,
)
print(resp.choices[0].message.content)
"
```

Must print `ok` (modulo whitespace). If it errors with `AccessDeniedException`,
go back to AWS console and request model access. If it errors with
`ValidationException: invalid model id`, you have the inference-profile prefix
wrong — re-check against
`aws bedrock list-inference-profiles --type-equals SYSTEM_DEFINED --region us-east-1`.

### 1.2 GPT-5.5 — the `xhigh` parameter

`reasoning.effort` on GPT-5.5 accepts `none | low | medium (default) | high |
xhigh`. The model is the base **`gpt-5.5`** SKU, not `gpt-5.5-pro`:

```python
ModelConfig(
    model_id="gpt-5.5",                      # NOT "gpt-5.5-pro" — see §1
    max_tokens=128_000,
    max_input_tokens=400_000,                # GPT-5.5 1M context — cap defensively
    model_configs={"reasoning_effort": "xhigh", "verbosity": "medium"},
    number_of_runs=1,                        # project policy — locked at 1
)
```

**Cost note.** `xhigh` substantially increases reasoning tokens (not visible
to the model API consumer as separate billing in most accounting paths;
they're rolled into output tokens). Plan for the high end of the cost range.
Choosing `gpt-5.5 xhigh` over `gpt-5.5-pro` at lower effort gives us most of
the flagship-quality signal at a meaningfully lower per-token bill — that is
the design intent.

### 1.3 Grok 4.3 — top-tier mode

xAI exposes three reasoning intensity levels on Grok 4.3. "Top tier" maps to
the `high` tier (xAI's published name; there is no `xhigh` on Grok). Note that
**Grok 4.20 is xAI's flagship**, not 4.3 — confirm with the user whether
they want 4.20 instead. Plan as written assumes 4.3 high.

```python
ModelConfig(
    model_id="grok-4.3",
    max_tokens=128_000,
    max_input_tokens=900_000,
    model_configs={"reasoning_effort": "high"},
    number_of_runs=1,
)
```

### 1.4 Wrapper change — replace the default judge

`src/apex_bench/config.py::DEFAULT_JUDGE_MODEL` flips from
`claude-opus-4-5-20251101` to `bedrock/us.anthropic.claude-opus-4-6-v1:0`.
One-line wrapper change. Vendor untouched.

---

## 2. Phase 2 — Make smoke pass with attachments

Every public-split task has PDFs, so smoke without attachment handling is a
non-starter. Two paths:

### 2.1 Reducto — what Mercor's harness ships, full stop

This is the project's parsing path. The vendored
`parser/__init__.py` registers `ReductoParser` and only `ReductoParser`.
`ReductoParser` handles PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX, CSV, TXT,
HTML, and common image formats (see
`parser/builtin/reducto_parser.py:30-41` for the canonical
`supported_extensions` list). It uses Reducto's API (and
`REDUCTO_API_KEY`) to OCR + extract text. The vendor caches parsed text
on disk keyed by content hash (`cache_parsed_documents=True` by default)
— re-runs are free.

Setup: `REDUCTO_API_KEY=...` in `.env`. That is the whole setup.

**Project policy:** no custom parser, no "skip parsing" mode. We use what
Mercor's harness ships. The Mercor *leaderboard* may or may not use
Reducto — that is not stated in the dataset card and we have not verified
it, so we do not claim leaderboard parity from this choice. We simply use
the upstream harness's parser surface as-is, which is the only credible
"don't reinvent the wheel" stance.

### 2.2 What we are NOT doing

For the record (so a future reader doesn't re-litigate this):
  - **No custom parser.** Building one that handles PDF + OCR + CSV +
    XLSX + DOCX as well as Reducto is non-trivial and produces numbers
    not comparable to anyone else's runs. Decided against.
  - **No "skip parsing" mode.** The harness supports `parsing_method=None`
    but most APEX tasks reference the attachment data directly ("use the
    attached CSV…"), so the model would have to hallucinate. Not useful
    for any reportable number.

**Exit criterion for Phase 2.** `apex-bench smoke -m grok-4.3 --allow-attachments
--domain Consulting` prints a `percentage_score` in `[0, 100]` and exits 0.

---

## 3. Phase 3 — No-cheatsheet baseline runs (the real number-producing phase)

Once Phase 1 + 2 pass, run the no-DC baseline. This is what the user asked
about as "DC versus no cheatsheet" — and the no-cheatsheet half *is*
the upstream harness behavior. No wrapper code is needed for it beyond what
exists.

### 3.1 Build `apex-bench run`

Today the wrapper has `apex-bench smoke` (one task). We need
`apex-bench run` (all-100, multiple models, R runs each, with resume from
the output CSV). The shape mirrors upstream `examples/run_with_hf.py` —
specifically:

- Read tasks from CSV.
- For each (task × model × run_index): generate, grade, append row.
- Skip tasks already present in the output CSV with `status="completed"`
  (resume semantics).
- Compute aggregate stats: median across runs per task, mean per domain,
  overall.

I will write this as `src/apex_bench/runner.py` + `apex-bench run` CLI
command. It will NOT modify the vendor; it will compose `GenerationTask` and
`GradingTask` exactly as upstream does, with the three judge/test models
above hard-coded as the default MODELS list (overridable via a `--models`
YAML).

### 3.2 Run plan

Project policy is **1 run per (task, model)**. There is no stability /
leaderboard-parity tier here — that is by design, see
`docs/REPRODUCIBILITY.md`. The available knobs are *which* tasks and
*which* models, not how many times to repeat them.

| Run | Models | Tasks | Budget estimate |
|---|---|---|---|
| **Pilot** | One cheap test model (Grok 4.3 high) | 5 tasks (1–2 per domain) | $3–$10 |
| **Per-domain explore** | 1 test model | 25 (single domain) | $20–$80 |
| **Full baseline** | GPT-5.5 xhigh, Grok 4.3 high | 100 (all four domains) | $100–$400 |

Cost includes generation + Opus 4.6 judging + Reducto parsing. Variance is
driven by Legal-domain attachment payloads (1–9 PDFs per task, up to 5.3 MB).
A pilot in Consulting (single-CSV, ~3 KB attachments) will run for under $10
total. A 25-task Legal sweep can run 5–10× that.

For comparing DC methods against the baseline (Phase 4), each method runs
the same 1 pass per task — but there are 5 methods (baseline + 4 DC
variants), so the per-method budget compounds × 5 in Phase 4, not via
runs-per-task.

**Exit criterion for Phase 3.** A `runs/baseline_<sha>/results.csv` and a
short markdown table with per-domain and overall accuracy for GPT-5.5 and
Grok 4.3, written automatically by `apex-bench run`. **This is the no-DC
number that DC must beat.**

---

## 4. Phase 4 — Add DC versus no-cheatsheet

This is the phase where this repo stops being "APEX setup" and starts being
"the DC-on-APEX experiment". Important architectural choice ahead.

### 4.1 Where do DC methods live?

Two clean options:

**Option A — integrate APEX into DC2 (recommended).** Add a new
`@register_benchmark class APEXv1` in DC2 at `src/dc2/benchmarks/apex_v1.py`.
DC2's existing `Method` registry (baseline / dc_cu / dc_rs / ace / dl) all
run on the new benchmark for free. APEX-side concerns — judge calls, PDF
parsing — get imported from this repo (`apex_bench.dataset`, possibly a thin
`apex_bench.grading` we'd extract). DC2 emits its standard
`runs/<bench>/<method>/<model>/queries.jsonl` shape; no new schema.

**Option B — implement DC inside this repo.** Build a `src/apex_bench/dc/`
package that re-implements the DC variants against the APEX-specific
interface. Faster on day 1 but creates a second DC implementation we'd have
to maintain.

A senior decision: **A**, every time. The harness is the volatile thing here
(APEX); the methods are well-understood (DC2's). Plug APEX into the methods,
not the other way around.

### 4.2 What "DC versus no cheatsheet" actually means on APEX

- "No cheatsheet" = DC2's `baseline` method. Generator-only, no memory,
  XML-protocol response. This is the apples-to-apples comparator for the
  upstream APEX runner — they are computing the same thing under different
  prompt shells, and we should verify they agree within a few percentage
  points on the same tasks/models. Disagreement bigger than that is a
  pipeline bug.
- "With cheatsheet" = DC2's `dc_cu`, `dc_rs`, `ace`, `dl`. Same 100 tasks,
  same models, same judge, methods run across the queries in a fixed seeded
  order so each method builds its memory under identical curriculum
  conditions.

### 4.3 Open research questions before running Phase 4

These are not blockers for setup, but they are blockers for *reporting* the
numbers honestly. Each is called out in DL_DEEP_DIVE.md but worth restating:

1. **APEX has no per-task ground-truth answer**, only a rubric the judge
   sees. DC2's no-label invariant survives unchanged. TRACE-style methods
   that use a GT-comparing reflector cannot run as-is; they either degrade
   to a no-label reflector or are excluded from this comparison.
2. **Example order matters.** DC2's `seed=10` shuffles before truncation.
   Use the same seed across methods so memory states evolve under the same
   curriculum.
3. **Judge tokens vs generator tokens.** Current policy: do not save judge
   token/cost columns in apex-bench result rows. The judge is shared
   infrastructure, not part of the method.

---

## 5. Phase 5 — Report

Project policy is one run per (task, model), so there is no stability tier
via run-repetition. Instead the variance signal comes from per-domain
breakdowns at fixed n=25 per domain. Once Phase 4 produces method-comparison
numbers:

- Per-domain accuracy table — APEX has known difficulty asymmetry across the
  four domains, and a method may help on Consulting while neutralizing on
  Finance.
- Per-rubric-criterion analysis — every task scores N criteria
  independently, so n=25 tasks × ~10 criteria gives ~250 binary judgments
  per (domain, method) cell. Confidence intervals on those binomials are
  the rigorous version of "is the difference real".
- Tokens-to-correct cost per method (DC2 already emits this for AIME /
  MMLU-Pro / finance; same machinery for APEX once integrated).
- Write the comparison report in DC2's `figures/apex_v1/`, matching DC2's
  existing per-benchmark report structure.

---

## 6. What gets pushed when

This plan is the gate for committing what's in the repo today. Do NOT push
to the private GitHub remote until:

- Phase 1 model resolution is confirmed (you've eyeballed Opus 4.6 routing
  with the one-liner in §1.1 — even if you choose to defer Reducto).
- This document has been read and approved.

After approval, the first commit lands with everything in §0 plus this plan,
and we move into Phase 1.

---

## Appendix A — Configurable knobs at a glance

| Setting | Where | Default |
|---|---|---|
| Judge model | `src/apex_bench/config.py:DEFAULT_JUDGE_MODEL` | `gpt-5.5` |
| Judge temperature | same file | 1.0 |
| Judge max tokens | same file | 32,000 |
| Number of runs per task | `apex_bench.config.RUNS_PER_TASK` (constant, not a CLI flag) | **1, locked** |
| Parsing method | `Settings.parsing_method` | `"reducto"` |
| Test models | `apex_bench.test_models` | GPT-5.5 profiles, Grok 4.3 profiles |
| Seed | not yet wired | DC2 default 10 (will be inherited at integration time) |

## Appendix B — Things explicitly out of scope for this plan

- Local PDF parsing pipeline.
- A judge alternative to Opus 4.6 (the brief is locked).
- Modifications to the vendored harness source.
- Methods other than DC2's existing five (baseline / dc_cu / dc_rs / ace / dl).
- Heldout split (400 tasks) — not public, not addressable.
