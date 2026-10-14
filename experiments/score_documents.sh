#!/usr/bin/env bash
# Document-level scoring for all pre-registered analyses (RESEARCH_QUESTIONS.md §0.5; D18 ladder).
# Cached by content hash (data/cache/scores.sqlite): re-running only scores what is missing.
set -euo pipefail
RUN=${RUN:-"uv run --no-sync cbtone"}
ALL="fed ecb boe rba mas bi bnm bot pboc"
HEADLINE="fed ecb boe rba mas bi bnm"
$RUN score --scorer dict $ALL --out results/scores/dict.parquet
$RUN score --scorer dict $ALL --native --out results/scores/dict-native.parquet
$RUN score --scorer llm $ALL --out results/scores/llm.parquet
$RUN score --scorer llm $ALL --native --out results/scores/llm-native.parquet
$RUN score --scorer llm $HEADLINE --masked --out results/scores/llm-masked.parquet
