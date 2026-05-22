"""On-disk persistence for the DC-RS subsystem.

Per domain, two pieces of state live on disk:

  - ``bank.jsonl`` — one ``BankEntry`` JSON object per line, append-only.
    The source of truth for the bank.
  - ``cheatsheet.txt`` — the current persistent cheatsheet slot for the
    domain. Replaced whole each task.

Plus two diagnostic outputs:

  - ``cheatsheets/task_<task_id>.txt`` — the cheatsheet produced for
    each task, archived for inspection.
  - ``synthesizer_log.jsonl`` — one record per synthesizer call:
    token counts, retrieved bank ids, wall seconds, fallback flag.

The directory layout mirrors the other apex-bench memory subsystems:

    runs/<run>/dc_rs/<Domain>/
      bank.jsonl
      cheatsheet.txt
      cheatsheets/task_<task_id>.txt
      synthesizer_log.jsonl
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from apex_bench.dc_rs.bank import BankEntry, DomainBank

EMPTY_CHEATSHEET = "(empty)"


@dataclass
class DomainStore:
    """File-system view of one domain's DC-RS state."""

    domain_dir: Path

    @classmethod
    def for_domain(cls, run_dir: Path, domain: str) -> DomainStore:
        d = run_dir / "dc_rs" / domain
        d.mkdir(parents=True, exist_ok=True)
        (d / "cheatsheets").mkdir(parents=True, exist_ok=True)
        return cls(domain_dir=d)

    # ---- bank ----------------------------------------------------------

    def bank_path(self) -> Path:
        return self.domain_dir / "bank.jsonl"

    def load_bank(self, domain: str) -> DomainBank:
        """Read every line of bank.jsonl into a fresh DomainBank."""
        bank = DomainBank(domain=domain)
        path = self.bank_path()
        if not path.is_file():
            return bank
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = BankEntry.model_validate_json(line)
                bank.append(entry)
        return bank

    def append_bank_entry(self, entry: BankEntry) -> None:
        with self.bank_path().open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")

    # ---- cheatsheet slot ----------------------------------------------

    def cheatsheet_path(self) -> Path:
        return self.domain_dir / "cheatsheet.txt"

    def read_cheatsheet(self) -> str:
        path = self.cheatsheet_path()
        if not path.is_file():
            return EMPTY_CHEATSHEET
        text = path.read_text(encoding="utf-8")
        return text if text.strip() else EMPTY_CHEATSHEET

    def write_cheatsheet(self, cheatsheet: str) -> None:
        self.cheatsheet_path().write_text(cheatsheet, encoding="utf-8")

    def archive_cheatsheet(self, task_id: str, cheatsheet: str) -> Path:
        path = self.domain_dir / "cheatsheets" / f"task_{task_id}.txt"
        path.write_text(cheatsheet, encoding="utf-8")
        return path

    # ---- synthesizer log -----------------------------------------------

    def synth_log_path(self) -> Path:
        return self.domain_dir / "synthesizer_log.jsonl"

    def append_synth_log(self, record: dict) -> None:
        with self.synth_log_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
