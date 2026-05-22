"""Per-run in-flight DC-RS state (apex-bench).

Holds the per-domain banks, per-domain cheatsheet slots, embedding
client, and the run directory where state is persisted. Constructed
once by the runner at the start of a run; mutated as tasks complete.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from apex_bench.dc_rs.bank import BankEntry, DomainBank
from apex_bench.dc_rs.config import DCRSConfig
from apex_bench.dc_rs.embeddings import EmbeddingClient, LiteLLMEmbeddingClient
from apex_bench.dc_rs.store import EMPTY_CHEATSHEET, DomainStore

log = logging.getLogger(__name__)


@dataclass
class DCRSRuntime:
    cfg: DCRSConfig
    run_dir: Path
    embed: EmbeddingClient
    banks: dict[str, DomainBank] = field(default_factory=dict)
    cheatsheets: dict[str, str] = field(default_factory=dict)
    stores: dict[str, DomainStore] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        cfg: DCRSConfig,
        run_dir: Path,
        embed: EmbeddingClient | None = None,
    ) -> DCRSRuntime:
        """Build a runtime, pre-loading the bank and cheatsheet for every
        domain that already has state on disk.

        The on-disk bank.jsonl is the source of truth for bank state; the
        cheatsheet.txt is the source of truth for the persistent cheatsheet
        slot. The results CSV is the source of truth only for which tasks
        have been completed. Loading both unconditionally on resume keeps
        the contributions of any task whose curation happened but whose
        CSV row failed to write.
        """
        if embed is None:
            embed = LiteLLMEmbeddingClient(model=cfg.embedding_model)
        rt = cls(cfg=cfg, run_dir=run_dir, embed=embed)
        root = run_dir / "dc_rs"
        if root.is_dir():
            for sub in root.iterdir():
                if not sub.is_dir():
                    continue
                rt.bank_for(sub.name)
        return rt

    def store_for(self, domain: str) -> DomainStore:
        if domain not in self.stores:
            self.stores[domain] = DomainStore.for_domain(self.run_dir, domain)
        return self.stores[domain]

    def bank_for(self, domain: str) -> DomainBank:
        if domain not in self.banks:
            store = self.store_for(domain)
            self.banks[domain] = store.load_bank(domain)
            self.cheatsheets[domain] = store.read_cheatsheet()
        return self.banks[domain]

    def cheatsheet_for(self, domain: str) -> str:
        if domain not in self.cheatsheets:
            # Force load via bank_for, which also fills the cheatsheet slot.
            self.bank_for(domain)
        return self.cheatsheets.get(domain, EMPTY_CHEATSHEET)

    def write_cheatsheet(self, domain: str, cheatsheet: str) -> None:
        """Replace the persistent cheatsheet for ``domain`` in memory and on disk."""
        store = self.store_for(domain)
        self.cheatsheets[domain] = cheatsheet
        store.write_cheatsheet(cheatsheet)

    def archive_cheatsheet(self, domain: str, task_id: str, cheatsheet: str) -> Path:
        return self.store_for(domain).archive_cheatsheet(task_id, cheatsheet)

    def append_synth_log(self, domain: str, record: dict) -> None:
        self.store_for(domain).append_synth_log(record)

    def append_entry(
        self,
        *,
        domain: str,
        task_id: str,
        task_prompt: str,
        deliverable: str,
        prompt_embedding: list[float],
    ) -> str:
        """Mint a new BankEntry, persist it, and return its bank_id."""
        bank = self.bank_for(domain)
        bank_id = bank.next_bank_id()
        added = bank.next_added_ordinal()
        entry = BankEntry(
            bank_id=bank_id,
            task_id=task_id,
            task_prompt=task_prompt,
            deliverable=deliverable,
            prompt_embedding=prompt_embedding,
            added=added,
        )
        bank.append(entry)
        self.store_for(domain).append_bank_entry(entry)
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
