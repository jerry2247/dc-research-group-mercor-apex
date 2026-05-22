# Dynamic Ledger — apex-bench

Test-time learning subsystem layered on the Mercor APEX-v1-extended
single-shot prose benchmark. Adapts the **Dynamic Ledger** variant of
Suzgun et al.'s *Dynamic Cheatsheet* to a single-turn prose deliverable
on a rubric-graded benchmark. The Ledger has **no ground-truth signal**
at any point — the curator never sees the criterion text, never sees
the judge's per-criterion verdict, never sees the expected answer.

## Design at a glance

```
   ┌──────────┐     ┌────────┐     ┌──────────────┐     ┌───────────┐
   │ RETRIEVE │────▶│ INJECT │────▶│   GENERATE   │────▶│  CURATE   │
   │ dual k=5 │     │ user   │     │ vendor       │     │ same model│
   │ cosine   │     │ prompt │     │ GenerationT. │     │ as agent  │
   └──────────┘     └────────┘     └──────────────┘     └─────┬─────┘
        ▲                                                     │
        │                                                     │
        └─────────────  L_{i+1}  ◀──────────────────────────  ┘
```

Per task, exactly one curator LLM call. No grader-in-the-loop. No
outcome bit threading. No citations. No response rewriting.

The Ledger is **off by default**. With `--dynamic-ledger` off, the
pipeline is byte-identical to the baseline runner — pinned by
`test_dynamic_ledger_off_csv_schema_unchanged`.

## Entry shape

```python
class Entry(BaseModel):
    entry_id: str                              # "entry-N" — monotonic per domain
    section: str                               # short categorical label
    content: str                               # free-form playbook text, no length cap
    source_problem: str                        # curator's paraphrase — second retrieval key
    active: bool = True                        # soft-delete flag
    created: int                               # 0-indexed per-domain task ordinal
    updated: int                               # last edit ordinal
    content_embedding: list[float]             # text-embedding-3-large; 3072d
    source_problem_embedding: list[float]      # text-embedding-3-large; 3072d
```

No counters (no helpful / harmful / usage). The Dynamic Ledger has no
GT, so quality signals from grading cannot reach the curator.

## Pipeline

### Hook A · retrieve + inject

Active entries in the task's domain are dual-retrieved against the
task prompt:

- `top_c = top-k(content_embedding cosine, k=5)`
- `top_p = top-k(source_problem_embedding cosine, k=5)`
- `B_i   = dedup-by-entry_id(top_p + top_c)`   (source-problem axis first)

The unioned subset is rendered into a `## Reference notes from prior
cases in this area` block and prepended to the task prompt **before**
the vendor template substitution (`{{Prompt}}` slot). The
`{{Domain}}` slot is unchanged.

### Generate

The vendor's `generation.run_generation_task_async` runs as-is. **No
changes** to vendor code. The injected prefix is just extra context
in the user-prompt portion of the rendered template.

### Hook B · curate

After grading, the curator runs **once**. Inputs:

- the per-domain Dynamic Ledger (active entries serialized as JSON for
  the curator's `<playbook>` block),
- the verbatim task prompt (WITHOUT the strategies-block injection),
- the deliverable prose, as the model generated it.

**Forbidden in the curator signature:** `criteria`, `score`, `scores`,
`gt_bit`, `gt_correct_bit`, `expected_answer`, `gold_response`,
`judge_rationale`, `verifier_result`, `final_score`. Pinned by the
load-bearing fidelity test `test_curator_signature_has_no_outcome`.

The curator emits a single `<memory_updates>` XML block holding a JSON
array of ops:

| Op       | Args                                | Effect                                  |
|----------|-------------------------------------|-----------------------------------------|
| `CREATE` | `section, content, source_problem`  | New entry; subject to create-time dedup |
| `UPDATE` | `entry_id, content`                 | Replace + re-embed; bump `updated`      |
| `DELETE` | `entry_id`                          | Soft-delete                             |

The three operations match the Dynamic Ledger approach in the
**Dynamic Cheatsheet 2.0** codebase (Jerry / Sabrina Yen-Ko / Shurui; mentor:
Mirac Suzgun). No `CONSOLIDATE`, no `NO_OP` — neither exists in the DL
approach.

Op application order: `DELETE → UPDATE → CREATE`. Hallucinated
`entry_id`s are dropped silently. Any op outside `{CREATE, UPDATE,
DELETE}` is parsed and dropped — the curator's wider prompt cannot
introduce ops not in this set.

### Dedup

Create-time only, against the **retrieved subset** `B_i`. Candidate
content is embedded, then compared to each retrieved entry's
`content_embedding`. If max cosine > 0.85 the CREATE is rejected with
a `skipped_similar` counter bump.

## Configuration

```python
@dataclass(frozen=True)
class DynamicLedgerConfig:
    enabled: bool = False
    embedding_model: str = "text-embedding-3-large"
    embedding_dim: int = 3072
    top_k_per_axis: int = 5
    curator_model: str | None = None        # filled from TestModelProfile at runtime
    curator_extra_args: dict | None = None  # filled from TestModelProfile at runtime
    curator_temperature: float = 1.0
    curator_max_tokens: int = 16000
    curator_timeout_seconds: int = 1800
    create_time_similarity_threshold: float = 0.85
```

CLI flag: `--dynamic-ledger / --no-dynamic-ledger`. Default OFF.

### Curator model policy

The curator runs on **the same model as the agent profile under test**,
with the same `model_configs` (reasoning effort, etc.) and the same
extended-thinking knobs. If the profile is `grok-4.3-high`, the curator
is also `grok-4.3-high`; if the profile is `gpt-5.5-medium`, the
curator is also `gpt-5.5-medium`. Only the **judge** model is fixed
(gpt-5.5 medium).

The runner fills `cfg.curator_model` and `cfg.curator_extra_args` from
the active `TestModelProfile` before the first curator call. Setting
`cfg.curator_model` explicitly is allowed for curator-ablation
experiments, but the CLI does not surface that knob.

## Per-domain isolation

Each domain (Finance, Legal, Consulting, Medicine) has its own Ledger
and its own snapshot history under
`runs/<run>/dynamic_ledger/<Domain>/snapshot_NNNN.json`. Retrieval at
task `i` in domain D sees the active entries of D's ledger only;
never cross-domain.

## Snapshots & resume

After each task in domain D, the runner saves
`snapshot_<ordinal>.json` and appends one line to `curator_log.jsonl`
with op counts, token usage, and wall time. On resume, the runtime
loads `snapshot_<max_completed>.json` so the in-flight ledger is
exactly what it would have been at that point.

## CSV columns added when the Ledger is on

```
dynamic_ledger_enabled
dynamic_ledger_snapshot_index_before
retrieved_entry_count
retrieved_entry_ids                  JSON list
curator_create_count                 (committed)
curator_create_blocked_count         (rejected by create-time dedup)
curator_update_count
curator_delete_count
dynamic_ledger_active_entry_count_after
dynamic_ledger_total_entry_count_after
dynamic_ledger_total_active_chars_after
curator_prompt_tokens
curator_completion_tokens
curator_wall_seconds
```

**No** GT-related columns. **No** criteria-related columns. **No**
citation-related columns.

## Curator prompt design

The curator system prompt frames the ledger as a **reference cheatsheet**
— a passive document of formulas, conventions, definitions, and pitfall
flags that a future practitioner consults the way an analyst consults a
clipped formula sheet. Entries are reference content, not procedures.

The exact prompt is in
[`src/apex_bench/dynamic_ledger/prompts/curator_system.txt`](../src/apex_bench/dynamic_ledger/prompts/curator_system.txt).
Every entry the curator emits must satisfy six properties:

- **S1** — reference content, not an instruction (formula, definition,
  convention, or pitfall flag — not a procedure or step list).
- **S2** — self-contained; readable without seeing the source case.
- **S3** — reusable on structurally distinct future cases; no
  case-specific numbers, dates, or named entities.
- **S4** — domain-specific insight, not generic advice.
- **S5** — short and dense (a tight paragraph; never a multi-section
  workflow).
- **S6** — `section` and `source_problem` name the *class* of case that
  should trigger retrieval, precisely enough to be retrievable.

Default behavior is zero, one, or two ops per session. The generator-side
injection block (
[`src/apex_bench/dynamic_ledger/prompts/generator_injection_block.txt`](../src/apex_bench/dynamic_ledger/prompts/generator_injection_block.txt)
) frames the retrieved entries as a formula sheet the generator may
consult but never follows; the generator's own analysis is authoritative.

## Tests

```
tests/test_dynamic_ledger_entry.py            Entry + DynamicLedger
tests/test_dynamic_ledger_store.py            SnapshotStore + resume
tests/test_dynamic_ledger_retriever_dedup.py  dual retrieval + dedup
tests/test_dynamic_ledger_curator.py          parser + apply_ops
tests/test_dynamic_ledger_injector.py         render + augment_user_prompt
tests/test_dynamic_ledger_fidelity.py         load-bearing invariants
```

## Run it

```bash
apex-bench run \
    --model grok-4.3-high \
    --task-ids 145 \
    --dynamic-ledger \
    --output runs/dl-on/results.csv
```

The first task in a domain starts from an empty ledger. Each subsequent
task in that domain receives retrieval results from prior tasks in the
same domain.

## Attribution

The **Dynamic Ledger** method itself — itemised strategy memory with
typed `CREATE` / `UPDATE` / `DELETE` operations, dual-axis
(strategy + source-problem) embedding retrieval, and a create-time
similarity filter — is introduced in the **Dynamic Cheatsheet 2.0**
codebase by **Jerry Gu, Sabrina Yen-Ko, and Shurui Liu** (Stanford
SAIL; mentor: Mirac Suzgun). It is one of three memory architectures
studied in DC2 alongside the Dynamic Cheatsheet variants (Suzgun et
al., 2025) and ACE (Zhang et al., 2025).

The reference implementation lives at
`src/dc2/methods/dl.py` and `prompts/dl/{generator,curator}.md` in
the DC2 codebase.

```bibtex
@misc{gu_yenko_liu_2026_dynamic_ledger,
  title  = {Dynamic Ledger: Retrieval-Augmented Structured Memory for
            Test-Time Learning},
  author = {Gu, Jerry and Yen-Ko, Sabrina and Liu, Shurui},
  note   = {Mentor: Mirac Suzgun},
  year   = {2026}
}

@misc{suzgun_yuksekgonul_bianchi_jurafsky_zou_2025_dynamic_cheatsheet,
  title  = {Dynamic Cheatsheet: Test-Time Learning with Adaptive Memory},
  author = {Suzgun, Mirac and Yuksekgonul, Mert and Bianchi, Federico and
            Jurafsky, Dan and Zou, James},
  year   = {2025},
  eprint = {2504.07952},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CL},
  url    = {https://arxiv.org/abs/2504.07952}
}

@misc{suzgun_kalai_2024_meta_prompting,
  title  = {Meta-Prompting: Enhancing Language Models with Task-Agnostic
            Scaffolding},
  author = {Suzgun, Mirac and Kalai, Adam Tauman},
  year   = {2024},
  eprint = {2401.12954},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CL},
  url    = {https://arxiv.org/abs/2401.12954}
}
```

### What this repository changes (adaptations, not the core method)

The DL **flow and framework** here match the DC2 reference:
single-call curator emitting typed `CREATE` / `UPDATE` / `DELETE`
ops inside `<memory_updates>`, no GT signal, dual top-k retrieval
on strategy and source-problem embeddings, create-time cosine
similarity gate (0.85) against the retrieved subset. The
adaptations to this benchmark are scoped:

- **Curator prompt content** — a reference-cheatsheet framing with the
  six properties (S1–S6) listed above replaces the DC2 prompt body. The
  output contract is unchanged (same `<memory_updates>` block, same
  three ops).
- **Per-domain ledger** — one ledger per Mercor domain (Finance /
  Legal / Consulting / Medicine). The DC2 reference uses one global
  ledger; per-domain isolation prevents cross-domain pollution on a
  benchmark whose four domains do not transfer.
- **Free-form strategy text** — DC2 mandates a `Description /
  Applicability / Example / Anti-pattern` 4-field strategy body; ours
  is free-form to fit longer professional workflows.
- **k = 5 per axis** (DC2 default is 3).
