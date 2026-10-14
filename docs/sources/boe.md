# Bank of England source notes

Adapter: `src/cbtone/sources/boe.py` (`BoEAdapter`, bank `boe`, English only).

## Document types
- `statement`: the MPC decision. Jan 2000 - Jul 2015 the stand-alone press release ("Bank of
  England maintains Bank Rate at ..."); from the August 2015 meeting the "Monetary Policy
  Summary".
- `minutes`: June 1997 - Jul 2015 stand-alone minutes (published about two weeks after the
  decision); from Aug 2015 the "Minutes of the Monetary Policy Committee meeting ending on ..."
  part of the combined publication.
- **Merge date:** the summary and minutes were merged into one publication, released together, from
  the meeting ending 5 Aug 2015 (published 6 Aug 2015). The combined page lives under
  `/monetary-policy-summary-and-minutes/`. The adapter always emits them as two Documents
  (`statement` + `minutes`) so the series stays comparable across the merge.
- Decisions of 1997-1999 have no stand-alone press release page, so `statement` starts in 2000.

## URL patterns
- Index: the site map `https://www.bankofengland.co.uk/_api/sitemap/getsitemap` (listed in
  robots.txt; the visible list pages are JS driven). One request, about 2.5 MB, cached.
- Press release: `/news/YYYY/<month>/mpc-<month>-YYYY` (HTML; a PDF copy sits beside it).
- Minutes 1997-Jul 2015: `/minutes/YYYY/monetary-policy-committee-<month>-YYYY`
  (also `/minutes/YYYY/minutes-<month>-YYYY` in 2003-2005, and one with a day,
  `...-18-september-2001`). The HTML page is a stub (the vote paragraph plus a PDF link); the
  full minutes are the PDF `/-/media/boe/files/minutes/<YYYY>/minutes-<month>-YYYY.pdf` (1999
  under `minutes/1900-2000/1999/`). `list_urls` reads the PDF link off the page and yields the PDF.
- Combined, Aug 2015 on: `/monetary-policy-summary-and-minutes/YYYY/<mpc-><month>-YYYY`
  (plus `13march-2020`, minutes of the special meeting, and a special summary page, 19 Mar 2020).
  PDF: `/-/media/boe/files/monetary-policy-summary-and-minutes/YYYY/<month>-YYYY.pdf`.

## Layout eras
- 2000 - Jul 2015 press releases: short HTML, one or two `<p>` (paragraphs separated by `<br><br>`
  in 2015), a "Notes to Editors" tail, and a PDF link that is dropped.
- 1997 - Jul 2015 minutes: HTML stub; text from the PDF (numbered paragraphs `1 ...`,
  sub-headings as short lines, page footers dropped).
- Aug 2015 - ~2021 combined: the HTML holds the summary only (content may be split over several
  `content-block` divs); the minutes come from the PDF, starting at the line "Minutes of the
  Monetary Policy Committee meeting ending on ...".
- ~2022 onward: the HTML page holds the summary (`h2 "Monetary Policy Summary, <month>"`) and the
  minutes (`h2 "Minutes of the Monetary Policy Committee meeting ending on ..."`, `h3`
  sub-headings, numbered paragraphs "1: ..."). The adapter splits at the minutes `h2`.
  The exact cut-over year was not mapped: the code checks each page for the minutes heading.

## Coverage (site map, counted 14 Oct 2026)
- Press releases `statement` 2000-Jul 2015: about 186 (11-12 per year; 7 in 2015).
- Stand-alone `minutes` 1997-Jul 2015: about 219 (7 in 1997, 12 per year after, 13 in 2001).
- Combined 2015 (Aug-Dec) - 2026: about 95 published pages (8 per year since 2017; 10 in 2020 with
  the special meetings), yielding about 95 `statement` + 95 `minutes`. The site map also lists
  placeholder pages for future meetings (Sep-Dec 2026, all of 2027: "to be published ..."), which
  `list_urls` skips. About 480 documents in total, roughly 500 page and PDF requests.
- Date rule: `statement` date = announcement date; `minutes` date = last day of the meeting
  covered (title "held on 7 and 8 April 1999", "meeting ending 3 June 2015"). Since 2015 that is the
  day before the announcement. Where a page gives no meeting date the day before publication is
  used.

## Release times (`published_at_utc`, zoneinfo `Europe/London`)
- `statement`: 12:00 on the announcement date. Source: press release of 1 Aug 2013 ("the decision
  will still be announced at the originally scheduled time of 12.00 on 5 September"); current pages
  titled "(to be published at 12pm)". Assumed unchanged for 2000-2012.
- `minutes` before 6 Aug 2015: 09:30 on the publication date. Source: press releases of
  1 Aug 2013 and 9 Jul 2015: "The minutes of the meeting will be published at 9.30am on
  Wednesday ..."; the same sentence appears in 2001.
- `minutes` in the combined publication: 12:00 (with the summary).
- Emergency/special meetings (March 2020): `None`.

## Press-release lead (2000-2012)
On the 2000-2012 `/news/` pages the decision sentence ("The Bank of England's Monetary Policy
Committee today voted to maintain ...") is only in the page lead (`div.page-description`), not in
`div.page-content`. The adapter prepends it as the first section when absent from the body, and
drops standalone publication notices ("The minutes of the meeting will be published at 9.30am
...", "The Committee's latest inflation and output projections will appear ...") unless nothing
else remains. Many 2000-2006 releases are therefore just ~100 characters (the decision sentence).

## Coverage fixes (cross-check)
Missing statements were caused by: (1) summaries stored as bare text with `<br><br>` instead of
`<p>` (Sep 2018, Mar/Jun 2019, Nov 2020, May 2021) so no blocks were found and the page was
treated as a placeholder; (2) Dec 2023, where the text sits in sections after the one holding
"Published on" (the whole `main` is now scanned); (3) 2000-2012 releases made only of the page
lead (Sep 2008) being treated as stubs; (4) slugs outside `mpc-<month>-YYYY`: `mpc-septmber-2003`
(typo in the real slug), `mpc-18-september-2001` (emergency cut) and the 11 Mar 2020 emergency
package `/news/2020/march/boe-measures-to-respond-to-the-economic-shock-from-covid-19`
(`EXTRA_STATEMENTS`; emitted with `published_at_utc=None`, as are all special meetings);
(5) 2007 minutes PDFs number paragraphs "1." (the parser now accepts an optional period).
After the fix, the cached 2000-2026 run gives 12 statements and 12 minutes a year for 2000-2015
(13 in 2001 for the 18 Sep 2001 meeting), 11 in 2016, 8 a year 2017-2025 (10 statements and 9
minutes in 2020), 6 so far in 2026. 2020 minutes: the special 19 Mar 2020 meeting has no minutes
page in the site map.

## Known limits
- Some recent minutes PDFs (seen: 2019) are AES-256 encrypted. `pypdf` needs the `cryptography`
  package for them; it is not a project dependency, so `parse` logs a warning and returns `[]` for
  those PDFs. The HTML summary of the same meeting is still produced. Proposed: add
  `cryptography` to `pyproject.toml` (not done here).
- Not mapped: which of the 2017-2021 combined pages already carry the minutes in HTML (handled
  per page); the HTML `Published on` date of a few pages may lag the real release.

## Politeness
robots.txt disallows only `/boeapps/database/ShowChart.asp`, `/boeapps/iadb`, `/boeapps/titan`,
`/error`, `/forms`, `/mfsd`, `/search`, `/test-folder`; no Crawl-delay, so the default 2 s interval
applies. A full fetch is about 500 requests (about 20 minutes). No block was met.

## Terms of use
Source: https://www.bankofengland.co.uk/legal ("Rules for using material from our website").
"Unless otherwise stated, the copyright and any other rights in the contents of the Resources,
including but not limited to images, text and data, are owned by the Governor and Company of the
Bank of England." Users may "download, display or print the Resources for personal use or internal
use within an individual organisation for non-commercial purposes". "The Bank typically grants
permission for non-commercial re-use of the Resources, particularly in an academic or education
context"; further requests go to the Head of Communications Division (enquiries@bankofengland.co.uk).
Where permission is granted the Bank accepts no responsibility for alteration of the material.

Redistributable: no. Public redistribution of the text is not granted by default; ask the Bank in
writing (academic re-use is typically permitted) or share only derived data (scores, labels).
