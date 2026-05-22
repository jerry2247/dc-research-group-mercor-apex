"""Unit tests for DC-RS bank entry shape and DomainBank sequencing."""

from __future__ import annotations

import json

from apex_bench.dc_rs.bank import BankEntry, DomainBank


def _make_entry(idx: int) -> BankEntry:
    return BankEntry(
        bank_id=f"bank-{idx:05d}",
        task_id=f"t-{idx}",
        task_prompt=f"prompt {idx}",
        deliverable=f"deliverable {idx}",
        prompt_embedding=[float(idx), float(idx + 1), float(idx + 2)],
        added=idx - 1,
    )


def test_bank_entry_roundtrip_via_json() -> None:
    e = _make_entry(7)
    raw = e.model_dump_json()
    parsed = BankEntry.model_validate_json(raw)
    assert parsed.bank_id == "bank-00007"
    assert parsed.task_id == "t-7"
    assert parsed.task_prompt == "prompt 7"
    assert parsed.deliverable == "deliverable 7"
    assert parsed.prompt_embedding == [7.0, 8.0, 9.0]
    assert parsed.added == 6


def test_bank_entry_ignores_extra_fields() -> None:
    payload = {
        "bank_id": "bank-00001",
        "task_id": "t-1",
        "task_prompt": "p",
        "deliverable": "d",
        "prompt_embedding": [1.0],
        "added": 0,
        "future_field": "value the schema does not know about",
    }
    e = BankEntry.model_validate_json(json.dumps(payload))
    assert e.bank_id == "bank-00001"


def test_domain_bank_sequencing() -> None:
    bank = DomainBank(domain="Finance")
    assert bank.entries == []
    assert bank.next_bank_id() == "bank-00001"
    assert bank.next_added_ordinal() == 0
    bank.append(_make_entry(1))
    assert bank.next_bank_id() == "bank-00002"
    assert bank.next_added_ordinal() == 1
    bank.append(_make_entry(2))
    assert bank.next_bank_id() == "bank-00003"
    assert bank.next_added_ordinal() == 2
    assert [e.task_id for e in bank.entries] == ["t-1", "t-2"]
