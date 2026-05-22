"""Typed run configuration for apex-bench.

A `Settings` instance is the single source of truth for a run: judge model,
paths, generation defaults. CLI flags override; env vars do not (env is only
for credentials).

Project policies (these are NOT knobs):
  - NUMBER_OF_RUNS = 1, always. Every reported number in this project uses one
    run per (task, model). This trades leaderboard-parity (8 runs/task) for
    being able to compare more methods within budget. Documented in
    `docs/REPRODUCIBILITY.md`.
  - JUDGE = gpt-5.5 at medium reasoning effort (OpenAI's default for that
    model). Fixed across all runs so cross-model comparisons stay well-defined;
    only the test model varies. Picked over Gemini for quality; picked over
    Opus 4.6 to keep judge costs proportional. Self-enhancement bias applies
    only when the test model is also gpt-5.5 — documented in
    `docs/REPRODUCIBILITY.md`.
  - PARSING_METHOD = "reducto" (matches upstream behavior; every public task
    has attachments and pypdf-only is insufficient — see catalog).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from apex_bench.dc_rs.config import DCRSConfig
from apex_bench.paths import default_dataset_dir, runs_dir

# --- Policy defaults (do not change casually) --------------------------------

DEFAULT_JUDGE_MODEL = "gpt-5.5"
"""GPT-5.5 with no reasoning_effort override → OpenAI's default `medium`.
This is the project judge across every run; only the test model varies.
The vendor's GradingModelConfig does NOT plumb model_configs through to the
LiteLLM request, so the medium default is what the API will apply — no
additional config needed in our wrapper. See `IMPLEMENTATION_PLAN.md` §1.4."""

DEFAULT_JUDGE_TEMPERATURE = 1.0
"""GPT-5.5 (the project judge) is an OpenAI reasoning model and only
accepts ``temperature == 1`` (the default). Other values are rejected with
HTTP 400. The legacy default of 0.01 came from Mercor's Gemini-judge
era; we left it on by accident and gpt-5.5 rejected it on the first
real run (2026-05-19). Helper :func:`apex_bench.runner._safe_judge_temperature`
also coerces any user-supplied non-1.0 value for reasoning-model judges
with a warning, as a defense in depth."""

DEFAULT_JUDGE_MAX_TOKENS = 32_000
"""Judge output budget. Per-criterion grading typically uses 50-500 tokens,
so 32k is far more than necessary — picked for safety on rubrics with very
verbose criterion descriptions."""

RUNS_PER_TASK = 1
"""Project policy: one run per (task, model). Not a knob. To prevent code
elsewhere from accidentally bumping this, the Settings dataclass exposes this
as a frozen field with no setter and the runner asserts equality before
launching a real run."""

DEFAULT_PARSING_METHOD = "reducto"
DEFAULT_CACHE_PARSED_DOCUMENTS = True

VALID_DOMAINS = ("Consulting", "Finance", "Legal", "Medicine")


# --- Settings ----------------------------------------------------------------


@dataclass(frozen=True)
class JudgeConfig:
    model_id: str = DEFAULT_JUDGE_MODEL
    temperature: float = DEFAULT_JUDGE_TEMPERATURE
    max_tokens: int = DEFAULT_JUDGE_MAX_TOKENS


@dataclass(frozen=True)
class Settings:
    """Run-time policy for an apex-bench invocation.

    All paths are absolute Path objects. CLI commands construct one of these
    from defaults + flags; library functions accept it as their config.

    Note: `number_of_runs` is intentionally absent. RUNS_PER_TASK is a project
    policy (1, always); see module docstring.
    """

    dataset_dir: Path
    runs_dir: Path
    judge: JudgeConfig
    parsing_method: str = DEFAULT_PARSING_METHOD
    cache_parsed_documents: bool = DEFAULT_CACHE_PARSED_DOCUMENTS
    dc_rs: DCRSConfig = field(default_factory=DCRSConfig)
    """DC Retrieval Synthesis settings. Default disabled — when off, the
    runner does not import any DC-RS module and the CSV schema is
    byte-identical to the baseline. See ``docs/DC_RS_PRD.md``."""

    @classmethod
    def defaults(cls) -> Settings:
        return cls(
            dataset_dir=default_dataset_dir(),
            runs_dir=runs_dir(),
            judge=JudgeConfig(),
        )

    def with_dataset_dir(self, p: Path) -> Settings:
        return Settings(
            dataset_dir=p,
            runs_dir=self.runs_dir,
            judge=self.judge,
            parsing_method=self.parsing_method,
            cache_parsed_documents=self.cache_parsed_documents,
            dc_rs=self.dc_rs,
        )

    def with_judge(self, judge: JudgeConfig) -> Settings:
        return Settings(
            dataset_dir=self.dataset_dir,
            runs_dir=self.runs_dir,
            judge=judge,
            parsing_method=self.parsing_method,
            cache_parsed_documents=self.cache_parsed_documents,
            dc_rs=self.dc_rs,
        )

    def with_dc_rs(self, dc_rs: DCRSConfig) -> Settings:
        return Settings(
            dataset_dir=self.dataset_dir,
            runs_dir=self.runs_dir,
            judge=self.judge,
            parsing_method=self.parsing_method,
            cache_parsed_documents=self.cache_parsed_documents,
            dc_rs=dc_rs,
        )
