"""Browseable index of APEX-v1-extended tasks.

Produces a one-line summary per task so an operator can scan the 100-row
public split and choose what to run. Pure read-only — no model calls, no
network. Safe to invoke before credentials are configured.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from apex_bench.dataset import Task, load_tasks


@dataclass(frozen=True)
class TaskSummary:
    task_id: str
    domain: str
    first_sentence: str  # ~100-char preview of the prompt
    prompt_chars: int
    rubric_chars: int
    n_attachments: int
    attachment_exts: tuple[str, ...]  # e.g. (".pdf", ".csv")


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _first_sentence(prompt: str, max_chars: int = 140) -> str:
    """Return the first sentence of `prompt`, capped at max_chars."""
    # Normalize whitespace so we don't show a sentence with stray newlines.
    prompt = re.sub(r"\s+", " ", prompt).strip()
    if not prompt:
        return ""
    parts = _SENTENCE_END.split(prompt, maxsplit=1)
    first = parts[0]
    if len(first) > max_chars:
        first = first[: max_chars - 1].rstrip() + "…"
    return first


def summarize(task: Task) -> TaskSummary:
    exts: list[str] = []
    seen: set[str] = set()
    for a in task.attachments:
        ext = a.path.suffix.lower() or "(none)"
        if ext not in seen:
            exts.append(ext)
            seen.add(ext)
    return TaskSummary(
        task_id=task.task_id,
        domain=task.domain,
        first_sentence=_first_sentence(task.prompt),
        prompt_chars=task.prompt_chars,
        rubric_chars=task.rubric_chars,
        n_attachments=len(task.attachments),
        attachment_exts=tuple(exts),
    )


def build_index(dataset_dir: Path) -> list[TaskSummary]:
    """Read the dataset and return one summary per task. CSV order preserved."""
    return [summarize(t) for t in load_tasks(dataset_dir)]
