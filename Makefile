# cbtone — all targets run inside the uv-managed env.
SHELL := /bin/bash
UV ?= uv
RUN := $(UV) run
CAFFEINATE := $(shell command -v caffeinate >/dev/null && echo "caffeinate -i")

.PHONY: help setup test lint format typecheck fetch snapshot score experiments quick paper reproduce docs

help:  ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

setup:  ## create the environment
	$(UV) sync

test:  ## unit tests (no network)
	$(RUN) pytest --cov=cbtone --cov-report=term-missing:skip-covered

lint:  ## ruff + mypy --strict on core
	$(RUN) ruff check .
	$(RUN) ruff format --check .
	$(RUN) mypy

format:  ## auto-format
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

fetch:  ## fetch raw documents for configured banks (polite, cached)
	$(CAFFEINATE) $(RUN) cbtone fetch

snapshot:  ## build data/corpus parquet snapshot
	$(RUN) cbtone snapshot

docs:  ## build the documentation site (mkdocs-material; needs the [docs] extra)
	$(RUN) --extra docs mkdocs build --strict

.PHONY: quick-ci
quick-ci:  ## dictionary scorer end-to-end on the committed mini corpus (no network)
	$(RUN) cbtone score --scorer dict fed rba --corpus tests/fixtures/corpus_mini --out /tmp/quick.parquet
