# Fed (FOMC) source notes

Adapter: `src/cbtone/sources/fed.py` (`FedAdapter`, bank `fed`, English only).
Tests: `tests/test_source_fed.py` (offline, fixtures in `tests/fixtures/fed/`).

## URL patterns
- Index pages (static HTML, fetched through `self.fetcher`):
  - `https://www.federalreserve.gov/monetarypolicy/fomchistoricalYYYY.htm` for each year
    1993-2020: one `div.panel` per meeting or conference call; the `<h5>` heading
    (e.g. `June 30-July 1 Meeting - 1998`, `January 21 Conference Call - 2008`) gives the
    meeting date (last day of the meeting); anything other than "Meeting" is flagged unscheduled.
  - `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm` for 2021 onwards (fetched
    once): `div.fomc-meeting` rows under `<h4>YYYY FOMC Meetings</h4>`; a day cell such as
    `17-18*` or `15 (notation vote)` -> last day; "notation" -> unscheduled.
- `statement` (links labelled "Statement" or "HTML"; PDF and "Implementation Note" are skipped):
  `/fomc/YYYYMMDDdefault.htm` (1994-97), `/boarddocs/press/{general|monetary}/YYYY/YYYYMMDD/`
  (1998-2005), `/newsevents/press/monetary/YYYYMMDD[a-z].htm` (2006-12),
  `/newsevents/pressreleases/monetaryYYYYMMDD[a-z].htm` (2013+).
- `minutes`: `/fomc/MINUTES/YYYY/YYYYMMDDmin.htm` (1993-94), `/fomc/minutes/YYYYMMDD.htm`
  (1995-2007, first meeting day in the name), `/monetarypolicy/fomcminutesYYYYMMDD.htm` (2008+).
  `date` is the index meeting date; the "(Released ...)" date goes into `hints["released"]`.
- `press_conference`: `/mediacenter/files/FOMCpresconfYYYYMMDD.pdf` (the index links the HTML
  wrapper `/monetarypolicy/fomcpresconfYYYYMMDD.htm`, which the adapter rewrites to the PDF). The
  January 2026 calendar row spells the wrapper `fomcpressconf20260128.htm` (a typo on the Fed's
  page); the adapter accepts both spellings. The PDF URL is built from the date and has only been
  checked against the 2013 fixture's pattern; verify on the first live run for 2026.
- Hints: `doc_type`, `date`, `language="en"`; optional `unscheduled="1"` (intermeeting calls and
  notation votes), `released` (ISO, minutes), `has_presser="1"` (statement on a press-conference day).
- robots.txt: `https://www.federalreserve.gov/robots.txt` returns 404 (checked 2026-10), so the
  fetcher treats everything as allowed; no Crawl-delay. Keep the default 2 s interval.

## Coverage
Statements 1994 -> present (1994-98 are short "Chairman announced today" notices; full statements
from 1999), minutes 1993 -> present, press-conference transcripts April 2011 -> present. The
Fed's years x types, approximate counts (about 8 scheduled meetings per year, plus 1-6 unscheduled
calls in some years): about 330 statements (incl. about 40 unscheduled), about 270 minutes
(one per scheduled meeting; minutes of intermeeting calls are appended to the next meeting's
minutes and de-duplicated, preferring the scheduled panel), about 125 press conferences
(about 4 per year 2011-2018, 8 per year since 2019). Estimates, not counted from live indexes.
A meeting without a linked statement (e.g. some 1990s panels) simply yields fewer items.

## Layout eras (HTML text extraction)
- 1994-1997: table-less legacy HTML ("Chairman X announced today ..."), no release time.
- 1998-2005: `boarddocs` pages; footer `Last update: <date>, h:mm AM/PM` and `Release Date:` line.
- 2006-2012: modern template with uppercase `<P>` tags.
- 2013+: `#article` container, headings via bold/`<strong>` blocks.
- Minutes: long documents with bold section headings ("Committee Policy Action", all-caps
  headings pre-2008); attendee lists are kept as unheaded sections.
Boilerplate dropped: nav/footer/forms/scripts, `lastUpdate`, `share`, "Release Date", "For immediate
release", "Return to text", footnote blocks, title/date banner lines, "Implementation Note" lines.
Press-conference PDFs: page headers/numbers removed; sections before the Chair speaks have no
heading, the Chair's opening remarks `heading="Introductory statement"`, everything after the
first non-Chair speaker `heading="Q&A"` (speaker labels like `CHAIRMAN BERNANKE.` are kept in text).

## Release times (`published_at_utc`, America/New_York)
- Statements: 14:00 ET from 2013-01-01 (the Fed's press-conference pages state e.g. "FOMC Meeting
  Statement (Released March 20, 2013 at 2:00 p.m.)"); 14:15 ET for scheduled statements
  1999-01-01..2012-12-31 (legacy footers read e.g. "Last update: November 17, 1998, 2:15 PM"; if
  a legacy footer time is on the page's own release date it is used directly).
  `None` for: unscheduled statements, 1994-98 pages without a footer time, and statements on
  press-conference days April 2011..2012 (released about 12:30 ET; not guessed).
- Minutes: 14:00 ET on the printed release date from 2005-01-01; earlier releases use the page
  footer time if present (e.g. 2003: "Last update: March 20, 2003, 2:00 PM"), else `None`.
- Press-conference transcripts: `None` (no posting time is published).
The 14:15 rule is documented but not independently verified for every pre-2013 meeting; downstream
event-window code should treat it as +/- 15 minutes.

## Politeness
About 33 index requests (one per year 1993-2020 plus the calendar page) and about 700 document
requests for the full history; at 2 s per request this is roughly 25 minutes.

## Terms of use
Source: https://www.federalreserve.gov/disclaimer.htm (section "Copyright/trademark"; reached via
the "Website Policies" footer link, https://www.federalreserve.gov/website-linking-policies.htm;
read 2026-10-14). Quote: "Unless otherwise indicated, information on Board's website is in the
public domain and may be copied and distributed without permission. Please cite to the Board as the
source of the information." Carve-outs: material identified as associated with a non-Board source
(copyright or trademark) needs that source's permission, and Board seals/logos are protected by
federal law (not text content). FOMC statements, minutes and transcripts are Board works with no
such marking in the fixtures.

Redistributable: yes (public domain; cite the Federal Reserve Board as the source, and keep
the original URL per document, which `Document.url` does). Flag in LICENSES.md that only the
FOMC text is claimed, not logos or third-party graphics.
