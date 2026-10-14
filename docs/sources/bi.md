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
- Index: `https://www.bi.go.id/en/statistik/indikator/BI-Rate.aspx` (table: No, Period,
  BI-Rate, Press Release Link; 10 rows per page, postback paging; see `NEEDED_bi.md`).
- Release: `https://www.bi.go.id/{en,id}/publikasi/ruang-media/news-release/Pages/sp_<slug>.aspx`.
  Slug eras: `sp_206618` (2018: ordinal+YY), `sp_2431322`/`sp_2528323` (2022-23),
  `sp_2627524` (2024: `<year-1998><ordinal><YY>`), `sp_2819326` (2026).
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
- Index table: every RDG decision from July 2005 (about 250 rows, about 25 pages), page 1 live.
- Documents verified: 2018-08 (en, id), 2025-09 (en, id), plus 2024 and 2026 pages seen in the
  cache. Pre-2018 release links (BI Rate era, 2005-2016) are unverified: ask the table's links.
  Counts expected: about 12 releases per year x 2 languages.

## Politeness
robots.txt: `User-agent: *`, `Allow: /`, no `Crawl-delay`; disallows `/_layouts`, `/Lists`, etc.
Default 2 s interval applies. A full run is about 500 article requests (about 17 minutes).

## Terms of use
No terms-of-use or copyright page was found on bi.go.id. Page footers read "(c) 2020 Bank
Indonesia"; the whistleblowing site (https://www.bi.go.id/wbsbi/disclaimer1.aspx) states
copyright held by Bank Indonesia, all rights reserved. No licence for reuse is stated.
Source URL checked: https://www.bi.go.id/en/publikasi/ruang-media/news-release/Pages/sp_2721925.aspx
(footer). Redistributable: no (no reuse licence found; ask bicara@bi.go.id before publishing text).
