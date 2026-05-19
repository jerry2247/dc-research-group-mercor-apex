# Vendored upstream — `apex-evals-v1-extended`

This directory contains a **vendored, pristine copy** of the Mercor APEX-v1
evaluation harness. It is treated as third-party source: do not edit files
under this directory. All customizations (judge model, defaults, runner
shape, dataset path resolution, etc.) live in our own `src/apex_bench/`
package and *import from* the vendored modules.

## Provenance

| | |
|---|---|
| Upstream repo | https://github.com/Mercor-Intelligence/apex-evals |
| Vendored subdirectory | `apex-evals-v1-extended/` |
| Upstream commit | `6cbf3f43156bf332329abe76ed4a695fc71ec5b0` |
| Commit date | 2026-04-09 |
| Commit message | `fix(deps): pin litellm==1.83.0 (#14)` |
| Upstream license | CC-BY-4.0 (see `LICENSE_UPSTREAM` — note inconsistency below) |
| Vendored on | 2026-05-18 |

## License note

The upstream repository has an inconsistency: the file named `LICENSE` at the
repo root contains CC-BY-4.0, while `apex-evals-v1-extended/pyproject.toml`
declares `license = {text = "MIT"}` and the harness `README.md` cites
"CC-by-4.0". We treat the `LICENSE` file as authoritative (CC-BY-4.0) and have
vendored that text verbatim into `LICENSE_UPSTREAM`. CC-BY-4.0 is a permissive
license: we may redistribute, including with modifications, provided we
attribute the upstream and indicate changes — which `UPSTREAM.md` does. Our
own `src/apex_bench/` code is MIT.

## Why vendor instead of `pip install` from upstream

1. **Reproducibility.** Pinning a commit in our own tree is harder to drift
   than a path or URL dependency. A fresh clone of this repo, with no network,
   contains everything needed to run.
2. **Modification headroom.** We want the freedom to patch the harness
   in-place if a research need calls for it. Keeping the source local makes
   that patch reviewable in PR rather than hidden in a fork.
3. **Provenance.** Reviewers can `git log` against this directory to see
   exactly what we touched relative to the upstream snapshot.

## Diff policy

- **Default**: do not modify files under `vendor/apex_evals/`. Any
  customization (e.g. judge model selection, output path conventions,
  per-task batching) goes in `src/apex_bench/` and uses the vendored modules
  as importable libraries.
- **If a patch becomes necessary**: keep it minimal, add a `# vendored-patch:
  <reason>` comment at each diff site, and record the change in a top-level
  `vendor/apex_evals/PATCHES.md` so a future syncer can re-apply or upstream
  it.
- **Resyncing upstream**: bump the commit SHA above, run a clean `rsync -a
  --exclude='.git' ...` from a fresh upstream checkout, then re-apply patches
  documented in `PATCHES.md`.

## What's in here

This is a copy of `apex-evals-v1-extended/` from the upstream repo. Modules of
interest, all importable as ordinary Python after `pip install -e
./vendor/apex_evals`:

| Module | Role |
|---|---|
| `generation` | `GenerationTask`, `ModelConfig`, `Attachment`, `run_generation_task_async` |
| `grading` | `GradingTask`, `GradingModelConfig`, `run_grading_task_async`, `GradingResult` |
| `call_llm` | LiteLLM adapter (one client, all providers) |
| `parser` | Document parsing — Reducto by default |
| `handler` | Input validation |
| `errors` | Typed exceptions |

The reference end-to-end runner lives at `examples/run_with_hf.py`. We do not
call it from production paths — our own runner in `apex_bench.cli` reproduces
its loop with our defaults.

## License

Vendored upstream code: **CC-BY-4.0** per `LICENSE_UPSTREAM` (see "License
note" above for the inconsistency). Our own code under `src/apex_bench/`:
**MIT** per top-level `LICENSE`. CC-BY-4.0 permits this combination provided
attribution is preserved, which `UPSTREAM.md` and `LICENSE_UPSTREAM` together
satisfy.
