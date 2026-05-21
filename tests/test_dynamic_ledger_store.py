"""Unit tests for the per-domain snapshot store + resume reconciliation."""

from __future__ import annotations

from pathlib import Path

from apex_bench.dynamic_ledger.entry import DynamicLedger
from apex_bench.dynamic_ledger.store import SnapshotStore


def _make_store(domain: str = "Finance") -> DynamicLedger:
    s = DynamicLedger(domain=domain)
    s.add(
        section="A",
        content="alpha",
        source_problem="apb",
        content_embedding=[1.0, 0.0],
        source_problem_embedding=[0.0, 1.0],
        created=1,
    )
    return s


def test_save_and_latest_roundtrip(tmp_path: Path) -> None:
    ss = SnapshotStore.for_domain(tmp_path, "Finance")
    store = _make_store()
    p1 = ss.save(store, index=1)
    assert p1.name == "snapshot_0001.json"

    store.add(
        section="B",
        content="beta",
        source_problem="bpb",
        content_embedding=[0.0, 1.0],
        source_problem_embedding=[1.0, 0.0],
        created=2,
    )
    p2 = ss.save(store, index=2)
    assert p2.name == "snapshot_0002.json"

    idx, loaded = ss.latest()
    assert idx == 2
    assert len(loaded.entries) == 2


def test_load_for_resume_respects_max_index_allowed(tmp_path: Path) -> None:
    ss = SnapshotStore.for_domain(tmp_path, "Finance")
    store = _make_store()
    ss.save(store, index=1)
    store.add(
        section="B",
        content="beta",
        source_problem="bpb",
        content_embedding=[0.0, 1.0],
        source_problem_embedding=[1.0, 0.0],
        created=2,
    )
    ss.save(store, index=2)
    ss.save(store, index=3)
    # CSV says only 1 task is completed; we must roll back to snapshot_0001
    idx, loaded = ss.load_for_resume(max_index_allowed=1, domain="Finance")
    assert idx == 1
    assert len(loaded.entries) == 1


def test_load_for_resume_empty_dir(tmp_path: Path) -> None:
    ss = SnapshotStore.for_domain(tmp_path, "Finance")
    idx, loaded = ss.load_for_resume(max_index_allowed=10, domain="Finance")
    assert idx == 0
    assert loaded.domain == "Finance"
    assert loaded.entries == {}


def test_append_curator_log(tmp_path: Path) -> None:
    ss = SnapshotStore.for_domain(tmp_path, "Finance")
    ss.append_curator_log({"task_id": "t1", "create": 1})
    ss.append_curator_log({"task_id": "t2", "create": 0, "delete": 1})
    lines = (ss.domain_dir / "curator_log.jsonl").read_text().splitlines()
    assert len(lines) == 2
    assert "t1" in lines[0]
    assert "t2" in lines[1]
