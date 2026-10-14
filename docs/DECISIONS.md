# Design decisions

Each entry: **what**, **why**, **alternatives rejected**. Newest at the bottom.

## D1 — Packaging and toolchain (2026-10-14)
- **What:** `uv` + hatchling, Python ≥ 3.11, `src/` layout, PyPI name `cbtone`, Apache-2.0,
  core deps kept small (pydantic, typer, polars, httpx, bs4/lxml, pypdf, pyyaml); heavy stacks
  (`torch`, `transformers`, `peft`, `anthropic`) in extras.
- **Why:** `pip install cbtone` must work on a laptop without pulling torch; all deps have arm64 wheels.
- **Rejected:** PyMuPDF for PDFs (AGPL clashes with Apache-2.0 redistribution); poetry (uv is faster
  and already the house standard).

## D2 — Polite fetcher is the only network path (2026-10-14)
- **What:** `PoliteFetcher` enforces robots.txt, ≥ 2 s per host, a descriptive User-Agent, and
  caches raw bytes + sidecar JSON (url, content type, SHA-256, fetched_at) under `data/raw/<bank>/`.
  401/403/429 → `BlockedError`; the adapter stops and writes `docs/sources/NEEDED_<bank>.md`.
- **Why:** MISSION §0; makes every downstream step offline-reproducible from the cache.
- **Rejected:** headless browser or retries with other user agents for blocked sites: that would be
  getting around the block.

## D3 — `Document.date` is the decision/meeting date (2026-10-14)
- **What:** for minutes and transcripts, `date` = the meeting the document belongs to; the release
  time goes into `published_at_utc`.
- **Why:** joins to `decisions.parquet` on (bank, date); the market event uses the release time.
- **Rejected:** keying by release date (minutes come out about 3 weeks later and would join to the wrong decision).

## D4 — Raw cache bodies git-ignored, sidecars committed (2026-10-14)
- **What:** `data/raw/**/*.bin` ignored; `.json` sidecars (URL + hash) committed.
- **Why:** MISSION §0, "commit only URLs + hashes" when the terms forbid redistribution; the sidecars are
  enough to verify a re-fetch. The text goes into `data/corpus/` only where the terms allow it.

## D5 — Non-commercial anchor data are evaluation-only (2026-10-14)
- **What:** the FOMC hawkish/dovish set and FOMC-RoBERTa are CC-BY-NC-4.0. cbtone downloads them at run
  time, uses them for evaluation and as a scorer, and never redistributes them or trains released
  weights on them.
- **Why:** MISSION §1.4; Apache-2.0 users may be commercial.
- **Rejected:** vendoring the CSVs in `tests/fixtures` (that would be redistribution). Tests use a 5-row synthetic
  stand-in with the same schema.
