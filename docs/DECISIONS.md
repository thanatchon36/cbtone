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

## D6 — Policy-rate decisions from BIS WS_CBPOL (2026-10-14)
- **What:** rate changes come from the BIS daily policy-rate series (1999→); holds come from meeting
  dates (statement/MPS documents) with no change within +3 days (ECB +7 days, because changes take
  effect up to about 6 days after announcement). The US is reported as the upper bound of the target
  range (BIS midpoint + 12.5 bp from 2008-12-16). For the euro area, BIS switches from the main
  refinancing rate (MRO) to the deposit facility rate (DFR) on 2024-09-18; the -60 bp step there is
  replaced by the observed 25 bp DFR cut, and the switch is documented. Changes below 0.5 bp are
  treated as rounding noise.
- **Why:** one public, consistent source for all rate-setting banks; the meeting calendars come from
  our own corpus, so they cross-check it.
- **Rejected:** scraping each bank's rate-history page (different formats, and the BIS series is the
  better-documented public standard).

## D7 — Bot-protection pages served with HTTP 200 count as blocked (2026-10-14)
- **What:** `PoliteFetcher` treats HTML whose `<title>` matches maintenance/captcha/access-denied
  interstitials as `BlockedError` and never caches it. MAS (www.mas.gov.sg) serves an ~850 KB
  "Maintenance" page to the cbtone User-Agent while robots.txt allows crawling, so MAS is treated as
  blocked; the URLs are listed in `docs/sources/NEEDED.md` for manual download.
- **Why:** an earlier project silently produced a 0 % rate from bad input; caching a block page as a
  "document" would be the same failure. MISSION §0 forbids getting around a block.
- **Rejected:** retrying with a browser User-Agent or a headless browser (that gets around the block); using
  the Internet Archive's copies of MAS pages without the author's say-so (an allowed "public mirror"
  under §0, but it would get around the bank's own access choice, so it's left to the author).
