# =============================================================================
#  apex-bench — task runner
#  All targets assume the project venv is at ./.venv and is activated by the
#  caller. Use `make setup` from a clean shell to create it.
# =============================================================================

.DEFAULT_GOAL := help

PY        ?= python3
VENV      ?= .venv
PIP        = $(VENV)/bin/pip
BIN        = $(VENV)/bin
SHELL     := /bin/bash

# Default dataset location. Override with: make catalog DATA=/path/to/dataset
DATA      ?= data/APEX-v1-extended

# -----------------------------------------------------------------------------
.PHONY: help
help:  ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# -----------------------------------------------------------------------------
.PHONY: setup
setup:  ## Create venv, install package + dev tools, register pre-commit hooks.
	bash scripts/setup.sh

.PHONY: install
install:  ## (Re)install the editable package and the vendored harness.
	$(PIP) install --upgrade pip
	$(PIP) install -e ./vendor/apex_evals
	$(PIP) install -e ".[dev]"

# -----------------------------------------------------------------------------
.PHONY: fetch-dataset
fetch-dataset:  ## Clone the mercor/APEX-v1-extended dataset into data/.
	bash scripts/fetch_dataset.sh

.PHONY: catalog
catalog:  ## Characterize the dataset; emits data/catalog.json.
	$(BIN)/apex-bench catalog --input-dir $(DATA) --output data/catalog.json

# -----------------------------------------------------------------------------
.PHONY: smoke
smoke:  ## Smoke-run ONE task. Usage: make smoke MODEL=claude-haiku-4-5-20251001
	@if [ -z "$(MODEL)" ]; then \
	  echo "error: MODEL is required. Example: make smoke MODEL=claude-haiku-4-5-20251001"; \
	  exit 2; \
	fi
	bash scripts/smoke_test.sh "$(MODEL)"

# -----------------------------------------------------------------------------
.PHONY: fmt
fmt:  ## Auto-format the project (ruff format + ruff --fix).
	$(BIN)/ruff format src tests
	$(BIN)/ruff check --fix src tests

.PHONY: lint
lint:  ## Lint without modifying.
	$(BIN)/ruff format --check src tests
	$(BIN)/ruff check src tests

.PHONY: type
type:  ## Static type-check apex_bench.
	$(BIN)/mypy src

.PHONY: test
test:  ## Run pytest.
	$(BIN)/pytest

.PHONY: check
check: lint type test  ## Run all checks (lint, type, test).

# -----------------------------------------------------------------------------
.PHONY: clean
clean:  ## Remove caches; preserves venv, data, runs.
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +

.PHONY: distclean
distclean: clean  ## Also remove the venv. data/ and runs/ are preserved.
	rm -rf $(VENV)
