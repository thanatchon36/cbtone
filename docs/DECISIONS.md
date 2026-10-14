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

## D8 — Redistribution per document type; ECB press conferences committed as URLs + hashes (2026-10-14)
- **What:** `redistributable` is decided per (bank, doc_type). ECB decision press releases ("Reproduction
  is permitted provided that the source is acknowledged") are committed with their text; ECB press
  conferences are committed as URL + SHA-256 only, because the ECB disclaimer requires prior
  authorisation for "documents bearing the names of their authors" and the introductory statement is
  delivered by the named President. `make fetch` rebuilds the full text locally.
- **Why:** when the terms are unclear, choose the reading that can't be a licence breach.
- **Rejected:** committing everything with attribution only.

## D9 — Market coverage: yields only where a free daily official source exists (2026-10-14)
- **What:** 2y/10y yields: US (FRED H.15), EA (ECB AAA curve, 2004-09→), UK (BoE spot-curve archive),
  AU (RBA F2, 2013→). SEA banks: FX only (no login-free daily yield files found). FX from Yahoo via
  `yfinance`, modelled as 17:00 New York closes; the raw FX parquet is not committed (Yahoo terms).
  Event day `t` = the first close strictly after the release in the series' own timezone.
- **Why:** MISSION §1.3; daily windows need daily data; FRED's non-US yields are monthly.
- **Consequence for RQ2:** the yield leg is tested for Fed/ECB/BoE/RBA only; the SEA legs use FX. Pre-registered as such.

## D10 — PBoC cut from the headline set; headline = 7 banks, 3 live languages (2026-10-14)
- **What:** `pbc.gov.cn/robots.txt` disallows every crawler except Baiduspider, so PBoC cannot be
  fetched. `cbtone.sources.pboc` runs in manual-file mode only (files listed in `docs/sources/NEEDED.md`);
  its selectors are unverified against real pages (synthetic fixture). PBoC is removed from
  `config/paper.yaml`. Headline banks: Fed, ECB, BoE, RBA, MAS, BI, BNM. MAS also depends on manual
  files (D7): if they are not supplied before pre-registration (`prereg-v1`), MAS is dropped too and
  the prereg says so. Languages: en (all), id (BI), ms (BNM); th (BoT) opt-in. The MISSION's
  "~8 banks in 4 languages" framing becomes "7 banks (6 if MAS stays blocked), 3 languages + Thai opt-in".
- **Why:** MISSION §0 forbids getting around robots.txt; §7 prefers clean evidence on fewer banks.
  A zh leg built on unverified selectors would be uncheckable.
- **Rejected:** fetching anyway, a Baiduspider User-Agent, third-party mirrors without the author's say-so.
