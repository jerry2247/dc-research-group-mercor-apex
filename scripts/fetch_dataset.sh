#!/usr/bin/env bash
# =============================================================================
#  Fetch mercor/APEX-v1-extended into ./data/APEX-v1-extended.
#
#  Default: try git clone (handles git-lfs if installed). Fallback:
#  huggingface-cli download. Both are equivalent for this dataset; the
#  fallback path avoids requiring git-lfs.
#
#  The dataset is CC-BY-4.0 with an explicit eval-only clause. By running
#  this script you acknowledge that the dataset must not be used for
#  training/fine-tuning. See docs/REPRODUCIBILITY.md.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

DEST="${DEST:-data/APEX-v1-extended}"
REPO_URL="https://huggingface.co/datasets/mercor/APEX-v1-extended"

mkdir -p "$(dirname "$DEST")"

if [[ -d "$DEST/.git" ]] || [[ -f "$DEST/data/train.csv" ]]; then
  echo ":: dataset already present at $DEST"
  if [[ -d "$DEST/.git" ]]; then
    echo ":: pulling latest"
    git -C "$DEST" pull --ff-only
  fi
else
  # Pick a downloader. Prefer the modern `hf` CLI (the renamed huggingface_hub
  # CLI). Fall back to git+lfs if that is what's available. The deprecated
  # `huggingface-cli` binary is intentionally not used.
  if command -v hf >/dev/null 2>&1; then
    echo ":: downloading via hf (huggingface_hub)"
    hf download mercor/APEX-v1-extended \
      --repo-type dataset \
      --local-dir "$DEST"
  elif command -v git-lfs >/dev/null 2>&1; then
    echo ":: hf not installed; cloning via git + git-lfs"
    git lfs install --local --skip-repo >/dev/null 2>&1 || true
    git clone --depth 1 "$REPO_URL" "$DEST"
  else
    echo "error: neither hf nor git-lfs is available." >&2
    echo "  install one of:" >&2
    echo "    pip install -U huggingface_hub    # inside .venv preferred" >&2
    echo "    brew install git-lfs" >&2
    exit 2
  fi
fi

# --- Verify ------------------------------------------------------------------
CSV="$DEST/data/train.csv"
if [[ ! -f "$CSV" ]]; then
  echo "error: expected $CSV after fetch; it is missing." >&2
  echo "       inspect $DEST contents to debug." >&2
  exit 3
fi

# Count the real CSV rows. The naive `wc -l < "$CSV"` is wrong here: APEX
# rubric JSON cells contain literal newlines, so `wc -l` reports thousands
# instead of the real 100 rows. Use Python's csv module which respects
# quoted multi-line fields.
ROWS=$(python3 -c "
import csv, sys
with open('$CSV', encoding='utf-8', newline='') as f:
    print(sum(1 for _ in csv.DictReader(f)))
")
HEADER=$(head -1 "$CSV")
echo ":: dataset OK"
echo "   path:    $DEST"
echo "   csv:     $CSV"
echo "   rows:    $ROWS  (parsed via csv.DictReader; wc -l would mis-report due to multi-line JSON cells)"
echo "   header:  $HEADER"

if [[ "$ROWS" != "100" ]]; then
  echo ":: WARNING — expected 100 rows in the public split, got $ROWS."
  echo "             Upstream may have updated; verify against the dataset card."
fi
