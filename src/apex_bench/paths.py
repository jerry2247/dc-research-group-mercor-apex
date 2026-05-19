"""Path resolution for apex-bench.

The repo root is whichever directory contains both `pyproject.toml` and
`vendor/apex_evals/`. We resolve it once, lazily, and key every other path
off it. Tests and CLI callers can override via the env var
`APEX_BENCH_ROOT`.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


class RepoLayoutError(RuntimeError):
    """Raised when the repo layout cannot be resolved."""


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """Return the absolute path to the apex-bench repo root.

    Resolution order:
      1. `$APEX_BENCH_ROOT` env var, if set and pointing at a valid root.
      2. Walk parents of this file until we find pyproject.toml AND
         vendor/apex_evals.
    """
    override = os.environ.get("APEX_BENCH_ROOT")
    if override:
        p = Path(override).resolve()
        if _looks_like_root(p):
            return p
        raise RepoLayoutError(
            f"APEX_BENCH_ROOT={override!r} is not a valid apex-bench root "
            "(missing pyproject.toml or vendor/apex_evals)."
        )

    here = Path(__file__).resolve()
    for candidate in [here, *here.parents]:
        if _looks_like_root(candidate):
            return candidate
    raise RepoLayoutError(
        "Could not locate apex-bench repo root. Set APEX_BENCH_ROOT or run from inside the repo."
    )


def _looks_like_root(p: Path) -> bool:
    return (p / "pyproject.toml").is_file() and (p / "vendor" / "apex_evals").is_dir()


def vendor_dir() -> Path:
    return repo_root() / "vendor" / "apex_evals"


def data_dir() -> Path:
    return repo_root() / "data"


def runs_dir() -> Path:
    return repo_root() / "runs"


def default_dataset_dir() -> Path:
    """Default path to the cloned mercor/APEX-v1-extended dataset."""
    return data_dir() / "APEX-v1-extended"


def default_dataset_csv() -> Path:
    """The CSV the upstream harness actually reads."""
    return default_dataset_dir() / "data" / "train.csv"
