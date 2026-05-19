"""Dataset characterization.

Produces a deterministic JSON summary of the APEX-v1-extended public split.
Reproducible: given the same dataset clone, this always emits the same bytes
(modulo `generated_at`, which is stamped from a monotonic source if you want
strict reproducibility — see `--no-timestamp`).

The output is the input to budget planning and model selection — never run a
full benchmark without first running `apex-bench catalog`.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from apex_bench.dataset import Task, load_tasks


@dataclass(frozen=True)
class LengthStats:
    n: int
    min: int
    p25: int
    median: int
    p75: int
    max: int
    mean: float

    @classmethod
    def from_ints(cls, xs: list[int]) -> LengthStats:
        if not xs:
            return cls(n=0, min=0, p25=0, median=0, p75=0, max=0, mean=0.0)
        sorted_xs = sorted(xs)
        return cls(
            n=len(xs),
            min=sorted_xs[0],
            p25=sorted_xs[len(xs) // 4],
            median=sorted_xs[len(xs) // 2],
            p75=sorted_xs[(3 * len(xs)) // 4],
            max=sorted_xs[-1],
            mean=round(statistics.mean(xs), 2),
        )


@dataclass(frozen=True)
class CatalogReport:
    """Deterministic snapshot of dataset properties."""

    dataset_dir: str
    generated_at: str | None
    total_tasks: int
    domains: dict[str, int]
    prompt_chars: LengthStats
    rubric_chars: LengthStats
    rubric_criteria: LengthStats
    tasks_with_attachments: int
    tasks_with_missing_attachments: int
    attachments_per_task: LengthStats

    def to_json(self) -> str:
        # asdict gives nested dicts for LengthStats. sort_keys for stable bytes.
        return json.dumps(asdict(self), indent=2, sort_keys=True)


# -----------------------------------------------------------------------------


def build_report(
    dataset_dir: Path,
    *,
    include_timestamp: bool = True,
) -> CatalogReport:
    tasks = load_tasks(dataset_dir)
    return _build_from_tasks(tasks, dataset_dir, include_timestamp=include_timestamp)


def _build_from_tasks(
    tasks: list[Task], dataset_dir: Path, *, include_timestamp: bool
) -> CatalogReport:
    prompt_chars = [t.prompt_chars for t in tasks]
    rubric_chars = [t.rubric_chars for t in tasks]
    raw_criteria: list[int | None] = [_count_rubric_criteria(t.rubric_json) for t in tasks]
    rubric_criteria: list[int] = [c for c in raw_criteria if c is not None]
    attachments_per_task = [len(t.attachments) for t in tasks]

    with_attachments = sum(1 for t in tasks if t.has_attachments)
    missing_attachments = sum(1 for t in tasks if any(not a.exists for a in t.attachments))

    return CatalogReport(
        dataset_dir=str(dataset_dir),
        generated_at=(
            datetime.now(UTC).isoformat(timespec="seconds") if include_timestamp else None
        ),
        total_tasks=len(tasks),
        domains=dict(sorted(Counter(t.domain for t in tasks).items())),
        prompt_chars=LengthStats.from_ints(prompt_chars),
        rubric_chars=LengthStats.from_ints(rubric_chars),
        rubric_criteria=LengthStats.from_ints(rubric_criteria),
        tasks_with_attachments=with_attachments,
        tasks_with_missing_attachments=missing_attachments,
        attachments_per_task=LengthStats.from_ints(attachments_per_task),
    )


def _count_rubric_criteria(rubric_json: str) -> int | None:
    """Count criteria across the rubric. None if the JSON is unparsable.

    The APEX rubric is a JSON array of single-key dicts (or, less commonly, a
    flat dict). Both shapes are accepted by the upstream grader and need to be
    counted consistently.
    """
    try:
        parsed = json.loads(rubric_json)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, list):
        return sum(len(d) for d in parsed if isinstance(d, dict))
    if isinstance(parsed, dict):
        return len(parsed)
    return None


# -----------------------------------------------------------------------------


def write_report(report: CatalogReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.to_json() + "\n", encoding="utf-8")
