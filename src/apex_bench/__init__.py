"""apex-bench — reproducible runner around the Mercor APEX-v1-extended harness.

This package provides a thin orchestration layer over the vendored Mercor
evaluation harness at `vendor/apex_evals/`. The vendored code is treated as
third-party source and is not modified; all customization (judge model
selection, default paths, runner shape) lives here.

Public surface:
    apex_bench.config — typed run-config (judge, paths, defaults)
    apex_bench.paths  — repo-root and data-dir resolution
    apex_bench.dataset — APEX dataset loader
    apex_bench.catalog — dataset characterization tool
    apex_bench.smoke  — single-task smoke runner
    apex_bench.cli    — Typer CLI entry point (`apex-bench`)
"""

from apex_bench.config import Settings

__all__ = ["Settings", "__version__"]
__version__ = "0.1.0"
