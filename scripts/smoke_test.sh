#!/usr/bin/env bash
# =============================================================================
#  scripts/smoke_test.sh MODEL_ID
#  Runs ONE APEX task end-to-end. Verifies the entire pipeline works.
#
#  Usage:
#    make smoke MODEL=claude-haiku-4-5-20251001
#    bash scripts/smoke_test.sh claude-haiku-4-5-20251001
#    bash scripts/smoke_test.sh gpt-4o-mini --domain Consulting
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if [[ $# -lt 1 ]]; then
  echo "usage: $0 MODEL_ID [extra args forwarded to apex-bench smoke]" >&2
  exit 2
fi

MODEL="$1"
shift || true

if [[ ! -d .venv ]]; then
  echo "error: .venv not found. Run 'make setup' first." >&2
  exit 2
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if [[ ! -f .env ]]; then
  echo "error: .env not found. Run 'make setup' and fill in keys." >&2
  exit 2
fi
# Load .env into this shell so apex-bench's load_dotenv() picks it up.
# (apex-bench will load_dotenv() itself, but exporting here makes the keys
# visible to subshells and gives a clearer error if a key is missing.)
set -a
# shellcheck disable=SC1091
. ./.env
set +a

if [[ ! -d data/APEX-v1-extended/data ]]; then
  echo "error: dataset not found at data/APEX-v1-extended/. Run 'make fetch-dataset'." >&2
  exit 2
fi

echo ":: smoke run (test model: $MODEL)"
apex-bench smoke --model "$MODEL" "$@"
