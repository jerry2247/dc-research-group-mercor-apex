"""Per-domain on-disk snapshot store + resume-from-CSV reconciliation.

Snapshots live at
``<run_dir>/dynamic_ledger/<Domain>/snapshot_<NNNN>.json`` (NNNN
zero-padded to four digits). One additional sidecar,
``curator_log.jsonl``, records one line per curator call with op
counts, token usage, and wall time.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from apex_bench.dynamic_ledger.entry import DynamicLedger

log = logging.getLogger(__name__)

_SNAPSHOT_RE = re.compile(r"^snapshot_(\d{4,})\.json$")


@dataclass
class SnapshotStore:
    domain_dir: Path

    @classmethod
    def for_domain(cls, run_dir: Path, domain: str) -> SnapshotStore:
        d = run_dir / "dynamic_ledger" / domain
        d.mkdir(parents=True, exist_ok=True)
        return cls(domain_dir=d)

    def snapshot_path(self, index: int) -> Path:
        return self.domain_dir / f"snapshot_{index:04d}.json"

    def save(self, store: DynamicLedger, *, index: int) -> Path:
        p = self.snapshot_path(index)
        p.write_text(store.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return p

    def latest(self) -> tuple[int, DynamicLedger] | None:
        idxs: list[int] = []
        for f in self.domain_dir.iterdir():
            m = _SNAPSHOT_RE.match(f.name)
            if m:
                idxs.append(int(m.group(1)))
        if not idxs:
            return None
        idx = max(idxs)
        return idx, DynamicLedger.model_validate_json(
            self.snapshot_path(idx).read_text(encoding="utf-8")
        )

    def load_for_resume(self, *, max_index_allowed: int, domain: str) -> tuple[int, DynamicLedger]:
        """Load the highest snapshot whose index ≤ ``max_index_allowed``.

        If no snapshot exists, returns ``(0, empty-store)``. If snapshots
        exist beyond ``max_index_allowed`` (e.g., the CSV was rolled back
        but snapshots weren't), the extras are left on disk; only the
        in-bound max is loaded.
        """
        candidates: list[int] = []
        for f in self.domain_dir.iterdir():
            m = _SNAPSHOT_RE.match(f.name)
            if m:
                candidates.append(int(m.group(1)))
        in_bound = [i for i in candidates if i <= max_index_allowed]
        if not in_bound:
            return 0, DynamicLedger(domain=domain)
        idx = max(in_bound)
        store = DynamicLedger.model_validate_json(
            self.snapshot_path(idx).read_text(encoding="utf-8")
        )
        return idx, store

    def append_curator_log(self, record: dict) -> None:
        p = self.domain_dir / "curator_log.jsonl"
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
