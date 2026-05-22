"""Unit tests for on-disk persistence + resume semantics."""

from __future__ import annotations

from pathlib import Path

from apex_bench.dc_rs.bank import BankEntry
from apex_bench.dc_rs.store import EMPTY_CHEATSHEET, DomainStore


def _entry(idx: int) -> BankEntry:
    return BankEntry(
        bank_id=f"bank-{idx:05d}",
        task_id=f"t-{idx}",
        task_prompt=f"p{idx}",
        deliverable=f"d{idx}",
        prompt_embedding=[float(idx), 0.0, 0.0],
        added=idx - 1,
    )


def test_append_and_load_bank_roundtrip(tmp_path: Path) -> None:
    store = DomainStore.for_domain(tmp_path, "Finance")
    store.append_bank_entry(_entry(1))
    store.append_bank_entry(_entry(2))
    store.append_bank_entry(_entry(3))

    # Reload from disk into a fresh DomainStore (resume path).
    store2 = DomainStore.for_domain(tmp_path, "Finance")
    bank = store2.load_bank("Finance")
    assert [e.bank_id for e in bank.entries] == ["bank-00001", "bank-00002", "bank-00003"]
    assert [e.task_id for e in bank.entries] == ["t-1", "t-2", "t-3"]
    assert bank.entries[0].prompt_embedding == [1.0, 0.0, 0.0]


def test_cheatsheet_slot_empty_when_no_file(tmp_path: Path) -> None:
    store = DomainStore.for_domain(tmp_path, "Finance")
    assert store.read_cheatsheet() == EMPTY_CHEATSHEET


def test_cheatsheet_slot_write_read_roundtrip(tmp_path: Path) -> None:
    store = DomainStore.for_domain(tmp_path, "Finance")
    store.write_cheatsheet("the body of the cheatsheet")
    store2 = DomainStore.for_domain(tmp_path, "Finance")
    assert store2.read_cheatsheet() == "the body of the cheatsheet"


def test_archive_cheatsheet_writes_per_task_file(tmp_path: Path) -> None:
    store = DomainStore.for_domain(tmp_path, "Finance")
    p = store.archive_cheatsheet("task-abc", "some cheatsheet text")
    assert p.exists()
    assert p.read_text() == "some cheatsheet text"
    assert p.name == "task_task-abc.txt"


def test_synth_log_append_jsonl(tmp_path: Path) -> None:
    import json

    store = DomainStore.for_domain(tmp_path, "Finance")
    store.append_synth_log({"task_id": "t-1", "prompt_tokens": 100})
    store.append_synth_log({"task_id": "t-2", "prompt_tokens": 200})
    lines = store.synth_log_path().read_text().strip().splitlines()
    assert len(lines) == 2
    parsed = [json.loads(ln) for ln in lines]
    assert parsed[0]["task_id"] == "t-1"
    assert parsed[1]["prompt_tokens"] == 200
