"""APEX-v1-extended dataset loader.

The dataset is a CSV at `<dataset_dir>/data/train.csv` with five columns:
    Task ID, Domain, Prompt, Rubric JSON, File Attachments

This loader is intentionally narrow: it does not parse PDFs, does not score,
does not call any model. Its only job is to surface the rows as typed
`Task` records and resolve attachment paths to absolute file paths.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

# Exact column names as published in mercor/APEX-v1-extended/data/train.csv.
# DO NOT rename these to be Pythonic — they have to match the upstream CSV.
COL_TASK_ID = "Task ID"
COL_DOMAIN = "Domain"
COL_PROMPT = "Prompt"
COL_RUBRIC_JSON = "Rubric JSON"
COL_FILE_ATTACHMENTS = "File Attachments"

REQUIRED_COLUMNS = (
    COL_TASK_ID,
    COL_DOMAIN,
    COL_PROMPT,
    COL_RUBRIC_JSON,
    COL_FILE_ATTACHMENTS,
)


class DatasetError(RuntimeError):
    """Raised when the dataset is missing, malformed, or unreadable."""


@dataclass(frozen=True)
class Attachment:
    """One file attached to a task. `path` is absolute and may not exist."""

    rel_path: str  # As written in the CSV; relative to dataset root
    path: Path  # Absolute resolved path

    @property
    def exists(self) -> bool:
        return self.path.is_file()


@dataclass(frozen=True)
class Task:
    """One APEX task row."""

    task_id: str  # Stored as str even though CSV declares int64; safer for IDs
    domain: str
    prompt: str
    rubric_json: str  # Raw JSON string; left unparsed at this layer
    attachments: tuple[Attachment, ...]

    @property
    def has_attachments(self) -> bool:
        return len(self.attachments) > 0

    @property
    def prompt_chars(self) -> int:
        return len(self.prompt)

    @property
    def rubric_chars(self) -> int:
        return len(self.rubric_json)


# -----------------------------------------------------------------------------


def csv_path(dataset_dir: Path) -> Path:
    """Path to the canonical train.csv inside a dataset clone."""
    return dataset_dir / "data" / "train.csv"


def validate(dataset_dir: Path) -> None:
    """Raise DatasetError if the dataset clone is unusable. Fail fast."""
    path = csv_path(dataset_dir)
    if not path.is_file():
        raise DatasetError(
            f"Expected APEX dataset CSV at {path}. Run `make fetch-dataset` "
            "or `bash scripts/fetch_dataset.sh` first."
        )
    with path.open(encoding="utf-8") as f:
        header = next(csv.reader(f), None)
    if header is None:
        raise DatasetError(f"{path} is empty.")
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise DatasetError(f"{path} is missing required columns: {missing}. Got: {header}.")


def iter_tasks(dataset_dir: Path) -> Iterator[Task]:
    """Yield typed Task records from the dataset CSV. Order matches the file."""
    validate(dataset_dir)
    path = csv_path(dataset_dir)
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            yield _row_to_task(row, dataset_dir)


def load_tasks(dataset_dir: Path) -> list[Task]:
    return list(iter_tasks(dataset_dir))


# -----------------------------------------------------------------------------


def _row_to_task(row: dict[str, str], dataset_dir: Path) -> Task:
    attachments_field = (row.get(COL_FILE_ATTACHMENTS) or "").strip()
    attachments: list[Attachment] = []
    if attachments_field:
        for rel in attachments_field.split("\n"):
            rel = rel.strip()
            if not rel:
                continue
            abs_path = (dataset_dir / rel).resolve()
            attachments.append(Attachment(rel_path=rel, path=abs_path))
    return Task(
        task_id=str(row.get(COL_TASK_ID, "")).strip(),
        domain=(row.get(COL_DOMAIN) or "").strip(),
        prompt=row.get(COL_PROMPT) or "",
        rubric_json=row.get(COL_RUBRIC_JSON) or "",
        attachments=tuple(attachments),
    )
