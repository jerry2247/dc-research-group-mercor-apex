"""Memory bank — the persistent state DC-RS reads from and appends to.

A ``BankEntry`` records one past ``(task_prompt, deliverable)`` pair
along with the prompt embedding used for cosine retrieval. ``DomainBank``
is the in-memory list of entries for a single domain. The on-disk
representation is one JSON object per line in ``bank.jsonl``; append-only.

No usage counters, no helpful/harmful flags, no soft-delete. Once an
entry is appended, it stays for the duration of the run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict


class BankEntry(BaseModel):
    """One past pair in the bank, plus its prompt embedding."""

    model_config = ConfigDict(extra="ignore")

    bank_id: str
    task_id: str
    task_prompt: str
    deliverable: str
    prompt_embedding: list[float]
    added: int


@dataclass
class DomainBank:
    """In-memory bank for a single domain. Ordered by insertion."""

    domain: str
    entries: list[BankEntry] = field(default_factory=list)

    def append(self, entry: BankEntry) -> None:
        self.entries.append(entry)

    def next_bank_id(self) -> str:
        return f"bank-{len(self.entries) + 1:05d}"

    def next_added_ordinal(self) -> int:
        return len(self.entries)
