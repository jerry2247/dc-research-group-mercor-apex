"""Render retrieved bank entries as the synthesizer input block.

The shape mirrors the reference implementation: descending-similarity
order is computed by the retriever, then the rendering reverses that
order so the most similar entry appears closest to the current task
prompt in the synthesizer's user message.
"""

from __future__ import annotations

from apex_bench.dc_rs.retriever import Retrieved


def format_retrieved_entries(retrieved: list[Retrieved]) -> str:
    """Return the markdown block that fills ``{retrieved_entries}``.

    When the list is empty (the first task in a new bank), returns a
    short placeholder so the prompt template still substitutes cleanly.
    """
    if not retrieved:
        return (
            "### PREVIOUS SOLUTIONS (START)\n\n"
            "(none — this is one of the first tasks in this domain; "
            "no prior pairs are available for retrieval)\n\n"
            "### PREVIOUS SOLUTIONS (END)"
        )

    # Render least-similar first so the most-similar entry is closest to
    # the current task prompt that follows.
    ordered = list(reversed(retrieved))
    parts: list[str] = ["### PREVIOUS SOLUTIONS (START)", ""]
    for idx, r in enumerate(ordered, start=1):
        parts.append(f"#### Previous Input #{idx} (Similarity: {r.similarity:.2f}):")
        parts.append("")
        parts.append(r.entry.task_prompt)
        parts.append("")
        parts.append(f"#### Model Solution to Previous Input #{idx}:")
        parts.append("")
        parts.append(r.entry.deliverable)
        parts.append("---")
        parts.append("---")
        parts.append("")
    parts.append("### PREVIOUS SOLUTIONS (END)")
    return "\n".join(parts)
