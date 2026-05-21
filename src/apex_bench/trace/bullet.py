"""TRACE bullet data model + ``TraceLedger`` container (apex-bench)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Bullet(BaseModel):
    """One TRACE atomic-strategy bullet."""

    model_config = ConfigDict(extra="ignore")

    bullet_id: str
    section: str
    content: str
    source_problem: str
    active: bool = True
    helpful: int = 0
    harmful: int = 0
    usage: int = 0
    created: int
    updated: int
    content_embedding: list[float] = Field(default_factory=list)
    source_problem_embedding: list[float] = Field(default_factory=list)


def format_bullet_id(n: int) -> str:
    if n < 0:
        raise ValueError(f"bullet_id ordinal out of range: {n}")
    return f"bullet-{n}"


def parse_bullet_id(bullet_id: str) -> int:
    if not bullet_id.startswith("bullet-") or len(bullet_id) <= len("bullet-"):
        raise ValueError(f"malformed bullet_id: {bullet_id!r}")
    try:
        return int(bullet_id[len("bullet-") :])
    except ValueError as exc:
        raise ValueError(f"malformed bullet_id: {bullet_id!r}") from exc


class TraceLedger(BaseModel):
    model_config = ConfigDict(extra="ignore")

    domain: str
    next_bullet_ord: int = 1
    bullets: dict[str, Bullet] = Field(default_factory=dict)

    def active_bullets(self) -> list[Bullet]:
        return [b for b in self.bullets.values() if b.active]

    def get(self, bullet_id: str) -> Bullet | None:
        return self.bullets.get(bullet_id)

    def add(
        self,
        *,
        section: str,
        content: str,
        source_problem: str,
        content_embedding: list[float],
        source_problem_embedding: list[float],
        created: int,
    ) -> Bullet:
        bullet_id = format_bullet_id(self.next_bullet_ord)
        self.next_bullet_ord += 1
        b = Bullet(
            bullet_id=bullet_id,
            section=section,
            content=content,
            source_problem=source_problem,
            created=created,
            updated=created,
            content_embedding=list(content_embedding),
            source_problem_embedding=list(source_problem_embedding),
        )
        self.bullets[bullet_id] = b
        return b

    def update_content(
        self, bullet_id: str, *, content: str, content_embedding: list[float], updated: int
    ) -> Bullet | None:
        b = self.bullets.get(bullet_id)
        if b is None or not b.active:
            return None
        new = b.model_copy(
            update={
                "content": content,
                "content_embedding": list(content_embedding),
                "updated": updated,
            }
        )
        self.bullets[bullet_id] = new
        return new

    def soft_delete(self, bullet_id: str, *, updated: int) -> Bullet | None:
        b = self.bullets.get(bullet_id)
        if b is None or not b.active:
            return None
        new = b.model_copy(update={"active": False, "updated": updated})
        self.bullets[bullet_id] = new
        return new

    def record_citation(self, bullet_id: str, *, gt_correct: bool) -> bool:
        b = self.bullets.get(bullet_id)
        if b is None or not b.active:
            return False
        updates: dict[str, Any] = {"usage": b.usage + 1}
        if gt_correct:
            updates["helpful"] = b.helpful + 1
        else:
            updates["harmful"] = b.harmful + 1
        self.bullets[bullet_id] = b.model_copy(update=updates)
        return True

    def serialize_for_llm(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for b in self.active_bullets():
            out.append(
                {
                    "bullet_id": b.bullet_id,
                    "section": b.section,
                    "content": b.content,
                    "source_problem": b.source_problem,
                    "created": b.created,
                    "updated": b.updated,
                    "helpful": b.helpful,
                    "harmful": b.harmful,
                    "usage": b.usage,
                }
            )
        return out
