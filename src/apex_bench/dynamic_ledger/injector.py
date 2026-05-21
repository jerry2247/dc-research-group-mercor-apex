"""Hook A: render the strategies block + prepend it to the agent's user prompt.

Unlike the agents-bench harness (which serializes a full
``initial_messages.json``), apex-bench generates a single LLM call from
a template that substitutes ``{{Prompt}}`` and ``{{Domain}}``. The
Dynamic Ledger augments the value substituted into ``{{Prompt}}``; the
prompt template itself is untouched.
"""

from __future__ import annotations

from pathlib import Path

from apex_bench.dynamic_ledger.entry import Entry

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _truncate_entry_content(content: str, cap: int) -> str:
    if cap <= 0 or len(content) <= cap:
        return content
    head = content[:cap]
    last_para = head.rfind("\n\n")
    if last_para > cap * 0.6:
        head = content[:last_para]
    return head + f"\n\n[... {len(content) - len(head):,} more chars in full entry]"


def render_entries_block(entries: list[Entry], *, max_chars_per_entry: int = 3000) -> str:
    """Render retrieved entries as ``<entry entry-N section=...>...</entry>``
    blocks separated by blank lines, with a soft cap on content length."""
    if not entries:
        return "(no relevant prior notes)\n"
    parts: list[str] = []
    for e in entries:
        body = _truncate_entry_content(e.content, max_chars_per_entry)
        parts.append(f"<entry {e.entry_id} section={e.section}>\n{body}\n</entry>")
    return "\n\n".join(parts) + "\n"


def _load_injection_prefix() -> str:
    return (_PROMPTS_DIR / "generator_injection_block.txt").read_text(encoding="utf-8")


def augment_user_prompt(task_prompt: str, *, entries: list[Entry]) -> str:
    """Prepend the strategies block to ``task_prompt`` and return the result.

    The vendor template substitution is performed by the runner; this
    function only builds the augmented prompt string.
    """
    prefix_template = _load_injection_prefix()
    block = render_entries_block(entries)
    prefix = prefix_template.replace("{entries_block}", block)
    return prefix + task_prompt
