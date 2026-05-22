"""Prepend the synthesized cheatsheet to the generator's user prompt.

Mirrors the position of the strategies-block injection used by the
other apex-bench memory subsystems: the wrapper text plus the
synthesized cheatsheet is placed *before* the verbatim task prompt,
and the combined string is then substituted into the vendored generator
template's ``{{Prompt}}`` slot.
"""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _injection_template() -> str:
    return (_PROMPTS_DIR / "generator_injection_template.txt").read_text(encoding="utf-8")


def augment_user_prompt(task_prompt: str, *, cheatsheet: str) -> str:
    """Return the user-prompt slot content with the cheatsheet block prepended.

    If the cheatsheet is empty, the prompt is returned unchanged so the
    generator sees byte-identical content to the baseline path.
    """
    if not cheatsheet.strip():
        return task_prompt
    block = _injection_template().replace("{cheatsheet}", cheatsheet)
    return f"{block}\n\n{task_prompt}"
