"""Structural tests — verify the package and vendored harness are importable.

These tests do not call any API. They run on a developer machine with the
venv set up and no `.env`. If any of these fail, `make setup` did not complete
correctly.
"""

from __future__ import annotations


def test_apex_bench_imports() -> None:
    import apex_bench

    assert apex_bench.__version__


def test_apex_bench_submodules_import() -> None:
    """Every wrapper module must be importable without side effects."""
    from apex_bench import catalog, cli, config, dataset, paths, smoke  # noqa: F401


def test_settings_defaults() -> None:
    from apex_bench.config import (
        DEFAULT_JUDGE_MODEL,
        RUNS_PER_TASK,
        Settings,
    )

    s = Settings.defaults()
    assert s.judge.model_id == DEFAULT_JUDGE_MODEL
    assert s.judge.model_id == "gpt-5.5", (
        "Project policy: judge is gpt-5.5 at OpenAI's default reasoning_effort "
        "(medium). See docs/REPRODUCIBILITY.md."
    )
    # Project policy: 1 run/task, always. This is not a Settings field — it is
    # a module-level constant — so we assert on it directly.
    assert RUNS_PER_TASK == 1, "Project policy: one run per (task, model)."


def test_repo_root_resolves() -> None:
    from apex_bench.paths import repo_root, vendor_dir

    root = repo_root()
    assert (root / "pyproject.toml").is_file()
    assert vendor_dir().is_dir()
    assert (vendor_dir() / "UPSTREAM.md").is_file()


def test_vendored_harness_imports() -> None:
    """If this fails, run `pip install -e ./vendor/apex_evals`."""
    from generation import Attachment, GenerationTask, ModelConfig  # noqa: F401
    from grading import GradingModelConfig, GradingTask  # noqa: F401


def test_vendor_prompt_template_present() -> None:
    from apex_bench.paths import vendor_dir

    tmpl = vendor_dir() / "prompt" / "response_generation_prompt.txt"
    assert tmpl.is_file()
    content = tmpl.read_text(encoding="utf-8")
    assert "{{Domain}}" in content
    assert "{{Prompt}}" in content
