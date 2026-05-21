# TRACE — apex-bench

**TRACE** (Tool-augmented Reasoning via Atomic Cheatsheet Editing;
Liao, Nair, Yang, Stanford CS224N) is a test-time-learning subsystem
layered on the Mercor APEX-v1-extended single-shot prose benchmark.
Unlike the Dynamic Ledger, TRACE *uses* the ground-truth correctness
bit — intentionally, per the paper.

We follow the paper's pipeline faithfully with these scoped
adaptations to the single-shot prose-deliverable setting:

1. **OpenAI embeddings** (`text-embedding-3-large`).
2. **No bullet length cap** — the paper caps atomic bullets at ~600
   characters; we let bullets fit the analytical workflows the
   benchmark surfaces.
3. **No SFT step** — the paper's optional supervised-fine-tuning
   stage is omitted.
4. **One TRACE framework** — we ship the GT-using reflector + curator
   pair the paper describes; no ablation variants.
5. **Same model for reflector + curator + generator** — the reflector
   and curator both run on the active `TestModelProfile`'s `model_id`
   with the same `model_configs` (reasoning effort, etc.). Only the
   **judge** model is fixed (gpt-5.5 medium).
6. **Pass@1 threshold** — TRACE's GT bit is `True` iff
   `grade_result.percentage_score >= 99.0` (matches the apex-bench
   "Pass@1" criterion: all rubric items scored).

TRACE is **off by default**. With `--trace` off the runner takes the
baseline code path; CSV schema is byte-identical to the no-TRACE
shape. `--trace` and `--dynamic-ledger` are mutually exclusive.

## Pipeline

```
   ┌──────────┐    ┌────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐    ┌──────────┐
   │ RETRIEVE │───▶│ INJECT │───▶│ GENERATE │───▶│  CITE   │───▶│  REFLECT │───▶│  CURATE  │
   │ dual k=5 │    │ user   │    │ vendor   │    │ parse + │    │ same     │    │ same     │
   │ cosine   │    │ prompt │    │ Generat- │    │ strip   │    │ model    │    │ model    │
   │          │    │        │    │ ionTask  │    │ tail    │    │          │    │          │
   └──────────┘    └────────┘    └──────────┘    └─────────┘    └──────────┘    └─────┬────┘
        ▲                                              │             ▲                 │
        │                                              ▼             │                 │
        │                                          ┌────────┐   gt_bit                 │
        │                                          │ GRADE  │   (percentage_score      │
        │                                          │ vendor │    >= 99.0)              │
        │                                          │ judge  │ ────────┘                │
        │                                          └────────┘                          │
        │                                                                              │
        └─────────────────────────  L_{i+1}  ◀─────────────────────────────────────────┘
```

Per task: **two** LLM calls into the TRACE pipeline (reflector, then
curator). Both calls receive the boolean `gt_correct`. Neither sees
the rubric text, per-criterion verdicts, expected answer, or judge
rationale.

## Bullet shape

```python
class Bullet(BaseModel):
    bullet_id: str                              # "bullet-N"
    section: str
    content: str                               # free-form, no length cap
    source_problem: str
    active: bool = True
    helpful: int = 0                           # cited on a case judged correct
    harmful: int = 0                           # cited on a case judged incorrect
    usage: int = 0                             # total cites
    created: int
    updated: int
    content_embedding: list[float]             # text-embedding-3-large; 3072d
    source_problem_embedding: list[float]
```

Counters condition reflector + curator behavior — a bullet with high
`harmful` and low `helpful` is a deletion candidate; a bullet with
high `helpful` is preserved or sharpened. CONSOLIDATE preserves
counters by summing across sources.

## Hooks into `runner._process_task`

| Hook | When | Effect |
|------|------|--------|
| **A. retrieve + augment** | before vendor template substitution | dual top-k retrieval (k=5 per axis); render cheatsheet block + citation instruction; the augmented string is substituted into the vendor template's `{{Prompt}}` slot; `{{Domain}}` unchanged. |
| **B. cite + strip** | after generator returns | parse `<citations>[bullet-...]</citations>` from the last line of the prose response; pass stripped prose to the grader; retain the original prose for the reflector + curator. |
| **C. counters + reflect + curate + apply + persist** | after grading completes | bump cited bullets' counters per `gt_correct`; call reflector with `(cheatsheet, problem, response, cited_bullets, gt_correct)` → emits `<reflector_proposals>`; call curator with the above plus the reflector's proposals → emits `<cheatsheet_updates>`; apply `DELETE → CONSOLIDATE → UPDATE → CREATE`; persist per-domain snapshot. |

All three hooks are guarded by `if trace_runtime is not None`. With
TRACE off they do not run; the CSV schema is the baseline shape.

## Op contract

Both reflector and curator emit a JSON array of operations, identical
schema:

| Op           | Args                                                  | Effect                                       |
|--------------|-------------------------------------------------------|----------------------------------------------|
| `CREATE`     | `section, content, source_problem`                    | New bullet; subject to create-time dedup     |
| `UPDATE`     | `bullet_id, content`                                  | Replace + re-embed; bump `updated`           |
| `DELETE`     | `bullet_id`                                           | Soft-delete                                  |
| `CONSOLIDATE`| `bullet_ids[], section, content, source_problem`      | Soft-delete sources; mint merged bullet (counters summed) |
| `NO_OP`      | `reason` (optional)                                   | Explicit "nothing to do this turn"          |

Reflector wraps output in `<reflector_proposals>...`; curator wraps
output in `<cheatsheet_updates>...`. Hallucinated `bullet_id`s are
dropped silently.

## Configuration

```python
@dataclass(frozen=True)
class TraceConfig:
    enabled: bool = False
    embedding_model: str = "text-embedding-3-large"
    embedding_dim: int = 3072
    top_k_per_axis: int = 5

    # Filled from the active TestModelProfile by the runner
    reflector_model: str | None = None
    curator_model: str | None = None
    model_extra_args: dict | None = None

    reflector_temperature: float = 1.0
    curator_temperature: float = 1.0
    reflector_max_tokens: int = 16000
    curator_max_tokens: int = 16000
    reflector_timeout_seconds: int = 1800
    curator_timeout_seconds: int = 1800

    create_time_similarity_threshold: float = 0.85
```

CLI flags: `--trace / --no-trace`, `--trace-top-k`. Mutually exclusive
with `--dynamic-ledger`.

## Per-domain isolation

Each domain (Finance, Legal, Consulting, Medicine) has its own TRACE
cheatsheet and snapshot history under
`runs/<run>/trace/<Domain>/snapshot_NNNN.json`.

## CSV columns added when TRACE is on

```
trace_enabled
trace_snapshot_index_before
retrieved_bullet_count
retrieved_bullet_ids                  JSON list
citations_present                     bool
citations_count                       int
citations_malformed_count             int
trailing_chars_after_citations        int
gt_correct_bit                        bool  (percentage_score >= 99.0)
reflector_proposal_count              int
curator_create_count
curator_create_blocked_count
curator_update_count
curator_delete_count
curator_consolidate_count
curator_no_op                         bool
trace_active_bullet_count_after
trace_total_bullet_count_after
trace_total_active_chars_after
reflector_prompt_tokens
reflector_completion_tokens
reflector_wall_seconds
curator_prompt_tokens
curator_completion_tokens
curator_wall_seconds
```

## Tests

```
tests/test_trace_bullet.py                 Bullet + TraceLedger + counters
tests/test_trace_curator_reflector.py      parsers + apply_ops + CONSOLIDATE counter sum
tests/test_trace_injector_citations.py     render + augment + extract/strip citations
tests/test_trace_fidelity.py               load-bearing signature, CSV, prompt invariants
```

## Run it

```bash
apex-bench run \
    --model grok-4.3-high \
    --domain Finance --limit 5 \
    --trace \
    --output runs/trace-on/results.csv
```

## Citation

This subsystem implements the **TRACE** method (Tool-augmented
Reasoning via Atomic Cheatsheet Editing) by Liao, Nair, and Yang,
published as a Stanford CS224N final project. We follow the paper's
reflector + curator pipeline with the adaptations enumerated above
(OpenAI embeddings, no bullet length cap, no SFT step, same model for
reflector + curator + generator, GT bit = `percentage_score >= 99.0`).

```bibtex
@misc{liao2025trace,
  title  = {TRACE: Tool-augmented Reasoning via Atomic Cheatsheet Editing},
  author = {Liao, ... and Nair, ... and Yang, ...},
  year   = {2025},
  note   = {Stanford CS224N project},
  url    = {https://web.stanford.edu/class/cs224n/project.html}
}
```
