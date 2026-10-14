# Progress

Resume with: "Read MISSION.md, docs/PROGRESS.md, docs/DECISIONS.md and continue".

## Phase 1 — in progress (last update 2026-10-14)

Shipped (committed):
- [x] Scaffold, `Document` schema, `PoliteFetcher` (robots, 2 s/host, cache, block-page detection)
- [x] Text utils: clean, langdetect, split (en/id/ms/zh/th), mask; snapshot builder
- [x] Decisions: BIS rates + holds from meeting dates; MAS stance extractor (gold set pending MAS text)
- [x] Literature: 33 sources, REVIEW.md, refs.bib, gap table
- [x] Anchor-data licences (FOMC set + FOMC-RoBERTa CC-BY-NC-4.0 → evaluation only)

In flight (subagents; uncommitted files on disk):
- [ ] Fed adapter: code done; tests/fixtures/docs pending
- [ ] ECB adapter: code + 11 tests; docs pending
- [ ] Markets: fx/yields/events code; tests/docs pending
- [ ] Adapters BI, BNM, MAS (manual-file parse), BoE, RBA, PBoC, BoT

Remaining in Phase 1:
- [ ] Full fetch run for all reachable banks (`caffeinate -i`), snapshot → data/corpus/*.parquet + VERSION
- [ ] decisions.parquet built from the corpus meeting dates; cross-check vs bank calendars
- [ ] Consolidate docs/sources/NEEDED.md (MAS) and LICENSES.md table
- [ ] CLI: fetch/parse/snapshot/decisions/markets commands
- [ ] FOMC anchor loader (download at run time) + SEA silver-set sampling (labels made in Phase 3)

Open issues:
- MAS serves a bot "Maintenance" page → blocked (D7). Author may approve Internet Archive copies.
- data/raw/boe and data/raw/rba also hold yield files from the markets agent (cache keys by URL hash, so no collision).
