"""Dataset-loader tests with a synthetic mini-CSV.

We do NOT depend on the real dataset being fetched. A tmp_path fixture is
enough to exercise every code path in `apex_bench.dataset`.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from apex_bench.dataset import (
    REQUIRED_COLUMNS,
    DatasetError,
    iter_tasks,
    load_tasks,
    validate,
)


def _write_csv(dataset_dir: Path, rows: list[dict[str, str]]) -> None:
    """Write rows to <dataset_dir>/data/train.csv with the canonical columns."""
    inner = dataset_dir / "data"
    inner.mkdir(parents=True, exist_ok=True)
    with (inner / "train.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(REQUIRED_COLUMNS))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def test_missing_csv_raises(tmp_path: Path) -> None:
    with pytest.raises(DatasetError, match="Expected APEX dataset CSV"):
        validate(tmp_path)


def test_missing_columns_raises(tmp_path: Path) -> None:
    inner = tmp_path / "data"
    inner.mkdir()
    (inner / "train.csv").write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="missing required columns"):
        validate(tmp_path)


def test_single_row_no_attachments(tmp_path: Path) -> None:
    _write_csv(
        tmp_path,
        [
            {
                "Task ID": "42",
                "Domain": "Consulting",
                "Prompt": "do the thing",
                "Rubric JSON": '[{"criterion 1": {"description": "x", "weight": "Primary objective(s)", "criterion_type": ["Reasoning"]}}]',
                "File Attachments": "",
            }
        ],
    )
    tasks = load_tasks(tmp_path)
    assert len(tasks) == 1
    t = tasks[0]
    assert t.task_id == "42"
    assert t.domain == "Consulting"
    assert t.prompt == "do the thing"
    assert t.has_attachments is False
    assert t.prompt_chars == len("do the thing")
    assert t.rubric_chars > 0


def test_row_with_attachments(tmp_path: Path) -> None:
    pdf = tmp_path / "files" / "doc.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4 stub")
    _write_csv(
        tmp_path,
        [
            {
                "Task ID": "1",
                "Domain": "Finance",
                "Prompt": "summarize the file",
                "Rubric JSON": "{}",
                "File Attachments": "files/doc.pdf",
            }
        ],
    )
    [t] = load_tasks(tmp_path)
    assert t.has_attachments is True
    assert len(t.attachments) == 1
    a = t.attachments[0]
    assert a.rel_path == "files/doc.pdf"
    assert a.path == (tmp_path / "files" / "doc.pdf").resolve()
    assert a.exists is True


def test_multiple_attachments_split_on_newlines(tmp_path: Path) -> None:
    for name in ("a.pdf", "b.pdf"):
        p = tmp_path / "files" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    _write_csv(
        tmp_path,
        [
            {
                "Task ID": "2",
                "Domain": "Legal",
                "Prompt": "summarize both",
                "Rubric JSON": "{}",
                "File Attachments": "files/a.pdf\nfiles/b.pdf",
            }
        ],
    )
    [t] = load_tasks(tmp_path)
    assert [a.rel_path for a in t.attachments] == ["files/a.pdf", "files/b.pdf"]
    assert all(a.exists for a in t.attachments)


def test_iter_tasks_is_lazy(tmp_path: Path) -> None:
    _write_csv(
        tmp_path,
        [
            {
                "Task ID": str(i),
                "Domain": "Medicine",
                "Prompt": f"prompt {i}",
                "Rubric JSON": "{}",
                "File Attachments": "",
            }
            for i in range(3)
        ],
    )
    it = iter_tasks(tmp_path)
    first = next(it)
    assert first.task_id == "0"
    assert sum(1 for _ in it) == 2
