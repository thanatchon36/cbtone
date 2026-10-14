#!/usr/bin/env bash
# All LLM-dependent jobs in order, on one backend (D20). Usage: experiments/run_llm_chain.sh
set -euo pipefail
export CBTONE_OLLAMA_URL=${CBTONE_OLLAMA_URL:-http://localhost:11434}
export CBTONE_SCORE_CACHE=${CBTONE_SCORE_CACHE:-data/cache/scores.sqlite}
PY=${PY:-"uv run --no-sync python"}
experiments/score_documents.sh
$PY experiments/score_sentences.py fomc silver rq4a
$PY experiments/train_ft.py
echo "LLM chain complete"
