# Progress

Resume with: "Read MISSION.md, docs/PROGRESS.md, docs/DECISIONS.md and continue".

## Phase 1 — in progress (last update 2026-10-14)

Shipped (committed):
- [x] Scaffold, `Document` schema, `PoliteFetcher` (robots, 2 s/host + Crawl-delay, cache,
      block-page detection, form POST cached per body)
- [x] Text utils: clean, langdetect, split (en/id/ms/zh/th), mask; snapshot builder with
      per-(bank, doc_type) redistribution (D8)
- [x] Decisions: BIS rates + holds from meeting dates; MAS stance extractor (gold set pending MAS text)
- [x] Markets: FX (Yahoo), yields US/EA/UK/AU (D9), event windows
- [x] Literature: 33 sources, REVIEW.md, refs.bib, gap table
- [x] Adapters, each with offline tests (≥ 96 % coverage) and `docs/sources/<bank>.md`:
      Fed, ECB, BoE, RBA, BNM, BI (latest index page; history via POST paging in progress),
      BoT (opt-in, 2021→), MAS (manual files, D7), PBoC (manual files, cut from headline, D10)
- [x] `LICENSES.md` per-bank table; `registry.REDISTRIBUTABLE` mirrors it (fail closed)
- [x] CLI: `fetch`, `snapshot` (cache only), `decisions`, `markets`
- [x] FOMC anchor loader (pinned HF revision, CC-BY-NC, evaluation only)
- [x] `docs/ANOMALIES.md` A1–A4

Headline set (D10): Fed, ECB, BoE, RBA, MAS, BI, BNM. Languages en/id/ms (+ th opt-in).
MAS drops out if the manual files are not supplied before `prereg-v1`.

Remaining in Phase 1:
- [ ] BI history via `PoliteFetcher.post` paging (subagent), then `cbtone fetch bi`
- [ ] Full fetch for fed/ecb/boe/rba/bnm/bot (running), then `cbtone snapshot` → data/corpus + VERSION
- [ ] `cbtone decisions`; cross-check meeting dates against bank calendars
- [ ] `cbtone markets`
- [ ] SEA silver-set sampling (200 sentences, BI/BNM/MAS; labels in Phase 3)
- [ ] Full `make test lint`; push

Open issues / decisions not yet in DECISIONS.md:
- MAS (D7) and PBoC (D10): the author either downloads the files in `docs/sources/NEEDED.md` by
  hand or approves Internet Archive copies.
- The events engine spec must key documents with `published_at_utc=None` on the release date (A1).
- BoE: academic re-use permission could be requested to make BoE text redistributable.
- data/raw/boe and data/raw/rba also hold yield files from the markets module (cache keys are URL hashes, so no collision).
