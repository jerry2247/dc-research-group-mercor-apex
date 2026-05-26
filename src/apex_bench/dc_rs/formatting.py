"""Render retrieved pool entries as the synthesizer input block.

Faithful to Suzgun et al.'s DC-RS reference ``_format_entries``
(``dc_rs.py:275-300``):

  * empty pool → the literal string ``"(empty)"``;
  * non-empty → a preamble note framing the prior pairs as evidence
    (not authoritative answers) followed by per-entry blocks in
    REVERSED order (most-similar last so it sits closest to the
    current query the synthesizer's prompt template appends below),
    and a ``#### PREVIOUS SOLUTIONS (END)`` footer.

The per-entry markdown shape mirrors the reference exactly.
"""

from __future__ import annotations

from apex_bench.dc_rs.retriever import Retrieved


def format_retrieved_entries(retrieved: list[Retrieved]) -> str:
    """Return the markdown block that fills ``{retrieved_entries}``.

    When the pool is empty (the first task in a run), returns the
    literal string ``"(empty)"`` — matching the reference behaviour so
    the synthesizer prompt template substitutes cleanly without any
    extra wrapper headers.
    """
    if not retrieved:
        return "(empty)"

    chunks: list[str] = [
        "### PREVIOUS SOLUTIONS (START)\n\n"
        "Note: The input-output pairs listed below are taken from previous "
        "test cases and are meant to assist you in understanding potential "
        "solution strategies. While they can offer insight and inspiration, "
        "they should not be blindly copied, as they may contain errors or "
        "may not fit your specific use case. Approach them with a critical "
        "mindset — analyse their logic, verify their correctness, and adapt "
        "them as needed. Your goal should be to develop a well-reasoned "
        "solution that best addresses the case at hand."
    ]
    # Reversed so the most-similar retrieved entry sits closest to the
    # current case appended below by the synthesizer template.
    for idx, r in enumerate(reversed(retrieved), start=1):
        entry = r.entry
        chunks.append(
            f"#### Previous Input #{idx} (Similarity: {r.similarity:.2f}):\n\n"
            f"{entry.task_prompt}\n\n"
            f"#### Model Solution to Previous Input  #{idx}:\n\n"
            f"{entry.deliverable}\n---\n---"
        )
    chunks.append("#### PREVIOUS SOLUTIONS (END)")
    return "\n\n".join(chunks).strip()
