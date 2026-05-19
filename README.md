# apex-bench

This repository is the **evaluation harness** our research group uses to
test our test-time memory mechanism — **memory subsystem**, our extension
of Dynamic Cheatsheet (Suzgun et al.) — on **Mercor's APEX-v1-extended**
benchmark.

> **Authors.** Jerry Gu, Kyleen Liao, Shurui Liu, Roshen Nair, Arnold Yang.
> **In collaboration with.** Mirac Suzgun (Stanford SAIL NLP).
> **Research focus.** Extension of Dynamic Cheatsheet to study agent test-time learning on long-horizon professional-services tasks.

**The benchmark is Mercor's, not ours.** We vendor their official
harness at a pinned commit (`vendor/apex_evals/`, commit `6cbf3f43`)
and add a thin policy/runner layer (judge selection, profile registry,
reproducible CSV output, audit telemetry) so we can evaluate our
framework against Mercor's published evaluation surface.

What lives where:

- **Mercor's harness** (vendored, untouched apart from two documented
  model-id additions): `vendor/apex_evals/`
- **Mercor's benchmark dataset**: not redistributed; fetched at setup
  time from `mercor/APEX-v1-extended` on HuggingFace
- **Our evaluation harness** (the policy + runner + audit + CSV
  schema): `src/apex_bench/`

Behavioral fidelity to Mercor's published evaluation behavior is
enforced by 70 pytest assertions and a 10-component code-level audit;
see [`docs/AUDIT.md`](docs/AUDIT.md).

> **Sister repo.** [`apex-agents-bench`](https://github.com/jerry2247/dc-research-group-mercor-apex-agents)
> targets Mercor's **APEX-Agents** benchmark — the multi-turn agent
> surface (480 tasks across 33 worlds, 9 MCP tools including code
> execution) via the Archipelago harness. Same judge, same project
> policies, different evaluation surface.

---

## TL;DR

A 5-tasks-on-Finance pilot at the cheapest tier, end-to-end, ~5 minutes:

```bash
make setup                                                 # one-time: venv + install + .env
$EDITOR .env                                               # paste OPENAI_API_KEY, XAI_API_KEY, REDUCTO_API_KEY
make fetch-dataset                                         # one-time: clone mercor/APEX-v1-extended

source .venv/bin/activate                                  # per-session
set -a; source .env; set +a                                # per-session: load keys into shell

apex-bench run --model grok-4.3-low --domain Finance --limit 5 \
    --output runs/finance-pilot/results.csv
```

The judge is fixed (`gpt-5.5`); you never specify it. The runner writes
one CSV row per completed task plus a `run_manifest.json` and a
`failures.jsonl` sidecar in the same directory. Re-running the same
`--output` resumes from where it left off — completed rows are never
re-paid.

---

## Table of contents

1. [What this is, in five lines](#1-what-this-is-in-five-lines)
2. [First-time setup](#2-first-time-setup)
3. [Running the benchmark](#3-running-the-benchmark)  ←  the section most readers want
4. [Reading the results](#4-reading-the-results)
5. [Browsing the dataset](#5-browsing-the-dataset)
6. [Troubleshooting](#6-troubleshooting)
7. [Project policies](#7-project-policies)
8. [Repo layout](#8-repo-layout)
9. [Documentation index](#9-documentation-index)
10. [Citation, license, contact](#10-citation-license-contact)

---

## 1. What this is, in five lines

- **APEX-v1-extended** is a Mercor benchmark of 100 expert-graded tasks
  (25 in each of `Consulting`, `Finance`, `Legal`, `Medicine`). Each
  task ships a prompt, 1–9 source attachments (PDF / CSV / XLSX / DOCX),
  and a per-task rubric of binary criteria.
- The model produces a single text deliverable; an LLM judge scores
  each criterion Pass/Fail. Per-task score = `# passed / # total × 100`.
- We use **Mercor's official harness** vendored at commit `6cbf3f43`
  with two documented model-id additions (gpt-5.5, grok-4.3) and no
  other changes; see [`vendor/apex_evals/PATCHES.md`](vendor/apex_evals/PATCHES.md).
- The **judge** is fixed: `gpt-5.5` at OpenAI's default
  `reasoning_effort=medium`. The **test models** are `gpt-5.5-{low,
  medium, high, xhigh}` and `grok-4.3-{low, medium, high}`. Claude on
  Bedrock is **deferred** pending upstream support.
- **One run per (task, model), always.** See [§7](#7-project-policies).

---

## 2. First-time setup

Run in order; each step verifies the previous.

### 2.1 — Install the project

```bash
git clone https://github.com/jerry2247/dc-research-group-mercor-apex.git apex-bench
cd apex-bench
make setup
```

`make setup` creates `.venv` (Python ≥ 3.11), installs the vendored
harness + the wrapper + dev tools, registers pre-commit hooks, and
copies `.env.example` to `.env`.

### 2.2 — Fill in API keys

Open `.env` and set the keys you need. Read
[`.env.example`](.env.example) for the full annotated list.

| Variable | Required for | Where to get one |
|---|---|---|
| `OPENAI_API_KEY` | the judge (`gpt-5.5`) AND `gpt-5.5-*` test profiles | platform.openai.com |
| `XAI_API_KEY` | `grok-4.3-*` test profiles | console.x.ai |
| `REDUCTO_API_KEY` | **every run** — all 100 tasks have attachments | platform.reducto.ai |

> **Whitespace matters.** `python-dotenv` does not strip whitespace.
> `OPENAI_API_KEY= sk-...` (note the space) is silently invalid.

Not yet needed (deferred): `ANTHROPIC_API_KEY`, `AWS_*` (Claude on
Bedrock), `GOOGLE_API_KEY` (project judge is gpt-5.5, not Gemini).

### 2.3 — Fetch the dataset

```bash
make fetch-dataset
```

Clones `mercor/APEX-v1-extended` into `data/APEX-v1-extended/` (~37 MB:
a 100-row CSV plus 176 attachment files). The CSV the harness reads is
`data/APEX-v1-extended/data/train.csv`. Verified row count uses
`csv.DictReader` (multi-line JSON cells make `wc -l` misleading).

### 2.4 — Activate the venv and load `.env` (every new terminal session)

```bash
source .venv/bin/activate
set -a; source .env; set +a
```

Activation puts the `apex-bench` command on `PATH`; the second line
exports the API keys into your shell so LiteLLM and Reducto see them.
*The runner also auto-loads `.env` via `python-dotenv` at preflight,
so the second line is belt-and-suspenders — but harmless.*

### 2.5 — Verify everything wires

```bash
apex-bench info                # paths + judge + vendor probe
apex-bench catalog             # writes data/catalog.json
apex-bench models              # 7 active test-model profiles
make check                     # 70 tests + ruff + mypy
```

If any of those fail, fix the failure before spending budget.

---

## 3. Running the benchmark

### 3.1 — Recommended flow: pilot first, then scale

To verify the full pipeline before committing to a full domain, run
**one task first** with the output path you want for the eventual
full domain. The runner resumes by `task_id` on the same CSV, so the
pilot row is reused (never re-paid) when you scale.

```bash
# Step 1 — one-task pilot (~$0.50–$2 depending on profile)
apex-bench run --model grok-4.3-high --domain Finance --limit 1 \
    --output runs/finance-grok43high/results.csv

# Inspect: confirm the CSV has 1 completed row, a non-zero score, and
# the per-criterion judge rationales in <model_key>_1_score_summary.

# Step 2 — finish the domain (24 remaining tasks)
apex-bench run --model grok-4.3-high --domain Finance \
    --output runs/finance-grok43high/results.csv
```

### 3.2 — Command shape

```
apex-bench run --model <profile> [--domain <d>] [--limit <N>] [--output <path>]
```

| Flag | Values | Notes |
|---|---|---|
| `--model` | a profile from `apex-bench models` | required |
| `--domain` | `Consulting` / `Finance` / `Legal` / `Medicine` | optional; case-sensitive |
| `--limit` | integer 1–100 | optional; each domain has exactly 25 tasks |
| `--task-ids` | comma-separated ids | overrides `--domain` and `--limit` |
| `--start-index` | integer | skip the first N tasks (within filter) |
| `--output` | path | default: `runs/<UTC>__<profile>__<scope>/results.csv` |

The judge is **fixed**: `gpt-5.5` at OpenAI's default
`reasoning_effort=medium`. You do not configure it.

### 3.3 — Test-model profiles

`apex-bench models` lists the current set:

| Family | Profiles | Provider notes |
|---|---|---|
| OpenAI GPT-5.5 | `gpt-5.5-low`, `gpt-5.5-medium`, `gpt-5.5-high`, `gpt-5.5-xhigh` | `max_tokens=127_997`, `max_input_tokens=272_000`, `verbosity=medium`. `temperature=1.0` (OpenAI's reasoning-model default; the vendored Pydantic `ModelConfig` would otherwise inject `0.7`, which the API rejects). |
| xAI Grok 4.3 | `grok-4.3-low`, `grok-4.3-medium`, `grok-4.3-high` | `max_tokens=256_000`, `max_input_tokens=256_000`, `temperature=0.8`. Matches the upstream `grok-4-0709` pattern. |
| Anthropic Claude 4.6 (Bedrock) | **deferred** | upstream has no Bedrock routing yet; see [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) |

### 3.4 — More example invocations

```bash
# Full Finance domain (25 tasks) at GPT-5.5 high
apex-bench run --model gpt-5.5-high --domain Finance

# 5-task pilot on Consulting at the cheapest tier
apex-bench run --model grok-4.3-low --domain Consulting --limit 5

# Re-run only specific task ids
apex-bench run --model gpt-5.5-medium --task-ids 1588,2108,2120

# Entire public split (100 tasks)
apex-bench run --model grok-4.3-medium
```

### 3.5 — Output, resume, and provenance

A run produces a directory containing:

```
runs/<UTC-timestamp>__<profile>__<scope>/
├── results.csv          one row per completed task
├── run_manifest.json    schema-versioned reproducibility manifest
└── failures.jsonl       UTC-timestamped record of every skipped task
```

The `run_manifest.json` captures: `apex-bench` version, git HEAD + dirty
state, vendor commit SHA, response-generation + grading template
SHA256s, dataset CSV SHA256, profile config, judge config (with
effective vs requested temperature), output paths, and per-run progress
counters. Written on start, on completion, and on preflight failure.

The `failures.jsonl` file captures every task that was selected but
not written (preflight failures, attachment-integrity refusals,
generation failures, per-criterion grading failures). One JSON object
per line; never overwritten.

To resume, re-run the same `apex-bench run` command with the same
`--output`. The runner reads existing rows and skips `task_id`s whose
`status == "completed"`. Default output paths include a UTC timestamp
so you must use `--output` explicitly if you intend to resume.

---

## 4. Reading the results

Each completed task writes one row to `results.csv`:

| Column | Meaning |
|---|---|
| `task_id` | dataset task id (string) |
| `domain` | `Consulting` / `Finance` / `Legal` / `Medicine` |
| `status` | `completed` (any failed task is logged to `failures.jsonl` instead) |
| `<model_key>_1_response` | the full deliverable text the model produced |
| `<model_key>_1_score` | percentage 0–100 |
| `<model_key>_1_score_summary` | rubric JSON with `autorating` (Pass/Fail) and `reason` per criterion |
| `generation_chars`, `wall_time_seconds` | response length + end-to-end time |
| `attachments_expected`, `attachments_sent`, `parsed_attachment_chars` | attachment audit: what the task declared, what we sent, how much text reached the model |
| `final_prompt_chars`, `final_prompt_sha256` | bit-level fingerprint of what reached the model |
| `agent_input_tokens`, `agent_output_tokens`, `agent_tokens` | provider-reported usage for the **test model only** |
| `agent_usage_available`, `agent_usage_source`, `agent_usage_consistent` | usage health checks |
| `judge_model`, `test_model_profile`, `test_model_id` | provenance |

At the end of a run the CLI prints a summary table: tasks completed,
overall mean %, per-domain mean %, CSV path.

> **Cost is intentionally not in the CSV.** The exposed vendor cost is
> a LiteLLM price-table estimate, not provider-billed. Token columns
> are sufficient for downstream cost reconstruction.
>
> **Judge tokens are intentionally not in the CSV.** They are shared
> evaluation overhead, not a model-output metric for cross-method
> comparisons.

---

## 5. Browsing the dataset

```bash
apex-bench list                                # all 100 tasks, one row each
apex-bench list --domain Finance               # one domain
apex-bench list -d Finance -d Medicine -n 5    # two domains, first 5 each
apex-bench list --domain Legal --full-prompt   # full prompts (long)
apex-bench show 1588                           # one task in full
apex-bench catalog                             # JSON summary to data/catalog.json
```

Per-domain task characterization with the full 100-task index lives in
[`docs/BENCHMARK_STRUCTURE.md`](docs/BENCHMARK_STRUCTURE.md).

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `command not found: apex-bench` | venv not activated | `source .venv/bin/activate` |
| `Missing required environment variable(s): ...` | preflight detected a missing key | set the key in `.env`; `set -a; source .env; set +a` |
| `Reducto error – 401 AUTH_ERROR` | bad / revoked Reducto key | re-issue at platform.reducto.ai |
| `Model <id> is not supported` | profile uses a model not in the vendor's `MODEL_MAPPINGS` | check `apex-bench models`; new models require a vendor patch with `# vendored-patch:` marker + `PATCHES.md` entry |
| `OpenAI error: invalid_api_key` | key has whitespace or was revoked | `OPENAI_API_KEY=sk-...` with no spaces |
| `AccessDeniedException` from Bedrock | a Claude profile was attempted | Claude is deferred; use `gpt-5.5-*` or `grok-4.3-*` |
| Run completes but a row is missing | task failed and was logged | open `<output-stem>.failures.jsonl` for the exact reason |
| `litellm.BadRequestError: Unsupported value: 'temperature'` | profile sent a non-default temperature to a reasoning model | should not happen with the bundled profiles; if it does, file an issue with `apex-bench info` output |

If something is genuinely broken in the harness, file an issue with
the failing task's `failures.jsonl` entry and `apex-bench info` output.

---

## 7. Project policies

These are NOT knobs. Each is enforced in code and protected by a test.

| Policy | Rationale | Enforced at |
|---|---|---|
| **1 run per (task, model)** | Trades leaderboard-parity (8 runs) for being able to compare more methods within budget. Variance signal comes from per-domain (n=25) and per-criterion (~250/cell) bins. | `apex_bench.config.RUNS_PER_TASK`; `tests/test_imports.py` |
| **Judge = `gpt-5.5`** at OpenAI default `reasoning_effort=medium` | One judge across every run keeps cross-model comparisons well-defined. Not Gemini. | `apex_bench.config.DEFAULT_JUDGE_MODEL`; `tests/test_imports.py` |
| **Judge `temperature=1.0`** | OpenAI reasoning models reject any other temperature. `_safe_judge_temperature` coerces non-1.0 values with a warning. | `apex_bench.runner._safe_judge_temperature`; `tests/test_fidelity.py` |
| **Reducto for attachments** | The parser the upstream harness ships; used as-is. | structural — vendor enforces |
| **No tools / no code execution / no web search / no thinking** on the eval surface | Upstream `run_with_hf.py` enables none of these for APEX. | `tests/test_fidelity.py::test_no_profile_uses_disallowed_capabilities` |
| **No vendor source modifications beyond documented patches** | Two MODEL_MAPPINGS additions for `gpt-5.5` + `grok-4.3`. Each carries a `# vendored-patch:` marker, is recorded in `PATCHES.md`, and is covered by a regression test. | `vendor/apex_evals/PATCHES.md`; `tests/test_fidelity.py` |
| **Refuse to score on corrupt input** | The runner skips (with a `failures.jsonl` entry) if any expected attachment is missing on disk, the vendor's attachment block is absent from the final prompt, a per-attachment section is missing, or any criterion's `grading_success` is False. Partial scoring would inflate apparent quality. | `apex_bench.runner._process_task`; `tests/test_runner.py` |

Full discussion: [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md).
Line-by-line fidelity audit: [`docs/AUDIT.md`](docs/AUDIT.md).

---

## 8. Repo layout

```
apex-bench/
├── README.md                       <- this file
├── pyproject.toml                  PEP 621; ruff / mypy / pytest config
├── Makefile                        `make help` lists every target
├── .env.example                    template for API keys (copied to .env on setup)
├── docs/                           project + benchmark documentation
├── scripts/                        setup.sh, fetch_dataset.sh, smoke_test.sh
├── src/apex_bench/                 wrapper (CLI, config, runner, dataset, profiles)
├── vendor/apex_evals/              pristine Mercor harness + 3 provenance files
├── tests/                          70 tests; all pass on a clean tree
├── data/                           gitignored — dataset + catalog artifacts
└── runs/                           gitignored — per-run CSV + manifest + failures
```

Why the wrapper is a separate package: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 9. Documentation index

Each doc answers a specific question. Read in order if you're new; jump
to the one that matches your question if not.

| Doc | What it answers |
|---|---|
| [`docs/INDEX.md`](docs/INDEX.md) | full doc index with section pointers |
| [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) | phased project plan with budget + verification gates |
| [`docs/AUDIT.md`](docs/AUDIT.md) | line-by-line confirmation we match Mercor's harness |
| [`docs/BENCHMARK_STRUCTURE.md`](docs/BENCHMARK_STRUCTURE.md) | what the 100 APEX tasks look like, per-domain breakdown, full per-task index |
| [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) | the 1 run/task policy, dataset license, what gets recorded per run |
| [`docs/HARNESS_NOTES.md`](docs/HARNESS_NOTES.md) | how the vendored harness works internally + known vendor quirks |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | wrapper-vs-vendor split + diff policy |
| [`vendor/apex_evals/UPSTREAM.md`](vendor/apex_evals/UPSTREAM.md) | upstream commit SHA, when we vendored, resync procedure |
| [`vendor/apex_evals/PATCHES.md`](vendor/apex_evals/PATCHES.md) | every vendor-source edit, with diff and rationale |

---

## 10. Citation, license, contact

**Citation.** Cite the underlying benchmark first — it is Mercor's
work, not ours:

> Vidgen, B. et al. *APEX-v1-extended.* 2026. arXiv:2509.25721.

If you build on this evaluation harness specifically (the wrapper, the
profile registry, the audit schema), a suggested form is:

> Gu, J., Liao, K., Liu, S., Nair, R., Yang, A., in collaboration with
> M. Suzgun (Stanford SAIL NLP). *apex-bench: evaluation harness for
> memory subsystem on Mercor's APEX-v1-extended.* 2026.
> https://github.com/jerry2247/dc-research-group-mercor-apex

The research contribution under evaluation here is **memory subsystem**
(our group's extension of Dynamic Cheatsheet); this repository is the
engineering harness that lets us evaluate it reproducibly against
Mercor's published benchmark.

**License.** This repository is MIT (see `LICENSE`). The vendored
harness is CC-BY-4.0 (see `vendor/apex_evals/LICENSE_UPSTREAM`). The
APEX-v1-extended dataset is not redistributed; it is fetched at setup
time under its own CC-BY-4.0 + eval-only terms (see
`docs/REPRODUCIBILITY.md`).

**Contact.** File an issue on the GitHub repository. For substantive
research questions, contact the authors directly.

---

## Related

- [`apex-agents-bench`](https://github.com/jerry2247/dc-research-group-mercor-apex-agents)
  — sister repo targeting the **APEX-Agents** benchmark (multi-turn
  agent surface, vendored Archipelago harness, same `gpt-5.5` judge).
  Use that repo for the agentic benchmark; use this repo for the
  single-shot text deliverable benchmark.
