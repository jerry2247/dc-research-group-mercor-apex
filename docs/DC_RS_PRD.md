# DC-RS — apex-bench

**DC-RS** (Dynamic Cheatsheet — Retrieval Synthesis; Suzgun et al. 2025,
arXiv:2504.07952) is a memory subsystem layered on the Mercor apex-bench
single-shot prose harness. DC-RS does **not** consume any grading signal:
the synthesizer never sees the rubric, the judge's verdict, the expected
answer, or any per-criterion outcome.

We follow Suzgun's published *retrieval-synthesis* variant with these
scoped adaptations to the apex-bench harness:

1. **OpenAI embeddings** (`text-embedding-3-large`) for the prompt
   embedding axis.
2. **Per-domain isolation.** Each apex-bench domain has its own memory
   bank and its own persistent cheatsheet slot. Retrieval at task *i* in
   domain *D* sees only past pairs from *D*. The TRACE subsystem uses the
   same isolation pattern.
3. **Prose-only.** apex-bench has no code-execution surface. The
   synthesizer prompt does not invoke any code-execution wrapper, and
   the generator does not consume one.
4. **Same model for synthesizer + agent.** The synthesizer runs on the
   active `TestModelProfile`'s `model_id` with the same
   `model_configs` (reasoning effort, temperature, timeout, etc.). Only
   the **judge** model is fixed (gpt-5.5 medium).

DC-RS is **off by default**. With `--dc-rs` off, the runner takes the
baseline code path; the CSV schema is byte-identical to the no-memory
shape. `--dc-rs` and `--trace` are mutually exclusive.

## Pipeline

```
   ┌──────────┐    ┌──────────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────┐
   │ EMBED    │───▶│  RETRIEVE    │───▶│ SYNTH    │───▶│  INJECT +    │───▶│ GENERATE │
   │ prompt   │    │  top-3 from  │    │ single   │    │  GENERATE    │    │ (vendor; │
   │          │    │  domain bank │    │ LLM call │    │  prompt has  │    │  un-     │
   │          │    │  by cosine   │    │ (sees    │    │  cheatsheet  │    │  modified│
   │          │    │              │    │  prev    │    │  prepended   │    │  template│
   │          │    │              │    │  ch-sh   │    │              │    │          │
   └──────────┘    └──────────────┘    └────┬─────┘    └──────┬───────┘    └─────┬────┘
        ▲                                   │                 │                  │
        │                          ┌────────▼────────┐        ▼                  ▼
        │                          │ replace single  │    ┌────────┐         ┌────────┐
        │                          │ persistent      │    │ GRADE  │         │        │
        │                          │ cheatsheet slot │    │ vendor │ ◀───────┘        │
        │                          │ for this domain │    │ judge  │                  │
        │                          └─────────────────┘    └────────┘                  │
        │                                                                             │
        │                            APPEND to domain bank                            │
        └───────────── (prompt, deliverable, prompt_embedding) ◀──────────────────────┘
```

Per task: **one** synthesizer LLM call. The synthesizer receives the
previous-task cheatsheet, the top-k=3 retrieved prior pairs (verbatim
prompt + verbatim prose deliverable), and the current task prompt — and
nothing else. No grading data, no expected answer.

## Persistent state per domain

Two pieces of state on disk, one piece of state in memory:

- **`bank.jsonl`** — append-only JSON-lines file. One `BankEntry` per
  line: `bank_id`, `task_id`, `task_prompt`, `deliverable`, the prompt
  embedding (3072-dim, `text-embedding-3-large`), and the `added`
  ordinal.
- **`cheatsheet.txt`** — the cheatsheet produced for the most recent
  task in the domain. Replaced whole each task. Initialised to the
  literal string `(empty)` when no task in the domain has completed yet.

The cheatsheet is **not** an accumulating object: each task's
synthesizer call produces a fresh cheatsheet from `(previous cheatsheet,
retrieved pairs, current task)`. The previous cheatsheet contributes
only what the synthesizer chooses to carry forward.

## Bank-entry shape

```python
class BankEntry(BaseModel):
    bank_id: str                     # "bank-NNNNN" per-domain sequential
    task_id: str                     # apex-bench task_id
    task_prompt: str                 # verbatim prompt given to the generator
                                     # (WITHOUT the synthesized cheatsheet wrapper)
    deliverable: str                 # verbatim generator response
    prompt_embedding: list[float]    # text-embedding-3-large; 3072d
    added: int                       # per-domain 0-indexed ordinal at append time
```

No usage counters, no helpful/harmful flags, no soft-delete. Append-only.

## Hooks into `runner.run_single_task`

| Hook | When | Effect |
|------|------|--------|
| **A. retrieve + synthesize + inject** | before the vendor template substitution that fills `{{Prompt}}` | embed the prompt; cosine-rank the domain bank; take top-k=3; render the retrieved pairs as a markdown block; call the synthesizer with `(previous cheatsheet, retrieved block, current prompt)`; parse the inner `<cheatsheet>...</cheatsheet>` body (fall back to the raw retrieved block if the wrapper is omitted); persist the new cheatsheet to disk; prepend the cheatsheet plus the partner-framed wrapper to the user-prompt slot. |
| **B. append to bank** | after grading completes | mint a new `bank_id`; append `(task_prompt, deliverable, prompt_embedding)` to `bank.jsonl`. |

Both hooks are guarded by `if dc_rs_runtime is not None`. With DC-RS off
they do not run; the CSV schema is the baseline shape.

## Retriever

Single-axis cosine on `prompt_embedding`:

```python
def retrieve(bank, *, query_embedding, k=3):
    if not bank.entries: return []
    scored = [(e, cosine(query_embedding, e.prompt_embedding)) for e in bank.entries]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:k]
```

No similarity threshold, no dedup, no domain filter at this layer (the
domain filter is at the `bank_for(domain)` layer above).

## Synthesizer — exact inputs

The synthesizer is a single LiteLLM completion call. Its function
signature is the load-bearing fidelity contract for the no-grading
property:

```python
def synthesize(
    *,
    current_cheatsheet: str,
    retrieved_entries_block: str,
    task_prompt: str,
    cfg: DCRSConfig,
) -> SynthesizerResult: ...
```

There is no `criteria`, no `score`, no `gt_correct`, no
`expected_answer`, no `judge_rationale` argument. A test asserts this
(`tests/test_dc_rs_fidelity.py`).

The synthesizer's output is parsed by `extract_cheatsheet`:

```python
_CHEATSHEET_RE = re.compile(r"<cheatsheet>\s*(.*?)\s*</cheatsheet>", re.DOTALL)
```

If the wrapper is present, the inner body becomes the cheatsheet. If
the wrapper is missing, the runtime falls back to the verbatim
retrieved-entries block — degradation, not failure.

## Generator-prompt injection

The synthesized cheatsheet is prepended to the user-prompt slot of the
vendored generator template, exactly where TRACE's bullet block is
injected. A short wrapper introduces the cheatsheet without using any
domain-specific framing:

```
A senior partner reviewed earlier work in this area and left these notes
for you. They are reference material — use what applies and ignore the
rest. They are not answers; the case below has its own specifics.

{cheatsheet}
```

The wrapper is two short paragraphs. The framing is "senior partner" —
domain-neutral, professional-services-applicable. The wrapper does not
mention DC-RS, retrieval, the bank, or the synthesizer.

## Configuration

```python
@dataclass(frozen=True)
class DCRSConfig:
    enabled: bool = False
    embedding_model: str = "text-embedding-3-large"
    embedding_dim: int = 3072
    top_k: int = 3

    synthesizer_model: str | None = None
    synthesizer_extra_args: dict | None = None

    synthesizer_temperature: float = 1.0
    synthesizer_max_tokens: int = 24_000
    synthesizer_timeout_seconds: int = 1800
```

CLI flags: `--dc-rs / --no-dc-rs`, `--dc-rs-top-k` (default 3).
Mutually exclusive with `--trace`.

## CSV columns added when DC-RS is on

```
dc_rs_enabled
dc_rs_bank_size_before
dc_rs_bank_size_after
dc_rs_retrieved_count
dc_rs_retrieved_bank_ids                  JSON list of bank_ids
dc_rs_appended_bank_id                    str
synthesizer_prompt_tokens
synthesizer_completion_tokens
synthesizer_wall_seconds
synthesizer_cheatsheet_chars
synthesizer_used_fallback                 bool
```

When `--no-dc-rs`, none of these columns appear in the header.

## Per-domain on-disk layout

```
runs/<run>/
  results.csv
  dc_rs/
    Consulting/
      bank.jsonl
      cheatsheet.txt
      cheatsheets/
        task_<task_id>.txt
      synthesizer_log.jsonl
    Finance/   ...
    Legal/   ...
    Medicine/   ...
```

`cheatsheets/task_<task_id>.txt` archives every cheatsheet the
synthesizer ever wrote for inspection; it is not load-bearing for
resume. `synthesizer_log.jsonl` records token counts and retrieval
diagnostics per call.

## Resume

The bank file is the source of truth for bank state; `cheatsheet.txt`
is the source of truth for the persistent cheatsheet slot. The results
CSV is the source of truth only for which `task_id`s have been
completed. On resume, the runtime scans `runs/<run>/dc_rs/` for each
domain subdirectory, loads the full `bank.jsonl`, and reads
`cheatsheet.txt` if present. The CSV is consulted only to skip
already-completed `task_id`s in the main loop.

## Tests

```
tests/test_dc_rs_bank.py              BankEntry round-trip; ordinal sequencing
tests/test_dc_rs_retriever.py         top-k cosine; ties; empty bank; k > bank size
tests/test_dc_rs_formatting.py        retrieved-entries markdown shape; reverse ordering
tests/test_dc_rs_extract.py           <cheatsheet> tag parser; fallback path
tests/test_dc_rs_synthesizer.py       kwargs-build pattern; placeholder substitution
tests/test_dc_rs_injector.py          generator-prompt wrapper substitution
tests/test_dc_rs_store.py             resume reads bank.jsonl + cheatsheet.txt
tests/test_dc_rs_fidelity.py          off-state CSV invariance; narrow synthesizer signature;
                                      mutex with --trace
```

The fidelity tests cover:
- the synthesizer signature includes neither `criteria`, `score`,
  `gt_correct`, nor `expected_answer` (load-bearing for the no-grading
  property);
- `--no-dc-rs` CSV header is byte-identical to baseline;
- `--dc-rs` plus `--trace` raises at the header builder.

## Citation

This subsystem implements the **DC-RS** variant of Dynamic Cheatsheet
by Suzgun, Yang, and Cohan.

```bibtex
@misc{suzgun2025dynamiccheatsheet,
  title  = {Dynamic Cheatsheet: Test-Time Learning with Adaptive Memory},
  author = {Suzgun, Mirac and Yang, Mert and Cohan, Arman},
  year   = {2025},
  eprint = {2504.07952},
  archivePrefix = {arXiv}
}
```
