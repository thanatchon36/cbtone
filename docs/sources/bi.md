# Bank Indonesia (BI) source notes

Adapter: `src/cbtone/sources/bi.py` (`BIAdapter`, bank `bi`, languages `id` and `en`).

## Document types
- `statement`: press release ("Siaran Pers" / "News Release") after each Board of Governors
  Meeting (RDG). Policy rate: BI Rate (to Aug 2016), BI 7-Day (Reverse) Repo Rate (Aug 2016 to
  Dec 2023), BI-Rate again from 21 Dec 2023. No minutes or press-conference transcripts are
  collected.

## Languages and pairing
Each release exists as `/en/...` and `/id/...` with an identical slug (`sp_<slug>.aspx`).
The adapter lists one link per decision and emits both language URLs; both documents get
`parallel_id = "bi:<date>:statement"`. A missing translation is served as HTTP 200 with a
"404" page; `parse` returns `[]` (no body). The English and Indonesian texts are separate
translations (paragraph counts can differ slightly, e.g. 17 vs 16 paragraphs on 17 Sep 2025).

## Dates and times
- `date` = decision announcement date from the index table (last day of the meeting, e.g.
  17 Sep 2025 for RDG 16-17 Sep). Page header stamps (`M/D/YYYY h:mm AM/PM`) are used only
  when no hint is given.
- `published_at_utc` = `None`. BI documents no release time. Page stamps differ by language for
  the same release (17 Sep 2025: 8:00 PM en, 2:00 PM id), so they are not trusted. If a rule is
  later found, the zone is `Asia/Jakarta` (WIB, UTC+7, no DST).

## URL patterns
- Index: `https://www.bi.go.id/en/statistik/indikator/BI-Rate.aspx` (table: No, Period, rate,
  Press Release Link; 10 rows per page, newest first). Paging is an ASP.NET postback: the
  adapter GETs page 1 and then `PoliteFetcher.post`s the whole form back (hidden fields incl.
  `__VIEWSTATE`/`__EVENTVALIDATION`/`__REQUESTDIGEST`, plus `<name>.x=5&<name>.y=5` of the
  "Next" image input `...DataPagerBI7DRR$ctl02$ctl00`). It stops when the Next button is
  disabled (last page), a page has no rows, or the oldest row is before `start_year`.
  Live check: 13 pages, 128 rows, 2016-04-21 to 2026-09-23. The Start/End date filter did not
  take effect with a plain POST (dates are set by JavaScript), so it is not used.
- Release: `https://www.bi.go.id/{en,id}/publikasi/ruang-media/news-release/Pages/sp_<slug>.aspx`
  (`SP_` upper case on some 2016-2019 pages; case is kept). Slug eras: `sp_183116` (2016:
  `<ordinal><YY>`), `sp_206618` (2018), `sp_2431322` (2022-23), `sp_2627524` (2024:
  `<year-1998><ordinal><YY>`), `sp_2819326` (2026).
- Fallback: `data/raw/bi/manual/*.htm*` (saved copies of the table, e.g. a differently filtered
  one) are merged with the live rows. No file is required.
- Not used: `.../news-release/default.aspx` (all release kinds, postback paging).
- `?utm...` query strings on shared links are stripped.

## Layout
One layout across 2018-2026: title in `h4#layout-title`; body in
`div.page-description div.ms-rtestate-field` (paragraphs and `ol/li`); page chrome, sidebar,
attachments, contact and "last updated" are outside the body. Cleaning: zero-width spaces
removed, the "No: 27/219/DKom" reference line dropped, signatories after the "Jakarta, <date>"
dateline dropped (footnotes beginning `[` kept), nested list items not duplicated.
Sections have `heading=None` (the releases have no headings). The 2006 IRU archive page
(`/en/iru/email-archive/...`) has a different single-paragraph stub layout and parses as one section.

## Coverage
- Index table: 128 decisions, April 2016 to September 2026 (about 12 per year). Documents
  parsed in tests: 2016-04 (BI Rate era, en/id), 2018-08, 2025-09 (en/id); 2016-06 pages also
  checked live. Expected output: about 256 documents (128 x 2 languages).
- Gap: BI Rate decisions from July 2005 to March 2016 (about 130 meetings) are not in this
  table and no other index was found (probed `/moneter/bi-rate/data/...` guesses: 404 pages).
  Only a few 2006 English stubs exist as IRU archive pages (`/en/iru/email-archive/...`, one
  paragraph, e.g. 2006-09-05). A human could find older release links via the site search or
  the Statistics pages and drop them as saved table HTML in `data/raw/bi/manual/`.
- Releases for 2016-2017 were parsed fine (title, ten paragraphs, reference number
  "No. 18/ 31 /DKom" and the "Communication Departement" signature stripped).

## Politeness
robots.txt: `User-agent: *`, `Allow: /`, no `Crawl-delay`; disallows `/_layouts`, `/Lists`, etc.
Default 2 s interval applies. A full run is 12 index POSTs plus about 256 article requests (about 10 minutes).

## Terms of use
No terms-of-use or copyright page was found on bi.go.id. Page footers read "(c) 2020 Bank
Indonesia"; the whistleblowing site (https://www.bi.go.id/wbsbi/disclaimer1.aspx) states
copyright held by Bank Indonesia, all rights reserved. No licence for reuse is stated.
Source URL checked: https://www.bi.go.id/en/publikasi/ruang-media/news-release/Pages/sp_2721925.aspx
(footer). Redistributable: no (no reuse licence found; ask bicara@bi.go.id before publishing text).
