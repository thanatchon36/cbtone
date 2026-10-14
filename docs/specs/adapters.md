# Spec: source adapters (`src/cbtone/sources/<bank>.py`)

Read first: `MISSION.md` §0 and §1.1, `src/cbtone/schema.py`, `src/cbtone/sources/base.py`.

## Contract

Each adapter is one module `src/cbtone/sources/<bank>.py` defining
`class <Bank>Adapter(SourceAdapter)` with `bank = "<bank>"` and:

- **Class docstring** listing: document types, URL patterns (index + document), date range
  covered, language(s), and a terms-of-use note quoting/linking the bank's copyright/terms page.
- `list_urls(start_year, end_year)` → yields `(url, hints)`. It may fetch index pages **only through
  `self.fetcher.get(self.bank, url)`** (never `httpx` directly: that would skip robots.txt, the rate
  limit and the cache). `hints` is a `dict[str, str]` with at least `doc_type`, `date` (ISO,
  meeting/decision date), `language`; optional `parallel_id`, `title`.
- `parse(raw, hints)` → `list[Document]`. **Pure** (no network). HTML via BeautifulSoup+lxml;
  PDF via `pypdf`. Output clean text: no navigation, footers, share widgets, scripts or
  "last updated" boilerplate. Keep paragraph structure in `sections` (one `Section` per paragraph,
  `heading` set when the source has headings). `text` = `"\n\n".join(section texts)`.
  `sha256` = `raw.sha256`; `fetched_at` = `raw.fetched_at`; `url` = `raw.url`.
- `published_at_utc`: fill when the release time is documented (e.g. FOMC statements 14:00
  America/New_York, 14:15 before 2013 — check, ECB decisions 13:15/14:15 CET depending on era — check);
  record the rule and its source in the module docstring. Otherwise `None`.
- Dates: `date` is the decision/meeting date (for minutes, the meeting they cover, not the
  release date; put release date into `published_at_utc` if known).
- `parallel_id` (multilingual banks only): `"<bank>:<date>:<doc_type>"`, identical across languages.

## Politeness (hard)

- Use only `self.fetcher`. Don't lower `min_interval_s` below 2 s for live runs.
- If robots.txt disallows the needed paths or the host returns 401/403/429 (`BlockedError`), **stop
  for that bank**. Write `docs/sources/NEEDED_<bank>.md` with the exact URLs (or URL patterns and
  index pages) a human can download manually and where to drop them (`data/raw/<bank>/manual/`),
  and make `parse` work on those manual files. Do not try to get around a block.
- Live exploration: use small samples (a handful of pages). Do NOT bulk-download the full history;
  the main session runs the full fetch.

## Deliverables per bank

1. `src/cbtone/sources/<bank>.py` (type-hinted, passes `mypy --strict`, `ruff check`, `ruff format`).
2. `tests/fixtures/<bank>/` — 2–4 **small** real raw samples (trim HTML to the article body region
   if > 200 KB; for PDF keep one short one or save its extracted text instead and test the PDF branch
   on a tiny one) covering each doc type and each era with a different layout.
3. `tests/test_source_<bank>.py` — offline tests using fixtures (construct a `RawResponse` from the
   file); assert: correct date/doc_type/language, non-empty text with ≥ N words, a known sentence
   from the document appears, no boilerplate strings (e.g. "Share", "Last Update", "Skip to main"),
   ≥ 3 sections. Test `list_urls` offline by putting the cached index pages into a temporary
   `PoliteFetcher(raw_dir=..., offline=True)` cache, or with `httpx.MockTransport`.
   One `@pytest.mark.network` live smoke test that fetches ≤ 2 documents.
4. `docs/sources/<bank>.md`: URL patterns, coverage (years × doc types, approximate counts),
   layout eras, release-time rule, terms-of-use summary + link, and whether redistributing the text is
   allowed (quote the clause). Do **not** edit shared files (`LICENSES.md`, `DECISIONS.md`, `base.py`,
   `schema.py`). If you need a change there, describe it in your final report.
5. Final report (≤ 250 words): what's covered, counts estimated from the index pages, known gaps,
   anything blocked, proposed shared-file changes.

Acceptance: `uv run pytest tests/test_source_<bank>.py -q` passes offline;
`uv run ruff check src/cbtone/sources/<bank>.py tests/test_source_<bank>.py` and
`uv run mypy src/cbtone/sources/<bank>.py` are clean. Do not commit; the main session reviews and commits.

## Bank-specific notes

### fed — FOMC
- Statements 1994→ (decisions w/ statements began Feb 1994), minutes (1993→; full history fine but
  ≥ 2000 is sufficient for headline), press-conference transcripts (2011→, PDF).
- Index: `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm` (2020→ roughly the
  last 5 years) and `https://www.federalreserve.gov/monetarypolicy/fomc_historical_year.htm` /
  `fomchistoricalYYYY.htm` for earlier years. Statement URL patterns changed over time
  (`/newsevents/pressreleases/monetaryYYYYMMDDa.htm`, `/boarddocs/press/monetary/YYYY/YYYYMMDD/`).
  Minutes: `/monetarypolicy/fomcminutesYYYYMMDD.htm` and older `/fomc/minutes/YYYYMMDD.htm`.
  Press conf: `/mediacenter/files/FOMCpresconfYYYYMMDD.pdf`.
- Unscheduled/intermeeting statements: include with `hints["unscheduled"]="1"` if visible.
- Terms: US federal government work, public domain (confirm on the site's disclaimer page).

### ecb — ECB
- Monetary policy decisions press releases (`/press/pr/date/YYYY/html/...mp...en.html`) and press
  conferences (introductory statement + Q&A, `/press/press_conference/monetary-policy-statement/...`;
  from 2022 the "monetary policy statement" format). 1999→.
- The ECB site loads lists via JS; use the per-year index pages / sitemaps if they exist
  (e.g. `https://www.ecb.europa.eu/press/pressconf/html/index.en.html`, year includes like
  `/press/pressconf/YYYY/html/index_include.en.html`) — find the static lists.
- Q&A: keep the questions/answers as sections; set `heading="Q&A"` on those, and the introductory
  statement sections with `heading` from the page. Downstream code may score intro only.
- Terms: ECB copyright notice permits reproduction with source acknowledged — verify and quote.

### mas — Monetary Authority of Singapore
- Monetary Policy Statements (doc_type `mps`): semi-annual (Apr/Oct) since 2001 — verify start —
  quarterly from 2024. English. Index: `https://www.mas.gov.sg/monetary-policy` and the MPS
  listing under `/news/monetary-policy-statements`. PDFs and HTML both exist.
- **MAS is known to block automated access.** Probe robots.txt and ≤ 3 pages. On a block, write
  `docs/sources/NEEDED_mas.md` (exact URLs; the main session asks the human to download them) and
  implement `parse` against manually saved HTML/PDF in `data/raw/mas/manual/` (date from the filename
  or the document text).
- **Exchange-rate-based policy**: the stance is a change to the S$NEER policy band's slope, width or
  centre. The adapter only extracts text; the stance extractor lives in `cbtone.decisions` (separate spec).

### bi — Bank Indonesia
- BI Board of Governors meeting press releases (BI Rate up to 2016-08, BI 7-Day (Reverse) Repo Rate
  2016-08 → 2024; renamed back to "BI-Rate" in 2024). **Both id and en**; set `parallel_id`.
  Site: `https://www.bi.go.id/id/publikasi/ruang-media/news-release/` and `/en/...`.

### bnm — Bank Negara Malaysia
- Monetary Policy Statements, **en + ms** (parallel). `https://www.bnm.gov.my/monetary-stability/mpc`
  and press-release listings. OPR decisions 2004→.

### boe — Bank of England
- Monetary Policy Summary + minutes (combined since 2015 "Monetary Policy Summary and minutes"),
  earlier minutes 1997→ and decision press releases. `https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes`.

### rba — Reserve Bank of Australia
- Statements by the Governor on the monetary policy decision (1990→; "Monetary Policy Decision" media
  releases; from 2024 Monetary Policy Board statements) and minutes (2006-10→). `https://www.rba.gov.au/media-releases/`,
  `https://www.rba.gov.au/monetary-policy/rba-board-minutes/`.

### pboc — People's Bank of China (optional if costly)
- MPC quarterly meeting communiqués (货币政策委员会例会) zh, en where available; LPR announcements
  (2019-08→) are formulaic — include but flag `doc_type="other"`. If parsing costs > 1 day, stop and
  report; the main session records the cut in DECISIONS.md.

### bot — Bank of Thailand (opt-in; excluded from headline)
- MPC press releases (th + en, parallel) and edited minutes. Implement like any other bank;
  nothing in docs or code comments may discuss policy choices.
