# RBA source notes

Adapter: `src/cbtone/sources/rba.py` (`RBAAdapter`, bank `rba`, English only). Pure static HTML;
no blocking observed (robots.txt only disallows `/assets/`, `/search/`, `/s/`, image library; no
Crawl-delay), so no manual-file mode and no `NEEDED_rba.md`.

## Document types
- `statement`: media release announcing each monetary-policy decision. Titles: "Statement by the
  Governor, Mr ...: Monetary Policy [Change]" (1990-2007), "Statement by <Governor>: Monetary
  Policy" (2007-2023), "Statement by the Reserve Bank Board: Monetary Policy Decision" (2024),
  "Statement by the Monetary Policy Board: Monetary Policy Decision" (2025-; the Monetary Policy
  Board was established 1 March 2025, the Reserve Bank Board's last meeting was 18 Feb 2025).
  Before Dec 2007 a release was issued only when the cash rate target changed; since then after
  every meeting (8 a year since 2024; 11 a year 2008-2023).
- `minutes`: minutes of the monetary-policy meeting (Reserve Bank Board to Feb 2025, then the
  Monetary Policy Board), published two weeks after the meeting; first published Dec 2007 with
  back-minutes from Oct 2006. Attendance lists (headings "Present", "Members participating",
  "Others participating"), the "Minutes approved" line, venue/date line and endnotes are dropped.
- `press_conference`: transcript of the Governor's media conference after the decision (from
  6 Feb 2024; 3:30 pm, not stated on the page). First speech part is the opening statement
  (`heading=None`); each later paragraph is `heading="Q&A"` with text `"Speaker: ..."`.
  Audio/video are not collected.

## URL patterns
- Index (static, one per year, `ul.list-articles`):
  - `https://www.rba.gov.au/monetary-policy/int-rate-decisions/YYYY/` (1990-; years without a change
    before 2008, e.g. 1995, say "There was no change in the cash rate" and have no list)
  - `https://www.rba.gov.au/monetary-policy/rba-board-minutes/YYYY/` (2006-)
- Statement: `/media-releases/YYYY/mr-YY-NN.html`.
- Minutes: `/monetary-policy/rba-board-minutes/YYYY/DDMMYYYY.html` (2006, PDF twins alongside),
  `.../YYYY/YYYY-MM-DD.html` (later). The date in the URL is the meeting (decision) day.
- Media conference: `/speeches/YYYY/mc-gov-YYYY-MM-DD.html`, discovered from the "More on the ...
  decision" tiles on each statement page (fetched while listing; cached).

## Coverage
Years x types (counts from cached indexes; 2008-2023 is 11 decisions a year, 8 since 2024):
- `statement`: 1990-2026, about 6 per year in 1990, 4 in 2000, 3 in Dec 2007, 11 per year 2008-2023,
  8 per year 2024-; roughly 300 documents, ~270 on the 2.30 pm era.
- `minutes`: Oct 2006-2026, 3 in 2006, then 8-13 per year; about 190.
- `press_conference`: Feb 2024-2026, one per decision; about 20.
A full run costs about 37 + 21 index pages plus ~500 documents at one request / 2 s.

## Layout eras
- 1990-2007 statements: `div[itemprop=text]` with `<p>` and `<ul><li>` bodies; enquiries box dropped.
- 2008-2023: same, with `<section>` wrapper; Governor name changes (Stevens, Lowe, Bullock).
- 2023-: `rss-mr-*` classes; 2024+ adds `<h2>` sub-headings (kept as `Section.heading`) and a
  "related contents" aside (dropped). 2026 pages embed `datetime="2026-09-29T14:30+10:00"`.
- Text uses cp1252 numeric entities (`&#146;`), mapped to Unicode quotes.

## Dates and release times (`published_at_utc`, `Australia/Sydney`)
- `date` is the meeting day. Pre-2008 releases came the morning after the meeting ("at its meeting
  yesterday"), so these are dated one day before the page date.
- Statements from 2008: 14:30 Sydney time. Source: "Decisions regarding monetary policy are made
  by the ... Board and explained in a media release announcing the decision at 2.30 pm after each
  Board meeting. (Prior to December 2007, media releases were issued only when the cash rate target
  was changed.)" (https://www.rba.gov.au/monetary-policy/int-rate-decisions/). If the page carries
  a timestamped `datetime` it takes precedence. Earlier statements (morning releases), minutes and
  press conferences: `None`.

## Politeness
Fetcher defaults (2 s). A full run is about 520 document requests plus indexes (about 20 min).

## Terms of use
Source: https://www.rba.gov.au/copyright/ ("Copyright and Disclaimer Notice"). Key clause: "With
the exception of Third Party Material, all RBA Material, including ... is the copyright of the
RBA. With exception of the Excluded Material, all RBA Material is provided under a Creative
Commons Attribution 4.0 International License (CC BY 4.0 Licence) and may be used in accordance
with the terms of that licence. The materials covered by this licence may be reproduced, published,
communicated to the public and adapted provided that the RBA is properly attributed." Excluded:
RBA logo, banknote images, third-party material, the Cash Rate and financial data (separate
terms in sections 4-5), econometric models, multimedia (audio/video such as the media-conference
recordings). Media releases, minutes and transcripts are plain RBA text, so CC BY 4.0 applies.
Attribution to give: "Source: Reserve Bank of Australia" with a link and a note if adapted.

Redistributable: yes (CC BY 4.0, attribution required; do not redistribute audio/video).
