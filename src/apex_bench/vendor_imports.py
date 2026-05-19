"""Helpers for importing the vendored Mercor harness cleanly."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from apex_bench.paths import vendor_dir


@contextmanager
def vendor_cwd() -> Iterator[None]:
    """Temporarily import/run vendored modules from their expected CWD.

    Mercor's grading module reads ``prompt/grading_prompt.txt`` at import
    time using a relative path. Importing it from the wrapper repo root logs
    a false error, even though we pass an absolute grading prompt path later.
    This context mirrors the upstream script's working directory just for
    the import boundary.
    """
    old_cwd = os.getcwd()
    os.chdir(vendor_dir())
    try:
        yield
    finally:
        os.chdir(old_cwd)
