"""Tests for the task-index browser."""

from __future__ import annotations

import csv
from pathlib import Path

from apex_bench.dataset import REQUIRED_COLUMNS
from apex_bench.task_index import _first_sentence, build_index


def _write_csv(dataset_dir: Path, rows: list[dict[str, str]]) -> None:
    inner = dataset_dir / "data"
    inner.mkdir(parents=True, exist_ok=True)
    with (inner / "train.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(REQUIRED_COLUMNS))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_first_sentence_basic() -> None:
    assert _first_sentence("First sentence. Second sentence.") == "First sentence."


def test_first_sentence_no_terminator_truncates_at_max_chars() -> None:
    s = _first_sentence("x" * 500, max_chars=20)
    assert len(s) <= 20
    assert s.endswith("…")


def test_first_sentence_strips_internal_whitespace() -> None:
    s = _first_sentence("hello\n   world.\nsecond.")
    assert s == "hello world."


def test_summarize_carries_attachment_exts(tmp_path: Path) -> None:
    pdf = tmp_path / "files" / "doc.pdf"
    csv_ = tmp_path / "files" / "data.csv"
    for p in (pdf, csv_):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    _write_csv(
        tmp_path,
        [
            {
                "Task ID": "9",
                "Domain": "Finance",
                "Prompt": "Compute the IRR. Use the spreadsheet.",
                "Rubric JSON": "{}",
                "File Attachments": "files/doc.pdf\nfiles/data.csv",
            }
        ],
    )
    [s] = build_index(tmp_path)
    assert s.task_id == "9"
    assert s.domain == "Finance"
    assert s.first_sentence == "Compute the IRR."
    assert s.n_attachments == 2
    assert set(s.attachment_exts) == {".pdf", ".csv"}


def test_build_index_preserves_csv_order(tmp_path: Path) -> None:
    _write_csv(
        tmp_path,
        [
            {
                "Task ID": str(i),
                "Domain": "Medicine",
                "Prompt": f"Question {i}.",
                "Rubric JSON": "{}",
                "File Attachments": "",
            }
            for i in (7, 3, 11)
        ],
    )
    summaries = build_index(tmp_path)
    assert [s.task_id for s in summaries] == ["7", "3", "11"]
