# apex-bench

Evaluation harness for **Dynamic Ledger** and **TRACE** — two test-time-learning subsystems — on Mercor's **APEX-v1-extended** benchmark (single-shot, professional-services prose deliverables).

## Project context

This repository sits inside a collaboration between two student teams at Stanford CS 224N, jointly mentored by Mirac Suzgun (Stanford SAIL NLP):

- **Dynamic Ledger** (*Retrieval-Augmented Structured Memory for Test-Time Learning*) — a no-ground-truth memory mechanism, developed by Jerry Gu, Sabrina Yen-Ko, and Shurui Liu.
- **TRACE** (*Tool-augmented Reasoning via Atomic Cheatsheet Editing*) — a memory mechanism that uses a per-task correctness bit, developed by Kyleen Liao, Roshen Nair, and Arnold Yang.

The two mechanisms are evaluated head-to-head on Mercor's APEX-v1-extended benchmark in this repository, and on the multi-turn agentic surface (Mercor's APEX-Agents) in the [`apex-agents-bench`](https://github.com/jerry2247/dc-research-group-mercor-apex-agents) sister repository. Both repositories share the same subsystem implementations and audit policy.

## What this repository is

A thin policy and orchestration layer over Mercor's evaluation harness (`vendor/apex_evals/`, vendored at commit `6cbf3f43`). The vendored harness — prompt template, attachment construction, rubric pass-through, per-criterion grading flow, and scoring formula — is preserved exactly; this repository contributes:

- **Two memory subsystems** that can be toggled via CLI flags; both are off by default. With either flag off the pipeline is byte-identical to the no-memory baseline (pinned by a fidelity test).
- **Project policies** — judge model fixed to `gpt-5.5` (medium reasoning effort, Mercor's published judge); one run per (task, model); a typed profile registry (`gpt-5.5-{low,medium,high,xhigh}`, `grok-4.3-{low,medium,high}`).
- **Reproducible CSV output** with per-task audit telemetry.

| Subsystem | CLI flag | Ground-truth signal | Spec |
|---|---|---|---|
| **Dynamic Ledger** | `--dynamic-ledger` | None | [`docs/DYNAMIC_LEDGER_PRD.md`](docs/DYNAMIC_LEDGER_PRD.md) |
| **TRACE** | `--trace` | boolean per-task correctness bit | [`docs/TRACE_PRD.md`](docs/TRACE_PRD.md) |

The benchmark dataset is Mercor's and is **not** redistributed; it is fetched at setup time from `mercor/APEX-v1-extended` on Hugging Face.

## Results

On the only configuration that has been run end-to-end at the time of writing — `grok-4.3-high`, gpt-5.5 judge, Finance subset (n = 25):

| Method | Pass@1 | Mean score (%) |
|---|:---:|:---:|
| Baseline (no memory) | 4 / 25 | 54.87 |
| + Dynamic Ledger | **5 / 25** | 50.02 |

Full per-domain × per-method table (with placeholders for Legal, Consulting, Medicine, and the TRACE row across all four), per-task breakdown, and a worked example of a Dynamic Ledger entry that converted a 23 → 92 score on a downstream task: [`results.md`](results.md). Pre-registered rollout order for the remaining cells: [`docs/EVALUATION_PLAN.md`](docs/EVALUATION_PLAN.md).

## Reproduce

```bash
git clone https://github.com/jerry2247/dc-research-group-mercor-apex.git apex-bench
cd apex-bench && pip install -e . && cp .env.example .env  # add API keys
make fetch-dataset                                          # fetches mercor/APEX-v1-extended

# Baseline (no memory)
apex-bench run --model grok-4.3-high --domain Finance --limit 25 \
    --output runs/grok43high-baseline/results.csv

# Dynamic Ledger
apex-bench run --model grok-4.3-high --domain Finance --limit 25 --dynamic-ledger \
    --output runs/grok43high-dl/results.csv
```

Full setup (venv, API keys, dataset hashes) and the documented divergences from Mercor's published harness: [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md), [`docs/AUDIT.md`](docs/AUDIT.md).

## Repository layout

| Path | Contents |
|---|---|
| `src/apex_bench/` | The harness — policy, runner, audit, CSV schema |
| `src/apex_bench/dynamic_ledger/` | Dynamic Ledger subsystem: config, retriever, curator, injector, prompts |
| `src/apex_bench/trace/` | TRACE subsystem: reflector, curator, prompts |
| `vendor/apex_evals/` | Mercor's evaluation harness, vendored at `6cbf3f43` |
| `data/APEX-v1-extended/` | Mercor's benchmark CSV, fetched from `mercor/APEX-v1-extended` |
| `runs/grok43high-baseline/` | Baseline run, grok-4.3-high, Finance subset |
| `runs/grok43high-dl/` | Dynamic Ledger run, same profile, same subset |
| `docs/` | Architecture, PRDs, reproducibility, audit. Index: [`docs/INDEX.md`](docs/INDEX.md) |

Behavioral fidelity to Mercor's published evaluation surface is enforced by pytest assertions and a code-level audit; see [`docs/AUDIT.md`](docs/AUDIT.md).

## License

Code: see [`LICENSE`](LICENSE). Mercor's vendored harness and benchmark dataset are governed by their respective upstream licenses.

## Citation

```bibtex
@misc{gu_yenko_liu_2026_dynamic_ledger,
  title  = {Dynamic Ledger: Retrieval-Augmented Structured Memory for
            Test-Time Learning},
  author = {Gu, Jerry and Yen-Ko, Sabrina and Liu, Shurui},
  note   = {Mentor: Mirac Suzgun},
  year   = {2026}
}

@misc{liao_nair_yang_2026_trace,
  title  = {TRACE: Tool-augmented Reasoning via Atomic Cheatsheet Editing},
  author = {Liao, Kyleen and Nair, Roshen and Yang, Arnold},
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
