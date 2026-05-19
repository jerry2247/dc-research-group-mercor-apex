"""Catalog tool tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from apex_bench.catalog import LengthStats, _count_rubric_criteria, build_report
from apex_bench.dataset import REQUIRED_COLUMNS


def _write_csv(dataset_dir: Path, rows: list[dict[str, str]]) -> None:
    inner = dataset_dir / "data"
    inner.mkdir(parents=True, exist_ok=True)
    with (inner / "train.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(REQUIRED_COLUMNS))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_length_stats_on_empty_input() -> None:
    s = LengthStats.from_ints([])
    assert s.n == 0 and s.min == 0 and s.max == 0 and s.mean == 0.0


def test_length_stats_basic() -> None:
    s = LengthStats.from_ints([1, 2, 3, 4, 5])
    assert s.n == 5
    assert s.min == 1
    assert s.max == 5
    assert s.median == 3
    assert s.mean == 3.0


@pytest.mark.parametrize(
    "rubric,expected",
    [
        ("[]", 0),
        ('{"a": {}}', 1),
        ('[{"criterion 1": {}}]', 1),
        ('[{"a": {}}, {"b": {}}, {"c": {}}]', 3),
        ("not json", None),
        ("123", None),
    ],
)
def test_count_rubric_criteria(rubric: str, expected: int | None) -> None:
    assert _count_rubric_criteria(rubric) == expected


def test_build_report_smoke(tmp_path: Path) -> None:
    _write_csv(
        tmp_path,
        [
            {
                "Task ID": "1",
                "Domain": "Consulting",
                "Prompt": "p1",
                "Rubric JSON": '[{"c1": {"description":"x", "weight":"Primary objective(s)", "criterion_type":["Reasoning"]}}]',
                "File Attachments": "",
            },
            {
                "Task ID": "2",
                "Domain": "Finance",
                "Prompt": "p2longer",
                "Rubric JSON": '[{"c1":{}}, {"c2":{}}]',
                "File Attachments": "",
            },
        ],
    )
    rep = build_report(tmp_path, include_timestamp=False)
    assert rep.total_tasks == 2
    assert rep.domains == {"Consulting": 1, "Finance": 1}
    assert rep.prompt_chars.min == 2
    assert rep.tasks_with_attachments == 0
    # Round-trip the report through JSON.
    s = rep.to_json()
    parsed = json.loads(s)
    assert parsed["total_tasks"] == 2
    assert parsed["generated_at"] is None
