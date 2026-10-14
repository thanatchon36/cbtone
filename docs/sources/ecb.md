# ECB source notes

Adapter: `src/cbtone/sources/ecb.py` (`EcbAdapter`, bank `ecb`, English only).

## URL patterns
- Index fragments (static; the visible list pages load them with JS via `data-snippets`), one per year,
  entries are `<dt isoDate="YYYY-MM-DD">` + `<dd>` pairs:
  - 1999-2024:
    - `https://www.ecb.europa.eu/press/pressconf/YYYY/html/index_include.en.html`
    - `https://www.ecb.europa.eu/press/pr/date/YYYY/html/index_include.en.html`
    - From about 2022 the press-conference include also lists the decision press release; the pr/date
      include lists the conference under an alias path (`/press/pressconf/YYYY/html/...`), which the
      adapter de-duplicates.
  - From 2019 the 2025+ mopo include below is also read for these years: the 2024 pr/date include is
    nearly empty and the pressconf one omitted the 7 Mar 2024 decision release (found via mopo).
  - 2025 onward (the old two return 404; discovered from `data-snippets` on
    `/press/govcdec/mopo/html/index.en.html` and
    `/press/press_conference/monetary-policy-statement/html/index.en.html`):
    - `https://www.ecb.europa.eu/press/press_conference/monetary-policy-statement/YYYY/html/index_include.en.html`
    - `https://www.ecb.europa.eu/press/govcdec/mopo/YYYY/html/index_include.en.html`
    - Neither is complete alone (the mopo include misses some HTML conferences, the statement include
      misses some decisions), so both are read and merged. They also list combined PDFs and
      "Meeting of ..." accounts (ignored), and the 2025 includes carry early-2026 items (filtered by year).
  - A year whose index returns 404 is skipped with a logged warning; other HTTP errors still raise.
- `statement`: `/press/pr/date/YYYY/html/prYYMMDD.en.html` (1999-2021),
  `ecb.mpYYMMDD~<hash>.en.html` (2022+). Title "Monetary policy decisions"
  ("Decisions on ECB interest rates" in Jan-Feb 1999).
- `press_conference`: `/press/press_conference/monetary-policy-statement/YYYY/html/isYYMMDD.en.html`
  (`ecb.isYYMMDD~<hash>` from ~2020).

## Coverage (1999 -> present)
Approximate counts (from sampled indexes, 1999/2003/2009/2016/2023): about 300 `statement`
(1999-2000 had two decision releases per month) and about 290 `press_conference`
(about 11-12 per year to 2014, 8 per year since 2015). Excludes combined-PDF
("Combined monetary policy decisions and statement"), podcasts, and extraordinary non-monetary releases.

## Layout eras
- 1999-2003: press release has `div.ecb-pressContentPubDate` and an `orderedlist` div; conference
  Q&A in a second `div.section` that starts with a `div.titlepage`.
- 2004-~2013: Q&A in `main > div.appendix`; questions start "Question:".
- ~2014-2019: one `div.section`; Q&A follows "We are now at your disposal for questions".
- 2020+: `a#qa` anchor (not always present); h2 sub-headings in the intro (2022+); unlabeled questions.
Q&A detection order: `#qa` anchor, 1999 titlepage / 2004 appendix, "at your disposal / ready to take
questions", first "Question" paragraph. Q&A sections get `heading="Q&A"`.

## Release times (`published_at_utc`)
- To 20 Jul 2022: decisions 13:45, press conference 14:30 (Frankfurt time, "CET").
- From 21 Jul 2022: decisions 14:15, press conference 14:45.
Source: ECB press release 27 June 2022, "New times for ECB's monetary policy decisions and press
conference": "monetary policy decisions will be published at 14:15 CET (instead of 13:45). The press
conferences will begin at 14:45 CET (instead of 14:30)."
(https://www.ecb.europa.eu/press/pr/date/2022/html/ecb.pr220627~73acedf868.en.html). Each decision
release also states the conference time ("press conference starting at 14:30 CET today";
"2.30 p.m." in 1999). Zone used: `Europe/Berlin` (IANA has no `Europe/Frankfurt`; identical rules).
Statements are timestamped only when the release announces a press conference.

## Politeness
robots.txt has `Crawl-delay: 5`; the adapter raises the fetcher interval to 5 s. A full fetch is
about 54 index (2 per year) + 600 document requests (about 1 hour).

## Terms of use
https://www.ecb.europa.eu/services/disclaimer/html/index.en.html: "Subject to the exception below,
users of this website may make free use of the information obtained directly from it subject to the
following conditions: When such information is distributed or reproduced, it must appear accurately
and the ECB must be cited as the source." Modified data must be flagged as modified. Exception:
"any reproduction, publication or reprint, in whole or in part, of documents that bear the name of
their authors, such as ECB Working Papers and ECB Occasional Papers, in the form of a different
publication ... is permitted only with the explicit prior written authorisation". Press releases
carry "Reproduction is permitted provided that the source is acknowledged."
Redistribution of the text with attribution is allowed; the authored-document exception arguably
touches the named-speaker introductory statements, so keep attribution and flag this in LICENSES.md.
