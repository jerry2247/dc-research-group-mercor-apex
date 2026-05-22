"""Hook A: render the cheatsheet block + return augmented user prompt.

For apex-bench the runner substitutes a single user-prompt slot into a
vendor template; we expose ``augment_user_prompt`` that returns the
string to substitute. The vendor template SHA stays unchanged.
"""

from __future__ import annotations

from pathlib import Path

from apex_bench.trace.bullet import Bullet

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _truncate_bullet_content(content: str, cap: int) -> str:
    if cap <= 0 or len(content) <= cap:
        return content
    head = content[:cap]
    last_para = head.rfind("\n\n")
    if last_para > cap * 0.6:
        head = content[:last_para]
    return head + f"\n\n[... {len(content) - len(head):,} more chars in full bullet]"


def render_bullets_block(bullets: list[Bullet], *, max_chars_per_bullet: int = 6000) -> str:
    if not bullets:
        return "(no relevant strategy bullets yet)\n"
    parts: list[str] = []
    for b in bullets:
        body = _truncate_bullet_content(b.content, max_chars_per_bullet)
        parts.append(
            f"<bullet {b.bullet_id} section={b.section} helpful={b.helpful} "
            f"harmful={b.harmful} usage={b.usage}>\n{body}\n</bullet>"
        )
    return "\n\n".join(parts) + "\n"


def _load_injection_prefix() -> str:
    return (_PROMPTS_DIR / "generator_injection_block.txt").read_text(encoding="utf-8")


def augment_user_prompt(task_prompt: str, *, bullets: list[Bullet]) -> str:
    """Build the augmented user-prompt string: cheatsheet block + citation
    instruction + the verbatim task prompt."""
    prefix_template = _load_injection_prefix()
    block = render_bullets_block(bullets)
    prefix = prefix_template.replace("{bullets_block}", block)
    return prefix + task_prompt
