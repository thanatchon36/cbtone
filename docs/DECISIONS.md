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

## D11 — MAS text from Internet Archive copies (2026-10-14)
- **What:** the author approved Internet Archive (Wayback Machine) copies for MAS (D7 left this to
  the author). `MasAdapter` lists archived Monetary Policy Statement URLs with the Wayback CDX API
  and fetches the raw snapshot (`web.archive.org/web/<timestamp>id_/<mas url>`) through
  `PoliteFetcher`, which applies robots.txt, rate limits, caching and block-page rejection. It never
  requests mas.gov.sg itself. `Document.url` is the snapshot URL, and the original MAS URL is
  recoverable from it. Hand-saved files in `data/raw/mas/manual/` still take precedence.
- **Checks:** a snapshot is accepted only if it is a 200 capture of a statement page whose parsed date
  matches the date in its slug. Captures that show the MAS "Maintenance" page are skipped, and the
  next capture of that URL is tried instead.
- **Licence:** unchanged. MAS terms require permission to redistribute, so MAS stays URL + SHA-256 only.
- **Why:** MAS is the only headline SEA bank with an exchange-rate-based framework, and MISSION §0 lists public
  mirrors as allowed. The author made the call on the bank's own access choice.
- **Not extended to PBoC:** PBoC remains manual-only (D10) unless the author says otherwise.

## D12 — PBoC text from Internet Archive copies (author-approved, 2026-10-14)
- **What:** the author approved Wayback Machine copies for PBoC as well. `PbocAdapter` gets the same
  archive mode as MAS (D11): it lists captures with CDX and fetches `id_` raw snapshots via
  `PoliteFetcher`, never pbc.gov.cn. `Document.url` is the snapshot URL, and hand-saved files take
  precedence. Captures are accepted only when the parsed meeting date matches, and block or empty
  pages are skipped.
- **Note:** unlike MAS (a bot page; robots.txt allowed crawling), pbc.gov.cn's robots.txt disallows
  crawlers. The archive's copies are a public mirror (MISSION §0), and the author made the call on the bank's
  stated crawler policy. cbtone itself still never crawls pbc.gov.cn.
- **Headline:** amends D10. PBoC rejoins the headline set (8 banks, 4 languages) only if the archive
  yields ≥ 80 % of MPC communiqués from 2010 onward *and* the selectors validate on real archived pages.
  Otherwise it stays an optional extension. This is decided and recorded before `prereg-v1`.
- **Licence:** terms unverified, so treated as not redistributable (URL + SHA-256 only).

## D13 — MAS stance gold labels come from MAS's published decision table (2026-10-14)
- **What:** the 20-row gold set for the MAS stance extractor takes `label_direction` and
  `label_parameters` from MAS's "past monetary policy decisions" table (archived copies, D11),
  not from hand labelling. Paragraphs are verbatim from the archived statements. #20 (27 Jul 2026,
  no usable capture) is replaced by 12 Oct 2018.
- **Why:** no human labeller is available, and an LLM reading the paragraph would not be
  "hand labels". The bank's own record of each decision is authoritative and independent of the extractor.
- **Rejected:** labels made by the session model (would be silver, not gold, and correlated with the extractor's design).

## D14 — MAS decisions come from MAS's own table; the text extractor is a fallback (2026-10-14)
- **What:** `decisions.parquet` takes MAS rows (`source="mas_table"`) from MAS's "Past Monetary
  Policy Decisions" table, using the newest usable Internet Archive capture (currently 2025-11-18, 59 decisions
  from 2001-02-22 to 2025-10-14; `*` = unscheduled). The rule-based extractor (`source="mas_text"`) is used only for
  statements dated after the table's last row.
- **Why:** validation showed the extractor is not reliable enough to be the primary source.
  - Before any fix: 15/19 on gold decision paragraphs, and 21/40 (53 %) on the full text of the
    other 40 table-covered statements.
  - After four general grammar fixes (passive voice; "has therefore decided"; month-year
    back-references; "from zero … to"): 20/20 gold, 31/40 (78 %) full text.
  - Both sets were used to design those fixes, so **no untouched test set remains**. The figures are
    development accuracy, not validation.
  - The bank's own record is authoritative, and the extractor is not needed where that record exists.
- **Consequence:** at most a handful of post-table MAS decisions rely on the extractor. They are
  flagged by `source` and reported separately. The extractor's limits go into the paper's Threats to Validity.

## D15 — PBoC stays out of the headline set: archive coverage is 53 % (2026-10-14)
- **Result of the D12 rule:** the Internet Archive yields 35 of 66 expected zh MPC communiqués
  for 2010–2026Q3 (53 %, below the pre-set 80 %), plus 16 en (2021→). From May 2016 to about 2022 every
  capture is an anti-bot JavaScript shell with no text. Selectors are now validated on real archived pages
  (three zh layouts, en).
- **Decision:** PBoC remains an optional zh extension, not in `config/paper.yaml`. Headline = 7 banks,
  3 languages (D10). Any PBoC result is reported as exploratory, with the 2016–2022 gap stated.
- Meeting dates for 2009–15 come from PBoC's own meeting-date table (archived): the pages say only
  "日前" ("recently").
