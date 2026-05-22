"""Extract the inner cheatsheet body from the synthesizer's raw response.

The synthesizer is instructed to wrap its output in
``<cheatsheet>...</cheatsheet>``. If it does, we keep the inner text.
If it does not, we fall back to the verbatim retrieved-entries block —
that way the generator still receives a non-empty reference even on
malformed synthesizer output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CHEATSHEET_RE = re.compile(r"<cheatsheet>\s*(.*?)\s*</cheatsheet>", re.DOTALL)


@dataclass(frozen=True)
class ExtractResult:
    cheatsheet: str
    used_fallback: bool


def extract_cheatsheet(raw_response: str, *, fallback: str) -> ExtractResult:
    """Return the inner cheatsheet body, or the fallback string if the
    synthesizer omitted the wrapper tag."""
    if raw_response:
        match = _CHEATSHEET_RE.search(raw_response)
        if match:
            inner = match.group(1).strip()
            if inner:
                return ExtractResult(cheatsheet=inner, used_fallback=False)
    return ExtractResult(cheatsheet=fallback, used_fallback=True)
