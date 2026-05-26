"""On-disk persistence for the DC-RS subsystem (single global pool).

Faithful to Suzgun et al.'s DC-RS, which carries one ``pool`` and one
``cheatsheet`` slot on the method state regardless of how many
benchmark domains a run touches. The on-disk layout mirrors that:

    runs/<run>/dc_rs/
      bank.jsonl                   # source of truth for the pool
      cheatsheet.txt               # most recent synthesized cheatsheet
      cheatsheets/task_<id>.txt    # per-task archive (diagnostic only)
      synthesizer_log.jsonl        # per-task synth call diagnostics

``bank.jsonl`` and ``cheatsheet.txt`` are load-bearing for resume. The
``cheatsheets/`` archive and ``synthesizer_log.jsonl`` are diagnostic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from apex_bench.dc_rs.bank import Bank, BankEntry

EMPTY_CHEATSHEET = "(empty)"


@dataclass
class Store:
    """File-system view of the run's single DC-RS state."""

    root: Path

    @classmethod
    def for_run(cls, run_dir: Path) -> Store:
        root = run_dir / "dc_rs"
        root.mkdir(parents=True, exist_ok=True)
        (root / "cheatsheets").mkdir(parents=True, exist_ok=True)
        return cls(root=root)

    # ---- pool ----------------------------------------------------------

    def bank_path(self) -> Path:
        return self.root / "bank.jsonl"

    def load_bank(self) -> Bank:
        """Read every line of bank.jsonl into a fresh Bank."""
        bank = Bank()
        path = self.bank_path()
        if not path.is_file():
            return bank
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                bank.append(BankEntry.model_validate_json(line))
        return bank

    def append_bank_entry(self, entry: BankEntry) -> None:
        with self.bank_path().open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")

    # ---- cheatsheet slot ----------------------------------------------

    def cheatsheet_path(self) -> Path:
        return self.root / "cheatsheet.txt"

    def read_cheatsheet(self) -> str:
        path = self.cheatsheet_path()
        if not path.is_file():
            return EMPTY_CHEATSHEET
        text = path.read_text(encoding="utf-8")
        return text if text.strip() else EMPTY_CHEATSHEET

    def write_cheatsheet(self, cheatsheet: str) -> None:
        self.cheatsheet_path().write_text(cheatsheet, encoding="utf-8")

    def archive_cheatsheet(self, task_id: str, cheatsheet: str) -> Path:
        path = self.root / "cheatsheets" / f"task_{task_id}.txt"
        path.write_text(cheatsheet, encoding="utf-8")
        return path

    # ---- synthesizer log -----------------------------------------------

    def synth_log_path(self) -> Path:
        return self.root / "synthesizer_log.jsonl"

    def append_synth_log(self, record: dict) -> None:
        with self.synth_log_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
