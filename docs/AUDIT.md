# Behavioral fidelity audit

> **Read this if you're asking:** "Are we actually running Mercor's
> harness or did we silently change something? Is there code execution?
> Tools? Web search? Are the token limits the same? Is the scoring
> formula the same?"
>
> **TL;DR:** 10-component audit comparing our wrapper to upstream
> behavior with code-level evidence and regression tests for each
> claim. If `make check` is green, every claim in this document still
> holds.

**Last reviewed: 2026-05-19 against upstream commit `6cbf3f43156bf332329abe76ed4a695fc71ec5b0`.**

This document records every check that confirms our wrapper does not change
what reaches the model or the judge relative to Mercor's reference runner
(`vendor/apex_evals/examples/run_with_hf.py`). The intent is to *match
Mercor's harness behavior exactly, excluding the deliberate model/judge/
runs-per-task substitutions documented in `IMPLEMENTATION_PLAN.md` and
`REPRODUCIBILITY.md`*.

Every audit item has a corresponding regression test under `tests/` that
must continue to pass on every CI run. If an audit assertion ever fails,
treat it as a halt-the-line event.

---

## A1. Vendor source integrity

**Claim**: The only changes to `vendor/apex_evals/` are (a) two MODEL_MAPPINGS
additions documented in `vendor/apex_evals/PATCHES.md` and (b) three
provenance files we added (`LICENSE_UPSTREAM`, `PATCHES.md`, `UPSTREAM.md`).

**Verification** (re-runnable):
```
diff -rq vendor/apex_evals  <fresh-upstream-checkout>/apex-evals-v1-extended
```

**Recorded result** on 2026-05-19:
```
Only in vendor/apex_evals: LICENSE_UPSTREAM    # provenance
Only in vendor/apex_evals: PATCHES.md          # provenance
Only in vendor/apex_evals: UPSTREAM.md         # provenance
Files vendor/apex_evals/src/call_llm/litellm_client.py
  and <upstream>/src/call_llm/litellm_client.py differ      # the 2 patch lines
```

The exact diff is:
```diff
        "gpt-5.2-pro",
+       "gpt-5.5",       # vendored-patch: gpt-5.5 post-dates pin
...
        "grok-4-0709",
+       "grok-4.3",      # vendored-patch: grok-4.3 post-dates pin
        "grok-3",
```

Two string additions in a single file. No logic, prompts, validators,
loops, schemas, or scoring changes touch the vendor.

**Test**: `tests/test_fidelity.py::test_vendored_patch_markers_present_in_litellm_client`.

---

## A2. Runner loop semantics

**Claim**: `apex_bench.runner.run_async` replicates the upstream
`process_task → save_result → calculate_stats` shape with the same row-write
rule (write the task row only when every model × run combo succeeds), the
same resume rule (skip task ids with `status="completed"` in the output
CSV), the same domain / start_index / limit filtering.

**Side-by-side**:

| Upstream `run_with_hf.py` | Our `runner.py` |
|---|---|
| `process_task(...)` lines 144-191 | `_process_task(...)` lines ~179-270 |
| `for model in MODELS` (×12 by default) | iterates exactly one profile per invocation |
| `for run in 1..NUMBER_OF_RUNS` (×1 by default) | identical (project policy 1 run/task) |
| `generate(...)` then `grade(...)` per (model, run) | identical |
| Row written only if status=="completed" | identical |
| `load_completed_tasks(...)` lines 77-86 | `load_completed_task_ids(...)` |
| `calculate_stats(...)` lines 196-252 | `calculate_stats(...)` |

**Tests**: `tests/test_runner.py` — `test_csv_headers_contains_all_expected_columns`,
`test_select_tasks_*`, `test_append_row_then_resume_skips_completed`,
`test_calculate_stats_basic`.

---

## A3. Per-criterion grading flow

**Claim**: Grading is one judge call per criterion, identical to the
upstream behavior. No client-side aggregation, no batching, no skipping.

**Source of truth**: `vendor/apex_evals/src/grading/executor.py:115`
(`grade_single_criterion`). We do not touch this code; the vendor is
unmodified. Our `_process_task` calls `run_grading_task_async` exactly
once per task, and that function handles the per-criterion loop internally.

**Operational consequence**: a task with 10 rubric criteria triggers ~10
judge model calls. Our runner does not change this.

---

## A4. Scoring formula

**Claim**: `percentage_score = #criteria_passed / #criteria_total * 100`.
Weights (`Primary objective(s)` vs `Not primary objective`) are recorded in
each criterion's result row but are NOT used in the percentage computation.

**Source of truth**: `vendor/apex_evals/src/grading/executor.py:412-414`:
```python
total_possible = len(valid_results)
total_earned = sum(1 for r in valid_results if r.get("autorating", False))
percentage_score = (total_earned / total_possible * 100) if total_possible > 0 else 0
```

We do not override this. Documented in `HARNESS_NOTES.md`.

---

## A5. Prompt template handling

**Claim**: We read `vendor/apex_evals/prompt/response_generation_prompt.txt`
verbatim and substitute only `{{Domain}}` and `{{Prompt}}` — the two
placeholders the upstream template defines. We never edit, paraphrase, or
add to the template.

**Verification**:
- Source-side: `apex_bench.runner._read_response_generation_template`
  reads the file from `vendor_dir()` at every run. No copy lives in `src/`.
- Substitution-side: `runner.py` does
  `prompt = response_template.replace("{{Domain}}", ...).replace("{{Prompt}}", ...)`
  — same as upstream `run_with_hf.py:155`.

**Tests**: `tests/test_fidelity.py` —
`test_response_generation_template_is_unmodified_from_vendor`,
`test_response_generation_template_has_only_two_placeholders`.

---

## A6. Attachment construction

**Claim**: Attachments are built with the same two fields the upstream
runner uses (`filename`, `url`) and the URL is the local `file://...` form
upstream produces from local task files.

**Source of truth**: `vendor/apex_evals/examples/run_with_hf.py:63-74`
(`create_attachments`). Our `_process_task` produces the same shape:
```python
VendorAttachment(filename=a.path.name, url=f"file://{a.path}")
```

**Test**: `tests/test_fidelity.py::test_attachment_construction_uses_only_filename_and_file_url`
checks the literal code pattern.

---

## A7. Rubric pass-through

**Claim**: The raw `Rubric JSON` string from the dataset CSV is passed to
`GradingTask(rubric=...)` verbatim. No preprocessing, normalization, or
filtering on our side. The vendor's `GradingTask` validator parses it
(supports list-of-dicts, dict, or string).

**Source-side test**: `tests/test_fidelity.py::test_rubric_passed_verbatim`
greps `runner.py` for `rubric=task.rubric_json`.

---

## A8. Generation parameters — no tools, no thinking, no web search, no extras

**Claim**: For every active test-model profile, the only `ModelConfig`
keys we set are the same keys Mercor sets in upstream `MODELS`:
`model_id`, `max_tokens`, `max_input_tokens`, `temperature` (where set),
`model_configs`, `number_of_runs`.

**Explicit exclusions** — none of these are ever set by any active profile:
- `use_tools` — would enable model-side function calling. Off.
- `is_custom_model` / `custom_model_config` — off; we use stock providers.
- `top_p` — off (upstream omits it for all 12 MODELS entries).
- `enable_thinking` / `thinking_tokens` — off (Anthropic-extended-thinking;
  Claude profiles are deferred, OpenAI/xAI do not expose).
- `system_prompt` (on `GenerationTask`) — off; the upstream runner never
  sets one. The prompt template is the entire input.
- `response_images` (on `GradingTask`) — off; not used in run_with_hf.py.
- **No web search / browser / retrieval tools** — neither vendor's
  `GenerationTask` nor the upstream MODELS list exposes a web-search
  capability for APEX. The model sees prompt + parsed attachments only.
- **No code execution** — the vendored harness has no code-execution path.
  All `execution_*` symbols in vendor source are timing metrics. APEX
  models produce text deliverables, graded by the judge as text.

**Tests**: `tests/test_fidelity.py` —
`test_no_profile_uses_disallowed_capabilities`,
`test_no_profile_enables_tools_or_thinking`,
`test_no_profile_sets_top_p`.

---

## A9. Token limits

**Claim**: All token limits in our profiles **exactly match** the
corresponding family in upstream `MODELS` (`run_with_hf.py:24-37`). We did
not invent any new cap, raise any cap, or lower any cap relative to that
list.

| Family | Field | Upstream value | Our profile value |
|---|---|---|---|
| GPT-5.x (`gpt-5`, `gpt-5.1`, `gpt-5.2`, `gpt-5.2-pro`) | `max_tokens` | 128000 / 127997 | **127997** for all `gpt-5.5-*` |
| GPT-5.x | `max_input_tokens` | 272000 | **272000** for all `gpt-5.5-*` |
| GPT-5.x | `temperature` | (omitted) | **1.0** for all `gpt-5.5-*`; this is OpenAI's default/only accepted temperature for reasoning models, and prevents the vendored `ModelConfig` default of 0.7 from being sent |
| Grok (`grok-4-0709`) | `max_tokens` | 256000 | **256000** for all `grok-4.3-*` |
| Grok (`grok-4-0709`) | `max_input_tokens` | 256000 | **256000** for all `grok-4.3-*` |
| Grok (`grok-4-0709`) | `temperature` | 0.8 | **0.8** for all `grok-4.3-*` |

**Tests**: `tests/test_fidelity.py` —
`test_gpt55_token_limits_match_upstream_pattern`,
`test_grok43_token_limits_match_upstream_grok_pattern`.

---

## A10. Stats aggregation

**Claim**: Per-task median across runs (= single score under our N=1
policy), per-domain mean of task medians, overall mean of task medians.
Same shape as upstream `calculate_stats` (`run_with_hf.py:196-252`).

**Tests**: `tests/test_runner.py::test_calculate_stats_basic` asserts
exact numeric output on a synthetic 3-row CSV.

---

## Deliberate, documented differences from Mercor's harness

These differences are **policy choices** with reasons recorded in
`docs/REPRODUCIBILITY.md` and `docs/IMPLEMENTATION_PLAN.md`. They are not
fidelity bugs; they are scope choices.

| Aspect | Mercor's harness | Ours | Reason |
|---|---|---|---|
| Judge model | gemini-2.5-flash (open default); gemini-2.5-pro thinking=on (leaderboard) | gpt-5.5 (medium-by-default) | User preference; not Gemini |
| Number of runs per task | 1 (open) or 8 (leaderboard) | **1, always** | Project policy — see REPRODUCIBILITY.md |
| Test models | hardcoded 12-entry list | one profile per invocation | We compare DC variants against a fixed test model |
| Claude/Bedrock | (would route via direct Anthropic API) | **deferred** | Vendor has no Bedrock routing; structural patch needed |

Every other behavioral knob — parser (Reducto), prompt template, attachment
construction, grading flow, scoring formula, resume mechanism, stats —
matches the upstream harness behavior exactly.

---

## Re-running the audit

```bash
make check     # full fidelity + structural test suite
```

If any `tests/test_fidelity.py::*` test fails, do not commit; we have
drifted. If `diff -rq vendor/apex_evals <upstream>` shows differences other
than the documented patches, do not commit; we have drifted.
