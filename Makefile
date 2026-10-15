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

XRUN := $(UV) run --extra transformers   # scorers + experiments need torch/transformers

.PHONY: score fomc-roberta experiments quick reproduce paper figures
score:  ## all pre-registered scoring jobs (LLM via local Ollama; cached, resumable)
	$(CAFFEINATE) env RUN="$(XRUN) cbtone" experiments/score_documents.sh
	$(CAFFEINATE) $(XRUN) python experiments/score_sentences.py fomc silver rq4a
	$(CAFFEINATE) $(XRUN) python experiments/train_ft.py

fomc-roberta:  ## FOMC-RoBERTa replication: train + score (D21; ~2 h + 10 min on an M4)
	$(CAFFEINATE) $(XRUN) python experiments/train_fomc_roberta.py
	$(CAFFEINATE) $(XRUN) cbtone score --scorer ft --model-dir data/models/fomc-roberta-repl \
	    fed ecb boe rba mas bi bnm bot pboc --out results/scores/fomc-roberta-repl.parquet

experiments:  ## RQ1-RQ5 tables, figures, results/summary.json (fails on unexplained sanity flags)
	$(CAFFEINATE) $(XRUN) python experiments/rq1_policy.py
	$(XRUN) python experiments/rq2_market.py
	$(XRUN) python experiments/rq3_crosslingual.py
	$(XRUN) python experiments/rq4_reliability.py
	$(XRUN) python experiments/rq5_transfer.py
	$(XRUN) python experiments/figures.py
	$(XRUN) python experiments/summarize.py

quick:  ## 60-document sample end-to-end: dictionary + LLM scores and event windows (<= 5 min)
	$(XRUN) cbtone score --scorer dict --quick
	$(XRUN) cbtone score --scorer llm --quick
	$(XRUN) cbtone events --out results/events-quick.parquet

paper:  ## paper/paper.pdf from paper/paper.md (numbers injected from results/summary.json)
	$(XRUN) python paper/build.py

reproduce: score experiments paper  ## everything from the committed corpus snapshot
