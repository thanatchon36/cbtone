# Plan

## Phase 1 — Corpus, decisions, labels, literature (started 2026-10-14)

| # | Item | Owner | Spec | Status |
|---|---|---|---|---|
| 1.1a | Fed adapter | subagent | specs/adapters.md | in progress |
| 1.1b | ECB adapter | subagent | specs/adapters.md | in progress |
| 1.1c | MAS, BI, BNM adapters | subagents (after Fed/ECB validate the spec) | specs/adapters.md | queued |
| 1.1d | BoE, RBA, PBoC, BoT adapters | subagents | specs/adapters.md | queued |
| 1.1e | text cleaning + sentence splitters (en/id/ms/zh/th), snapshot builder | subagent | specs/text.md | queued |
| 1.2 | BIS policy-rate decisions table + MAS stance extractor + 20-doc gold | subagent + main review | specs/decisions.md | queued |
| 1.3 | Market data (yfinance FX, FRED yields) + event timestamps | subagent | specs/markets.md | queued |
| 1.4 | FOMC anchor set (licence check) + 200-sentence SEA silver set | main + subagent | specs/labels.md | queued; silver labels need the LLM scorer, so they finish in Phase 3/4 with labelling only, no full-corpus scoring before prereg |
| 1.5 | Literature: 3 clusters → REVIEW.md + refs.bib + gap table | 3 subagents, main merges | specs/literature.md | in progress |

Exit criteria: documents/sentences/manifest parquet built for every reachable headline bank;
decisions.parquet; LICENSES.md complete; REVIEW.md with gap table; PROGRESS.md updated; pushed.
