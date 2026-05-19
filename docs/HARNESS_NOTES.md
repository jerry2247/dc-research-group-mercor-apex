# Harness notes — what the vendored Mercor code actually does

> **Read this if you're asking:** "What does the upstream harness
> actually do at run time? How does grading work? What model ids does
> LiteLLM accept? What vendor bugs do we work around?"
>
> **TL;DR:** internal map of the vendored Mercor code so you can debug
> a failing run, understand a log message, or plan an upstream resync.

A reader's guide to `vendor/apex_evals/`. Useful when debugging or planning a
modification.

## End-to-end shape (upstream)

`vendor/apex_evals/examples/run_with_hf.py` is the reference runner. Per task
× per model × per run:

1. Build prompt from `prompt/response_generation_prompt.txt` with `{{Domain}}`
   and `{{Prompt}}` substituted.
2. Build `Attachment(filename, url)` per file in the task's `File Attachments`
   column. The url scheme `file://...` is supported.
3. Call `run_generation_task_async(GenerationTask(prompt, models,
   attachments))`. Internally:
   - `parser/` parses attachments via Reducto (default). The parsed text is
     concatenated into the prompt; the model never sees PDFs as binary.
   - `call_llm/litellm_client.py` dispatches the chat completion via
     LiteLLM, selecting the provider by the model id's prefix or via
     `MODEL_MAPPINGS`.
4. Call `run_grading_task_async(GradingTask(solution, rubric,
   grading_model))`. Internally:
   - The grading model (default `gemini-2.5-flash` upstream) is asked to
     binary-rate each criterion against the rubric. Output is parsed into
     per-criterion `autorating` (True/False) plus a `reason`.
   - `points_earned` / `points_possible` / `percentage_score` are computed
     from weighted criteria.

## Result schemas (relevant pieces only)

### `generation.GenerationResult`

```
results: list[dict]                # one per (model, run); has `success`, `response`, `error_message`, `model`
completed: int
failed: int
total_tokens: int
total_cost: float
```

### `grading.GradingResult`

```
points_earned: float
points_possible: int
percentage_score: float
criteria_results: list[dict]       # per criterion: criterion_key, autorating, reason
grading_error: str | None
execution_time_seconds: float
total_grading_tokens: int
total_grading_cost: float
```

## Model-id surface

`vendor/apex_evals/src/call_llm/litellm_client.py::MODEL_MAPPINGS` is the
truth on what model ids the harness will route. It includes (as of the pinned
commit):

- **OpenAI**: gpt-4, gpt-4-turbo, gpt-4o, gpt-4o-mini, gpt-3.5-turbo,
  o1-preview, o1-mini, gpt-5, gpt-5.1, gpt-5.2, gpt-5.2-pro, o3, o3-mini,
  o4-mini-deep-research-2025-06-26.
- **Anthropic**: claude-3-5-sonnet-20241022, claude-3-5-haiku-20241022,
  claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307,
  claude-4 family (claude-4, claude-4-sonnet-20250722, …, claude-opus-4-5-20251101,
  claude-sonnet-4-5-20250929, claude-opus-4-1-20250805, claude-opus-4-20250514,
  claude-sonnet-4-20250514).
- **Google**: gemini-3-pro-preview, gemini-pro, gemini-1.5-pro,
  gemini-1.5-flash, gemini-1.0-pro, gemini-2.0-flash-exp, gemini-2.5-pro,
  gemini-2.5-flash.
- **xAI**: grok-beta, grok-code-fast-1, plus 4.x / 3.x variants.

If your chosen model is not in this list, LiteLLM may still route it; the
list is a hint to LiteLLM and a sanity check, not an enforcer.

## Knobs that matter

| Setting | Where | Effect |
|---|---|---|
| `temperature` | `ModelConfig.temperature` (default 0.7) | Sampling temperature. Some reasoning models reject any value other than 1 — leave it unset in that case. |
| `max_tokens` | `ModelConfig.max_tokens` | Output budget. Distinct from input cap. |
| `max_input_tokens` | `ModelConfig.max_input_tokens` | If set, the input is trimmed via `litellm.utils.trim_messages` before send. |
| `model_configs` | `ModelConfig.model_configs` | Free-form dict forwarded to LiteLLM. Used for `reasoning_effort`, `verbosity`, etc. |
| `enable_thinking` / `thinking_tokens` | `ModelConfig.*` | Anthropic extended thinking. |
| `parsing_method` | `GenerationTask.parsing_method` (default `"reducto"`) | Pluggable; see `parser/parser_registry.py`. |
| `cache_parsed_documents` | `GenerationTask.cache_parsed_documents` (default True) | Cache PDF parses keyed by content hash. |

## Known vendor bugs (worked around in the wrapper)

### Grading prompt is loaded relative to CWD at import time

`vendor/apex_evals/src/grading/executor.py:18` declares
`DEFAULT_GRADING_PROMPT_PATH = Path("prompt/grading_prompt.txt")`. The
module-level guard at line 20–23 only assigns `DEFAULT_GRADING_PROMPT` when
that path exists *relative to the current working directory at import time*.
Any process running outside `vendor/apex_evals/` will see a logged ERROR at
import and then NameError later if `_resolve_prompt_template` is ever called
with a `None` template (line 479).

**Workaround.** Our wrapper always passes `grading_prompt_template=` on
`GradingTask`, with the template read from the vendor's own `prompt/`
directory via `apex_bench.smoke._read_grading_template`. The wrapper never
relies on the broken module-level constant.

This is a candidate upstream patch (vendor should resolve the path relative
to the package, not CWD). Until that lands, the workaround is the rule.

## Failure modes (and the right fix)

| Symptom | Most likely cause | Fix |
|---|---|---|
| `Generation failed - <provider auth error>` | wrong key in `.env` for the provider hosting the model | check `.env`, run `apex-bench info` to confirm vendor import |
| `Generation failed - context length` | task prompt + parsed PDFs exceeds `max_input_tokens` | raise the cap or set `max_input_tokens` to trim |
| `Grading returned no results` | judge call failed silently or returned malformed JSON | check `ANTHROPIC_API_KEY`; lower judge temperature; inspect raw text via verbose mode |
| `File not found: <pdf>` | dataset clone is incomplete (LFS not pulled) | re-run `make fetch-dataset` |
| `pydantic ValidationError on Rubric` | malformed rubric JSON in a specific task | upstream issue — log task_id, skip, continue |

When in doubt, read the source at `vendor/apex_evals/src/generation/executor.py`
or `vendor/apex_evals/src/grading/executor.py`. They are short and direct.
