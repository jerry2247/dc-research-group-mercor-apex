---
license: cc-by-4.0
task_categories:
  - text-generation
  - question-answering
language:
  - en
tags:
  - finance
  - legal
  - medical
  - consulting
  - benchmarking
  - rubric-grading
pretty_name: APEX-v1-extended
size_categories:
  - n<1K
configs:
  - config_name: default
    data_files:
      - split: train
        path: data/**
---

# APEX-v1-extended

The AI Productivity Index (APEX) is a benchmark from [Mercor](https://www.mercor.com/apex/) for assessing whether frontier models are capable of performing economically valuable tasks across four jobs: **investment banking associate**, **management consultant**, **big law associate**, and **primary care physician (MD)**.

APEX-v1-extended doubles the heldout evaluation set from n=200 to n=400, with increased complexity and variety. On average, tasks take over two-and-a-half hours for seasoned professionals to complete.

- **Tasks:** 400 heldout (100 per job) + 100 open-source dev set
- **Domains:** Investment banking, Management consulting, Law, Medicine
- **Grading:** Rubric-based, using a Judge LM (Gemini 2.5 Pro, Thinking=On)
- **Runs per model:** 8
- **License:** CC-BY 4.0
- **Intended use:** APEX-v1-extended is intended exclusively for model evaluation. Any use of this dataset for training, fine-tuning, or parameter fitting is forbidden. Crawling or scraping the dataset is also forbidden.

## Dataset overview

Each case consists of a prompt, source documents, and a grading rubric with prompt-specific quality criteria. Cases were created by 76 experts with a mean of 7.25 years of professional experience, sourced through the Mercor platform.

| Domain | # Cases (heldout) | Expert backgrounds |
|---|---|---|
| Investment banking | 100 | Goldman Sachs, Evercore, JPMorgan |
| Management consulting | 100 | McKinsey, BCG, Bain |
| Law | 100 | Latham & Watkins, Skadden, Cravath |
| Medicine | 100 | Leading medical institutions |

## Evaluation

APEX uses **rubric-based grading**:

- Each rubric contains multiple criteria (binary: Pass / Fail).
- A single Judge LM (Gemini 2.5 Pro, Thinking=On) grades each criterion independently.
- The overall score for each response is the mean percentage of criteria met.
- Each model is evaluated 8 times per task.

Changes from APEX-v1.0 to v1-extended include: (1) switching from a panel of LM judges to a single LM, (2) passing the prompt and source documents to the judge alongside the rubric, and (3) doubling the heldout set from n=200 to n=400.

## Leaderboard

You can view the latest leaderboard with live updates on the [APEX Leaderboard](https://www.mercor.com/apex/apex-v1-leaderboard/).

The leaderboard is based on the hidden heldout set of 400 tasks. For each task, responses are collected 8 times, graded using the Judge LM, and the mean value is reported.

## How to load the dataset

```python
from datasets import load_dataset

ds = load_dataset("mercor/APEX-v1-extended")
print(ds)
print(ds["train"][0].keys())
```

## Eval harness

Our evaluation harness is available open-source on GitHub: [Mercor-Intelligence/apex-evals](https://github.com/Mercor-Intelligence/apex-evals/tree/main/apex-evals-v1-extended)

```bash
git clone https://github.com/Mercor-Intelligence/apex-evals
cd apex-evals-v1-extended
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt && pip install -e .
cp example.env .env  # fill in your API keys
python examples/run_with_hf.py --input_dir /path/to/APEX-v1-extended --output apex_results.csv --start_index 0 --limit 5
```

## Citation

```bibtex
@misc{vidgen2025apex,
  title        = {The AI Productivity Index: APEX-v1-extended},
  author       = {Vidgen, Bertie and Fennelly, Abby and Pinnix, Evan and Bencheck, Julien and Khan, Daniyal and Richards, Zach and Bridges, Austin and Huang, Calix and Hunsberger, Ben and Robinson, Isaac and Datta, Akul and Mahapatra, Chirag and Barton, Dominic and Sunstein, Cass R. and Topol, Eric and Foody, Brendan and Nitski, Osvald},
  year         = {2025},
  howpublished = {arXiv},
  url          = {https://arxiv.org/abs/2509.25721}
}
```

## Related benchmarks

- [APEX-Agents](https://huggingface.co/datasets/mercor/apex-agents) — Long-horizon agentic tasks in professional services
- [ACE](https://huggingface.co/datasets/mercor/ACE) — AI Consumer Index for everyday consumer tasks
- [APEX-SWE](https://huggingface.co/datasets/mercor/APEX-SWE) — Software engineering tasks (integration + observability)

## Contact us

[apex@mercor.com](mailto:apex@mercor.com)

## Legal disclaimer

This material is provided for research, educational, and informational purposes only. It consists of hypothetical, simulated financial and legal and regulatory analyses and illustrative scenarios. No representation is made that any scenario described herein is likely to occur, is being contemplated by any person, or reflects an actual proposed or pending transaction or any legal, regulatory, or compliance risk.

This material does not constitute (and should not be construed as) financial, investment, legal, tax, accounting, or other professional advice, and is not intended to form the basis of any investment decision or any contract.

To the maximum extent permitted by applicable law, Mercor disclaims any liability for any direct or indirect losses or damages arising from or related to the use of (or reliance on) this material, including without limitation any loss of profits, loss of business, loss of goodwill, or consequential, incidental, special, punitive, or exemplary damages, even if advised of the possibility of such damages. Nothing in this disclaimer limits or excludes liability that cannot be limited or excluded under applicable law.

## Robots Exclusion Statement

User-Agent: *
Disallow: /

We ask that:
- You do *not* crawl, scrape, index, or download this dataset programmatically.
- You do *not* use this dataset for training models or any automated processing without express permission from the dataset owner.