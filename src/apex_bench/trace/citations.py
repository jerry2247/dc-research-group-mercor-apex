"""TRACE citation parsing for single-shot prose deliverables.

The generator emits, on the LAST line of its prose response,
``<citations>[bullet-1, bullet-7]</citations>`` (or empty). The
wrapper parses out the cited bullet ids, strips the tag, and passes
the stripped prose to the grader. The original response (with the
tag) is retained for the reflector + curator's view.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CITATIONS_RE = re.compile(
    r"<citations>\s*\[\s*((?:bullet-\d+(?:\s*,\s*bullet-\d+)*)?)\s*\]\s*</citations>",
    re.IGNORECASE,
)
_LOOSE_CITATIONS_RE = re.compile(r"<citations\b[^>]*>(.*?)</citations>", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class CitationExtract:
    stripped_response: str
    cited_bullet_ids: list[str]
    citations_present: bool
    citations_malformed_count: int
    trailing_chars_after_citations: int


def extract_and_strip_citations(response: str) -> CitationExtract:
    if not response:
        return CitationExtract(
            stripped_response="",
            cited_bullet_ids=[],
            citations_present=False,
            citations_malformed_count=0,
            trailing_chars_after_citations=0,
        )

    malformed = 0
    for m in _LOOSE_CITATIONS_RE.finditer(response):
        if not _CITATIONS_RE.search(m.group(0)):
            malformed += 1

    matches = list(_CITATIONS_RE.finditer(response))
    if not matches:
        return CitationExtract(
            stripped_response=response,
            cited_bullet_ids=[],
            citations_present=False,
            citations_malformed_count=malformed,
            trailing_chars_after_citations=0,
        )
    last = matches[-1]
    inside = last.group(1).strip()
    ids: list[str] = []
    if inside:
        for token in inside.split(","):
            t = token.strip()
            if t and re.fullmatch(r"bullet-\d+", t):
                ids.append(t)

    trailing = response[last.end() :]
    trailing_nonws = sum(1 for c in trailing if not c.isspace())
    before = response[: last.start()].rstrip()
    return CitationExtract(
        stripped_response=before,
        cited_bullet_ids=ids,
        citations_present=True,
        citations_malformed_count=malformed,
        trailing_chars_after_citations=trailing_nonws,
    )
