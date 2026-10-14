# MAS - Monetary Authority of Singapore

- **Status:** www.mas.gov.sg serves an HTTP 200 "Maintenance" bot page to the polite fetcher (D7), so
  `cbtone.sources.mas` **never requests mas.gov.sg**. Since D11 (author-approved) it reads
  Internet Archive (Wayback Machine) copies, plus any hand-saved files in `data/raw/mas/manual/`.
- **Doc type:** Monetary Policy Statement (2001->; semi-annual, quarterly from 2024, plus off-cycle).
- **Language:** en.
- **Date:** from the slug (`...-DDmonYY`, `...-DD-mon-YY`, `...-DD-mon-YYYY`, `mps-YYYY-MM-DD`), else
  from the statement text.
- **Release time:** not documented; `published_at_utc=None`. MAS statements are usually released at
  08:00 SGT before the market opens, but that is not verified, so event windows use day-level timing.
- **Terms of use** (https://www.mas.gov.sg/terms-of-use): prior written permission is needed to
  reproduce or distribute content, apart from a personal, non-commercial single copy.
  **Redistributable: no.** Commit the URL and SHA-256 only.

## Internet Archive mode (D11)

`MasAdapter.fetch(start, end)`:

1. loads manual files first (they take precedence by statement date);
2. lists archived statement URLs with the Wayback CDX API (`PoliteFetcher.get`, cached under
   `data/raw/mas/`): prefix queries for `www.mas.gov.sg/news/monetary-policy-statements/`, the bare
   `mas.gov.sg` host, and the old `/news-and-publications/monetary-policy-statements...` paths
   (`/en/` too), `filter=statuscode:200`, `collapse=urlkey`;
3. keeps only statement URLs: `/news/monetary-policy-statements/YYYY/<slug>` where the slug holds a
   date in the same year, or the 2012-13 `.aspx` layout `.../Monetary-Policy-Statement-12Oct12.aspx`.
   Index and listing pages, `/-/media/` assets, query/tracking variants, garbled URLs and slugs
   without a date (e.g. `2005/mas-press-statement`) are dropped;
4. fetches the raw snapshot `https://web.archive.org/web/<ts>id_/<mas url>` (latest capture first).
   If it is a "Maintenance" page (rejected by `PoliteFetcher`), an HTTP error, not a statement, or
   its date differs from the slug, the other captures of that URL are tried (CDX
   `collapse=digest`, next-older first, then newer, at most 8);
5. accepts a capture only if the date parsed from the page equals the slug date (if the text has no
   day, as in Apr 2008, the month and year in the title must match); one document per date;
6. `Document.url` is the snapshot URL (the MAS URL is the part after `id_/`).

robots.txt or an HTTP 401/403/429 from archive.org stops the run (`BlockedError`); it is not
worked around. web.archive.org has no robots.txt (404), the fetcher interval is 2 s, no
parallelism. `use_archive=False` gives manual-only mode.

## Coverage (live run 2026-10-14: `uv run cbtone fetch mas --start 2001 --end 2026`)

62 statements, Feb 2001 to Apr 2026. Every decision in MAS's own "past monetary policy decisions"
table (archived 31 Mar 2020, 2001 to Mar 2020) is present, with matching dates; 2020-10 onward
matches the expected April/October (+ off-cycle Jan 2022, Jan 2025; quarterly from 2024) cadence.

| Year | n | Dates |
|---|---|---|
| 2001 | 4 | 22 Feb, 10 Apr (a short "reaffirms" notice), 12 Jul, 10 Oct |
| 2002 | 2 | 2 Jan, 11 Jul |
| 2003 | 3 | 2 Jan, 10 Jul, 10 Oct |
| 2004-2007 | 2 each | Apr, Oct |
| 2008 | 2 | 10 Apr, 10 Oct |
| 2009-2014 | 2 each | Apr, Oct |
| 2015 | 3 | 28 Jan, 14 Apr, 14 Oct |
| 2016-2019 | 2 each | Apr, Oct |
| 2020 | 2 | 30 Mar, 14 Oct |
| 2021 | 2 | 14 Apr, 14 Oct |
| 2022 | 4 | 25 Jan, 14 Apr, 14 Jul, 14 Oct |
| 2023 | 2 | 14 Apr, 13 Oct |
| 2024 | 4 | 29 Jan, 12 Apr, 26 Jul, 14 Oct |
| 2025 | 4 | 24 Jan, 14 Apr, 30 Jul, 14 Oct |
| 2026 | 2 | 29 Jan, 14 Apr |

Notes: the old NEEDED.md guesses for 2002-03 (Apr/Oct) were wrong; the real 2002-03 decisions were
2 Jan 2002, 11 Jul 2002, 2 Jan 2003, 10 Jul 2003 and 10 Oct 2003. Several July slug dates differ from
the old guesses (26 Jul 2024, 30 Jul 2025). No statement exists only as a PDF in the archive
listing (a PDF query found only survey, SORA and monograph PDFs), so none was taken.

**Missing** (listed in `docs/sources/NEEDED.md` for manual download):
- 2026-07-27: every archived capture (4, Jul-Sep 2026) is the "Maintenance" page.
- 2026-10-14: no archived copy yet.

Layout eras seen (all parse with the same selectors): 2001-2003 (numbered paragraphs, date line first),
2004-2014, 2015 (`1.` numbering), 2016-2025 (current site). 2012-13 also have an older `.aspx`
URL; the new-layout URL is preferred and de-duplicated by date. The Apr 2008 text carries no full
date, hence the title fallback.

## Fixtures

`tests/fixtures/mas/`: real, trimmed (scripts/styles removed, < 150 KB) archived captures
`snapshot-2001-02-22.html`, `snapshot-2008-04-10.html`, `snapshot-2025-10-14.html`, a real archived
"Maintenance" page `snapshot-maintenance.html`, and `cdx-prefix-sample.json` (real CDX rows plus one
synthetic PDF row). `mas-monetary-policy-statement-13oct23.html` and `undated-page.html` are
synthetic manual-file fixtures.
