"""DC-RS (Dynamic Cheatsheet — Retrieval Synthesis) subsystem for apex-bench.

A faithful port of Suzgun et al.'s DC-RS (arXiv:2504.07952) adapted
to the prose-only apex-bench harness.

Per task: embed the current prompt → retrieve top-k=3 most similar
``(prompt, deliverable)`` pairs from the single global pool → one
synthesizer LLM call produces a fresh cheatsheet (informed by the
previous-task cheatsheet and the retrieved pairs) → the generator
answers using that cheatsheet → after grading, the new
``(prompt, deliverable, embedding)`` triple is appended to the pool.

No ground-truth signal reaches the synthesizer. The cheatsheet is
replaced whole each task; the pool is append-only.

See ``docs/DC_RS_PRD.md`` for the full specification.
"""

from __future__ import annotations

from apex_bench.dc_rs.bank import Bank, BankEntry
from apex_bench.dc_rs.config import DCRSConfig
from apex_bench.dc_rs.extract import extract_cheatsheet
from apex_bench.dc_rs.formatting import format_retrieved_entries
from apex_bench.dc_rs.injector import augment_user_prompt
from apex_bench.dc_rs.retriever import retrieve
from apex_bench.dc_rs.synthesizer import SynthesizerResult, synthesize

__all__ = [
    "Bank",
    "BankEntry",
    "DCRSConfig",
    "SynthesizerResult",
    "augment_user_prompt",
    "extract_cheatsheet",
    "format_retrieved_entries",
    "retrieve",
    "synthesize",
]
