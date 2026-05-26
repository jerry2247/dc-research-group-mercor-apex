"""Memory pool — the persistent state DC-RS reads from and appends to.

Faithful to Suzgun et al.'s DC-RS reference: one global pool per run,
not segmented by domain. Each ``BankEntry`` records one past
``(task_prompt, deliverable)`` pair along with the prompt embedding
used for cosine retrieval. The pool is append-only; no usage counters,
no helpful/harmful flags, no soft-delete.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict


class BankEntry(BaseModel):
    """One past pair in the pool, plus its prompt embedding.

    Mirrors Suzgun's ``PoolEntry`` shape adapted to apex-bench's
    prose-only surface (where ``deliverable`` is the verbatim generator
    response — there is no separate ``embedding_text`` field because
    apex-bench's embedding text and query are the same string)."""

    model_config = ConfigDict(extra="ignore")

    bank_id: str
    task_id: str
    task_prompt: str
    deliverable: str
    prompt_embedding: list[float]
    added: int


@dataclass
class Bank:
    """The single global pool for a DC-RS run."""

    entries: list[BankEntry] = field(default_factory=list)

    def append(self, entry: BankEntry) -> None:
        self.entries.append(entry)

    def next_bank_id(self) -> str:
        return f"bank-{len(self.entries) + 1:05d}"

    def next_added_ordinal(self) -> int:
        return len(self.entries)
