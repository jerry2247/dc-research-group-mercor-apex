# Vendor patches applied to `apex-evals-v1-extended`

This file records every change we have applied on top of the pristine
upstream snapshot recorded in `UPSTREAM.md`. The policy in `UPSTREAM.md`
permits these patches as long as each one is:

  1. Minimal,
  2. Tagged at the diff site with a `# vendored-patch: <reason>` comment,
  3. Recorded here with rationale and resync notes.

A fresh `rsync` from the upstream commit recorded in `UPSTREAM.md` followed
by re-applying these patches must produce the same file state we have now.

---

## Patch 1 — Register `gpt-5.5` and `grok-4.3` in `MODEL_MAPPINGS`

**File**: `src/call_llm/litellm_client.py`

**Sites**: two lines added inside the `MODEL_MAPPINGS` dict.

**Diff** (relative to upstream commit `6cbf3f43156bf332329abe76ed4a695fc71ec5b0`):

```python
# In MODEL_MAPPINGS["openai"], after "gpt-5.2-pro":
+ "gpt-5.5",  # vendored-patch: GPT-5.5 (released 2026-04-24) post-dates upstream pin; see vendor/apex_evals/PATCHES.md

# In MODEL_MAPPINGS["xai"], after "grok-4-0709":
+ "grok-4.3",  # vendored-patch: Grok 4.3 (released May 2026) post-dates upstream pin; see vendor/apex_evals/PATCHES.md
```

**Reason.** The upstream pin was cut on 2026-04-09. GPT-5.5 (OpenAI,
2026-04-24) and Grok 4.3 (xAI, May 2026) shipped after that. The vendor's
`LiteLLMClient.validate_model()` rejects any model id not in
`MODEL_MAPPINGS` via an exact-string match (`litellm_client.py:166-171`),
so both models would otherwise be rejected before any API call.

**Why this patch is safe.** The dict is the only barrier; once a model id
is present, the vendor's standard routing applies:
  - OpenAI: prefix `""`, model sent to LiteLLM as `gpt-5.5`. LiteLLM 1.83
    accepts `gpt-5.5` and routes it to OpenAI as the standard
    `model=gpt-5.5` API call. OpenAI's default `reasoning_effort` is
    `medium`; profile-level overrides flow through `model_configs` (vendor
    spreads it into `acompletion(**params)` at
    `litellm_client.py:281-282`).
  - xAI: prefix `xai`, model sent to LiteLLM as `xai/grok-4.3`. Per
    LiteLLM's docs the `xai/*` wildcard accepts any xAI-hosted model, so
    `xai/grok-4.3` is the canonical routing. `reasoning_effort` (`low` /
    `medium` / `high`) flows the same way.

**Resync notes.** When Mercor ships an upstream release that includes
either model id in MODEL_MAPPINGS, drop the corresponding line from this
patch and re-`rsync` against the new upstream commit. Update `UPSTREAM.md`
with the new commit SHA at the same time.

---

## Patch policy reminder

Patches are recorded here in chronological order. Do not delete entries;
when an upstream release subsumes a patch, leave it documented but mark
the date the patch was retired. This keeps the audit trail intact for
researchers who want to reproduce earlier runs.

| Patch | Applied | Retired | Reason |
|---|---|---|---|
| Patch 1 — register gpt-5.5 / grok-4.3 | 2026-05-19 | active | upstream pin pre-dates both models |
