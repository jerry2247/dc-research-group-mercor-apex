"""Unit tests for on-disk persistence + resume semantics (global store)."""

from __future__ import annotations

from pathlib import Path

from apex_bench.dc_rs.bank import BankEntry
from apex_bench.dc_rs.store import EMPTY_CHEATSHEET, Store


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
    store = Store.for_run(tmp_path)
    store.append_bank_entry(_entry(1))
    store.append_bank_entry(_entry(2))
    store.append_bank_entry(_entry(3))

    # Reload from disk into a fresh Store (resume path).
    store2 = Store.for_run(tmp_path)
    bank = store2.load_bank()
    assert [e.bank_id for e in bank.entries] == ["bank-00001", "bank-00002", "bank-00003"]
    assert [e.task_id for e in bank.entries] == ["t-1", "t-2", "t-3"]
    assert bank.entries[0].prompt_embedding == [1.0, 0.0, 0.0]


def test_cheatsheet_slot_empty_when_no_file(tmp_path: Path) -> None:
    store = Store.for_run(tmp_path)
    assert store.read_cheatsheet() == EMPTY_CHEATSHEET


def test_cheatsheet_slot_write_read_roundtrip(tmp_path: Path) -> None:
    store = Store.for_run(tmp_path)
    store.write_cheatsheet("the body of the cheatsheet")
    store2 = Store.for_run(tmp_path)
    assert store2.read_cheatsheet() == "the body of the cheatsheet"


def test_archive_cheatsheet_writes_per_task_file(tmp_path: Path) -> None:
    store = Store.for_run(tmp_path)
    p = store.archive_cheatsheet("task-abc", "some cheatsheet text")
    assert p.exists()
    assert p.read_text() == "some cheatsheet text"
    assert p.name == "task_task-abc.txt"


def test_synth_log_append_jsonl(tmp_path: Path) -> None:
    import json

    store = Store.for_run(tmp_path)
    store.append_synth_log({"task_id": "t-1", "prompt_tokens": 100})
    store.append_synth_log({"task_id": "t-2", "prompt_tokens": 200})
    lines = store.synth_log_path().read_text().strip().splitlines()
    assert len(lines) == 2
    parsed = [json.loads(ln) for ln in lines]
    assert parsed[0]["task_id"] == "t-1"
    assert parsed[1]["prompt_tokens"] == 200


def test_store_layout_is_flat_not_per_domain(tmp_path: Path) -> None:
    """Suzgun's DC-RS reference carries one global pool + one cheatsheet
    slot. Our on-disk layout matches: no per-domain subdirectories
    under runs/<run>/dc_rs/."""
    store = Store.for_run(tmp_path)
    expected_root = tmp_path / "dc_rs"
    assert store.root == expected_root
    assert expected_root.is_dir()
    assert (expected_root / "cheatsheets").is_dir()
    # No Domain/ subdir is created by the store.
    domain_like = [p for p in expected_root.iterdir() if p.is_dir() and p.name != "cheatsheets"]
    assert domain_like == [], f"unexpected per-domain dir(s): {domain_like}"
