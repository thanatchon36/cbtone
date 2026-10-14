# BNM source notes

Adapter: `src/cbtone/sources/bnm.py` (`BNMAdapter`, bank `bnm`, English + Malay).

## Document types
- `statement`: the Monetary Policy Statement ("Pernyataan Dasar Monetari") issued on the last day of
  every Monetary Policy Committee (MPC) meeting. One document per meeting per language.
- No minutes, speeches or press conferences are in scope.

## Languages and translation pairing
- `en` and `ms`. The two versions of a meeting share `parallel_id = "bnm:<YYYY-MM-DD>:statement"`.
- The site picks the language from a session cookie. The same path serves both languages; `/ms/-/...`
  and `?languageId=ms_MY` do not work (404 / English). The adapter therefore requests every page
  through the portal's language switch, which sets the language and redirects to the page:
  `https://www.bnm.gov.my/c/portal/update_language?p_l_id=<id>&redirect=<path>&languageId=en_US|ms_MY`
  (`p_l_id` 1515 for the index, 182 for statements). These URLs are the Documents' `url`.
- English and Malay pages of a meeting share the slug `monetary-policy-statement-DDMMYYYY`
  (decision date), so pairing is exact. `parse` reads `<html lang>` as the true language.
- Anomaly: a session-language cookie leaks between plain requests (a plain URL returned Malay after an
  `update_language ms_MY` call), which is why the plain URL is never used.

## Date and release time
- `date` = decision date (the last day of the meeting): from the index/slug, else the header ("3 Nov
  2022", "26 Mei 2004").
- `published_at_utc`: every statement states "Not for publication or broadcast before HHMM on
  <weekday, date>" (Malay: "sebelum jam HHMM pada ..."). That time is taken as the release time in
  `Asia/Kuala_Lumpur` (UTC+8, no DST) and converted. Seen: 1800 (2004, 2010, 2016), 1500 (2020, 2022,
  2026). The Nov 2022 statement confirms: "The Monetary Policy Statement will be released at 3 p.m. on
  the final day of each MPC meeting." No embargo time -> `None`.

## URL patterns
- Index (one static table, all years): `https://www.bnm.gov.my/monetary-stability/opr-decisions`
  (date, change in OPR, new OPR level, "View Statement" link; Malay labels "Lihat Pernyataan").
- Statement: `https://www.bnm.gov.my/-/monetary-policy-statement-DDMMYYYY`. Body is in
  `.journal-content-article`; header in `.article-header` (h2 title, embargo, date).
- Also useful: `https://www.bnm.gov.my/monetary-stability/mpc`. Not used.

## Coverage (2004-05-26 -> 2026-09-03)
141 statements. Documents: 141 `en` + 139 `ms` = 280 (the Malay pages of 2005-12-15 and
2013-07-11 are placeholders, see Anomalies). Index count per year:
2004: 3, 2005: 5, 2006-2009: 8 each, 2010-2025: 6 each, 2026: 5 (to 3 Sep).
OPR decisions began in 2004; holds are included (the index lists every meeting).

## Layout eras
- 2004-2009: whole statement inside one `<p>`, paragraphs separated by `<br><br>`.
- 2010-2020s: one `<p>` per paragraph. From about 2022 the last statement of a year adds a schedule
  table of next-year MPC meetings (caption `<p>` + table) and a "See also" list; 2026 adds a "See
  also: Social Media" line. All of that is dropped, as are the signature and copyright lines.

## Politeness
robots.txt (checked 2026-10-14) disallows only `/view.php?*` (generic agents), plus
`/index.php?` and `/group/guest/` (Googlebot); no `Crawl-delay`; no block page or 403 was seen.
The default 2 s interval is used. A full run is 1 index + 282 page requests (about 10 minutes). No `NEEDED_bnm.md` is required.

## Terms of use
https://www.bnm.gov.my/terms-of-use ("Terms of Use for BNM Website"): "the entire contents of BNM
website are subject to copyright as a collective work under the Malaysian copyright and trademarks
laws"; "User shall not modify, publish, transmit, participate in the transfer or sale, create
derivative works, or in any way exploit or reproduce, any of the content of BNM website, in whole or
in part. User may download material for User's personal use only, provided that it is not for the
purpose of private or commercial gain."; "no copying, redistribution, retransmission, publication or
commercial exploitation of downloaded material will be permitted without the express written
permission of BNM". Each statement ends "(c) Bank Negara Malaysia, YYYY. All rights reserved."
The separate "Terms of Use for BNM Datasets" (https://www.bnm.gov.my/terms-of-use-bnm-datasets)
covers datasets labelled "Source: Bank Negara Malaysia", not these statements (not read here).
Disclaimer: https://www.bnm.gov.my/disclaimer.

Redistributable: no (written permission from BNM is needed to republish the text; keep the
statements out of any published corpus and release derived features only).

## Anomalies (found in the full run)
- Untranslated Malay pages: 2005-12-15 and 2013-07-11 say only "Artikel ini cuma terdapat dalam
  Bahasa Inggeris buat masa sekarang." `parse` returns `[]` (logged), so those meetings have no `ms`
  document and are unpaired.
- 2008-10-24 (en and ms): the page holds two `.journal-content-article` assets, a "Press Releases"
  listing first and the statement second. The adapter takes the one containing `.article-header`;
  if none has it, it logs a warning and returns `[]`.
- 2007-11-26 (en, ms) and 2011-11-11 (en): the whole statement is one `<p>` directly before the
  schedule table; an earlier table-caption rule dropped it. Captions are now only paragraphs of
  at most 150 characters.
- Short but genuine: 2006-01-20 en/ms (491 / 498 characters).
