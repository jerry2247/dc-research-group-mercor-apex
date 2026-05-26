"""Per-run in-flight DC-RS state (apex-bench).

Holds the single global pool, the single cheatsheet slot, the
embedding client, and the run directory where state is persisted —
mirroring Suzgun et al.'s DC-RS reference, which carries one ``pool``
and one ``cheatsheet`` per method instance regardless of how many
benchmark domains the run touches.

Constructed once by the runner at the start of a run; mutated as tasks
complete.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from apex_bench.dc_rs.bank import Bank, BankEntry
from apex_bench.dc_rs.config import DCRSConfig
from apex_bench.dc_rs.embeddings import EmbeddingClient, LiteLLMEmbeddingClient
from apex_bench.dc_rs.store import EMPTY_CHEATSHEET, Store

log = logging.getLogger(__name__)


@dataclass
class DCRSRuntime:
    cfg: DCRSConfig
    run_dir: Path
    embed: EmbeddingClient
    store: Store = field(init=False)
    bank: Bank = field(init=False)
    cheatsheet: str = field(init=False, default=EMPTY_CHEATSHEET)
    _loaded: bool = field(init=False, default=False)

    @classmethod
    def create(
        cls,
        *,
        cfg: DCRSConfig,
        run_dir: Path,
        embed: EmbeddingClient | None = None,
    ) -> DCRSRuntime:
        """Build a runtime, loading the pool + cheatsheet slot from disk
        if either is present (resume).

        The on-disk ``bank.jsonl`` is the source of truth for the pool;
        ``cheatsheet.txt`` is the source of truth for the persistent
        cheatsheet slot. The results CSV is the source of truth only for
        which tasks have been completed.
        """
        if embed is None:
            embed = LiteLLMEmbeddingClient(model=cfg.embedding_model)
        store = Store.for_run(run_dir)
        bank = store.load_bank()
        cheatsheet = store.read_cheatsheet()
        rt = cls(cfg=cfg, run_dir=run_dir, embed=embed)
        rt.store = store
        rt.bank = bank
        rt.cheatsheet = cheatsheet
        rt._loaded = True
        return rt

    def write_cheatsheet(self, cheatsheet: str) -> None:
        """Replace the persistent cheatsheet slot in memory and on disk."""
        self.cheatsheet = cheatsheet
        self.store.write_cheatsheet(cheatsheet)

    def archive_cheatsheet(self, task_id: str, cheatsheet: str) -> Path:
        return self.store.archive_cheatsheet(task_id, cheatsheet)

    def append_synth_log(self, record: dict) -> None:
        self.store.append_synth_log(record)

    def append_entry(
        self,
        *,
        task_id: str,
        task_prompt: str,
        deliverable: str,
        prompt_embedding: list[float],
    ) -> str:
        """Mint a new BankEntry, persist it, and return its bank_id."""
        bank_id = self.bank.next_bank_id()
        added = self.bank.next_added_ordinal()
        entry = BankEntry(
            bank_id=bank_id,
            task_id=task_id,
            task_prompt=task_prompt,
            deliverable=deliverable,
            prompt_embedding=prompt_embedding,
            added=added,
        )
        self.bank.append(entry)
        self.store.append_bank_entry(entry)
        return bank_id


def dc_rs_csv_fragment_empty() -> dict:
    """Default fragment for the DC-RS CSV columns when the run is on but
    a per-task error prevents filling individual fields."""
    return {
        "dc_rs_enabled": True,
        "dc_rs_bank_size_before": 0,
        "dc_rs_bank_size_after": 0,
        "dc_rs_retrieved_count": 0,
        "dc_rs_retrieved_bank_ids": "[]",
        "dc_rs_appended_bank_id": "",
        "synthesizer_prompt_tokens": 0,
        "synthesizer_completion_tokens": 0,
        "synthesizer_wall_seconds": 0.0,
        "synthesizer_cheatsheet_chars": 0,
        "synthesizer_used_fallback": False,
    }
