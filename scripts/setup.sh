#!/usr/bin/env bash
# =============================================================================
#  apex-bench setup --- create venv, install package + vendored harness,
#  install pre-commit hooks. Idempotent: safe to re-run.
# =============================================================================
set -euo pipefail

# Resolve repo root regardless of caller's CWD.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

PY="${PY:-python3}"
VENV="${VENV:-.venv}"

echo ":: apex-bench setup (root=$ROOT)"

# --- 1. Python version check -------------------------------------------------
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "error: Python >=3.11 required. Got: $($PY --version 2>&1)" >&2
  exit 2
fi
echo ":: Python OK: $($PY --version 2>&1)"

# --- 2. Venv -----------------------------------------------------------------
if [[ ! -d "$VENV" ]]; then
  echo ":: creating venv at $VENV"
  "$PY" -m venv "$VENV"
else
  echo ":: venv exists at $VENV"
fi

# shellcheck disable=SC1090
source "$VENV/bin/activate"

# --- 3. Install --------------------------------------------------------------
echo ":: upgrading pip"
pip install --quiet --upgrade pip setuptools wheel

echo ":: installing vendored harness (./vendor/apex_evals)"
pip install --quiet -e ./vendor/apex_evals

echo ":: installing apex-bench with [dev] extras"
pip install --quiet -e ".[dev]"

# --- 4. Pre-commit hooks -----------------------------------------------------
# pre-commit requires a git repo. Initialise one if it isn't there yet; the
# very first `make setup` call doubles as repo init.
if [[ -f .pre-commit-config.yaml ]]; then
  if [[ ! -d .git ]]; then
    echo ":: no .git yet; running git init (initial branch: main)"
    git init -q -b main
  fi
  echo ":: installing pre-commit hooks"
  pre-commit install --install-hooks
fi

# --- 5. .env from .env.example -----------------------------------------------
if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  echo ":: created .env from .env.example (chmod 600). Edit it with real keys before running smoke."
else
  echo ":: .env exists; not overwriting"
fi

# --- 6. Sanity import probe --------------------------------------------------
echo ":: import probe"
python -c "
import sys
try:
    from generation import GenerationTask, ModelConfig
    from grading import GradingTask, GradingModelConfig
    from apex_bench import __version__
    print(f'  apex_bench v{__version__}')
    print('  vendor.generation OK')
    print('  vendor.grading OK')
except ImportError as e:
    print(f'  IMPORT FAILED: {e}', file=sys.stderr)
    sys.exit(1)
"

echo
echo "setup OK. Next steps:"
echo "  1. \$EDITOR .env       # fill in OPENAI_API_KEY (judge), model key, and REDUCTO_API_KEY"
echo "  2. make fetch-dataset  # clone mercor/APEX-v1-extended"
echo "  3. make catalog        # characterize the dataset"
echo "  4. make smoke MODEL=<some-model-id>"
