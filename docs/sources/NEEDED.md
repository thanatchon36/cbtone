# NEEDED: files a human must download by hand

Consolidated manual-download list. Automated access is blocked or unavailable for the sources
below (MISSION section 0; DECISIONS D7), so the author saves the pages in a normal browser.
Nothing here asks the pipeline to get around a block.

## MAS - Monetary Policy Statements (2001 to Oct 2026)

`www.mas.gov.sg` returns a ~850 KB "Maintenance" bot-protection page (HTTP 200) to the polite
fetcher (robots.txt itself allows crawling, Crawl-delay 2), so MAS is treated as blocked.

### How to
1. Open each URL below in your browser and save the page (File > Save Page As > "Webpage, HTML
   only" or "Complete"; or print to PDF) into `data/raw/mas/manual/`.
2. Keep the slug (the last path segment) as the file name, e.g.
   `mas-monetary-policy-statement-13oct23.html`. `mps-YYYY-MM-DD.html` also works. Do not rename
   to anything without a date; if you must, the date is read from the statement text.
3. Run `uv run cbtone fetch mas`; it loads every `.html`/`.htm`/`.pdf` in that folder.

### Slug patterns
- 2004-2014: `monetary-policy-statement-DD-mon-YY` (e.g. `...-14-oct-10`)
- 2015: `monetary-policy-statement-DDmonYY` (e.g. `...-28jan15`)
- 2016 on: `mas-monetary-policy-statement-DDmonYY`
- Slugs marked "(unconfirmed slug)" were not seen in a search result: the slug, and often the day
  of month, is a guess from the pattern. If the URL 404s, find the statement from the index
  https://www.mas.gov.sg/monetary-policy/mas-monetary-policy-statements and
  https://www.mas.gov.sg/monetary-policy/past-monetary-policy-decisions (table of every decision
  since 2001; `*` marks off-cycle ones). Statements before about 2004 may only exist as PDFs or
  inside Macroeconomic Review PDFs (e.g. Oct 2005 is reproduced in
  https://www.mas.gov.sg/-/media/MAS/resource/publications/macro_review/MR_Oct05.pdf).
- Cadence: Feb/Jul/Oct 2001 (Oct off-cycle), then semi-annual (April/October, regular from Oct
  2003); off-cycle Jan 2015, Mar 2020, Jan 2022 and Jan 2025; quarterly (Jan/Apr/Jul/Oct) from 2024.

### Checklist
- [ ] 2001-02-22: https://www.mas.gov.sg/news/monetary-policy-statements/2001/monetary-policy-statement-22-feb-01 (unconfirmed slug) - first MPS (22 Feb 2001); page may only exist as a PDF/older URL
- [ ] 2001-07 (day unknown) - find it in https://www.mas.gov.sg/news/monetary-policy-statements/2001/ via the index https://www.mas.gov.sg/monetary-policy/mas-monetary-policy-statements (unconfirmed slug) - slope set to 0%; day unknown
- [ ] 2001-10 (day unknown) - find it in https://www.mas.gov.sg/news/monetary-policy-statements/2001/ via the index https://www.mas.gov.sg/monetary-policy/mas-monetary-policy-statements (unconfirmed slug) - off-cycle; band widened; day unknown
- [ ] 2002-04 (day unknown) - find it in https://www.mas.gov.sg/news/monetary-policy-statements/2002/ via the index https://www.mas.gov.sg/monetary-policy/mas-monetary-policy-statements (unconfirmed slug) - day unknown
- [ ] 2002-10 (day unknown) - find it in https://www.mas.gov.sg/news/monetary-policy-statements/2002/ via the index https://www.mas.gov.sg/monetary-policy/mas-monetary-policy-statements (unconfirmed slug) - day unknown
- [ ] 2003-04 (day unknown) - find it in https://www.mas.gov.sg/news/monetary-policy-statements/2003/ via the index https://www.mas.gov.sg/monetary-policy/mas-monetary-policy-statements (unconfirmed slug) - day unknown
- [ ] 2003-07 (day unknown) - find it in https://www.mas.gov.sg/news/monetary-policy-statements/2003/ via the index https://www.mas.gov.sg/monetary-policy/mas-monetary-policy-statements (unconfirmed slug) - re-centred lower, Jul 2003; day unknown
- [ ] 2003-10 (day unknown) - find it in https://www.mas.gov.sg/news/monetary-policy-statements/2003/ via the index https://www.mas.gov.sg/monetary-policy/mas-monetary-policy-statements (unconfirmed slug) - day unknown
- [ ] 2004-04-12: https://www.mas.gov.sg/news/monetary-policy-statements/2004/monetary-policy-statement-12-apr-04
- [ ] 2004-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2004/monetary-policy-statement-14-oct-04 (unconfirmed slug)
- [ ] 2005-04-12: https://www.mas.gov.sg/news/monetary-policy-statements/2005/monetary-policy-statement-12-apr-05 (unconfirmed slug)
- [ ] 2005-10-11: https://www.mas.gov.sg/news/monetary-policy-statements/2005/monetary-policy-statement-11-oct-05 (unconfirmed slug)
- [ ] 2006-04-12: https://www.mas.gov.sg/news/monetary-policy-statements/2006/monetary-policy-statement-12-apr-06 (unconfirmed slug)
- [ ] 2006-10-12: https://www.mas.gov.sg/news/monetary-policy-statements/2006/monetary-policy-statement-12-oct-06 (unconfirmed slug)
- [ ] 2007-04-12: https://www.mas.gov.sg/news/monetary-policy-statements/2007/monetary-policy-statement-12-apr-07 (unconfirmed slug)
- [ ] 2007-10-12: https://www.mas.gov.sg/news/monetary-policy-statements/2007/monetary-policy-statement-12-oct-07 (unconfirmed slug)
- [ ] 2008-04-10: https://www.mas.gov.sg/news/monetary-policy-statements/2008/monetary-policy-statement-10-apr-08
- [ ] 2008-10-10: https://www.mas.gov.sg/news/monetary-policy-statements/2008/monetary-policy-statement-10-oct-08
- [ ] 2009-04-14: https://www.mas.gov.sg/news/monetary-policy-statements/2009/monetary-policy-statement-14-apr-09
- [ ] 2009-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2009/monetary-policy-statement-14-oct-09 (unconfirmed slug)
- [ ] 2010-04-14: https://www.mas.gov.sg/news/monetary-policy-statements/2010/monetary-policy-statement-14-apr-10
- [ ] 2010-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2010/monetary-policy-statement-14-oct-10
- [ ] 2011-04-14: https://www.mas.gov.sg/news/monetary-policy-statements/2011/monetary-policy-statement-14-apr-11
- [ ] 2011-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2011/monetary-policy-statement-14-oct-11 (unconfirmed slug)
- [ ] 2012-04-13: https://www.mas.gov.sg/news/monetary-policy-statements/2012/monetary-policy-statement-13-apr-12 (unconfirmed slug)
- [ ] 2012-10-12: https://www.mas.gov.sg/news/monetary-policy-statements/2012/monetary-policy-statement-12-oct-12
- [ ] 2013-04-12: https://www.mas.gov.sg/news/monetary-policy-statements/2013/monetary-policy-statement-12-apr-13
- [ ] 2013-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2013/monetary-policy-statement-14-oct-13
- [ ] 2014-04-14: https://www.mas.gov.sg/news/monetary-policy-statements/2014/monetary-policy-statement-14-apr-14
- [ ] 2014-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2014/monetary-policy-statement-14-oct-14 (unconfirmed slug)
- [ ] 2015-01-28: https://www.mas.gov.sg/news/monetary-policy-statements/2015/monetary-policy-statement-28jan15 - off-cycle
- [ ] 2015-04-14: https://www.mas.gov.sg/news/monetary-policy-statements/2015/monetary-policy-statement-14apr15 (unconfirmed slug)
- [ ] 2015-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2015/monetary-policy-statement-14oct15
- [ ] 2016-04-14: https://www.mas.gov.sg/news/monetary-policy-statements/2016/mas-monetary-policy-statement-14apr16 (unconfirmed slug)
- [ ] 2016-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2016/mas-monetary-policy-statement-14oct16
- [ ] 2017-04-13: https://www.mas.gov.sg/news/monetary-policy-statements/2017/mas-monetary-policy-statement-13apr17 (unconfirmed slug)
- [ ] 2017-10-13: https://www.mas.gov.sg/news/monetary-policy-statements/2017/mas-monetary-policy-statement-13oct17 (unconfirmed slug)
- [ ] 2018-04-13: https://www.mas.gov.sg/news/monetary-policy-statements/2018/mas-monetary-policy-statement-13apr18
- [ ] 2018-10-12: https://www.mas.gov.sg/news/monetary-policy-statements/2018/mas-monetary-policy-statement-12oct18
- [ ] 2019-04-12: https://www.mas.gov.sg/news/monetary-policy-statements/2019/mas-monetary-policy-statement-12apr19
- [ ] 2019-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2019/mas-monetary-policy-statement-14oct19
- [ ] 2020-03-30: https://www.mas.gov.sg/news/monetary-policy-statements/2020/mas-monetary-policy-statement-30mar20 - off-cycle
- [ ] 2020-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2020/mas-monetary-policy-statement-14oct20 (unconfirmed slug)
- [ ] 2021-04-14: https://www.mas.gov.sg/news/monetary-policy-statements/2021/mas-monetary-policy-statement-14apr21
- [ ] 2021-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2021/mas-monetary-policy-statement-14oct21
- [ ] 2022-01-25: https://www.mas.gov.sg/news/monetary-policy-statements/2022/mas-monetary-policy-statement-25jan22 (unconfirmed slug) - off-cycle; day unconfirmed
- [ ] 2022-04-14: https://www.mas.gov.sg/news/monetary-policy-statements/2022/mas-monetary-policy-statement-14apr22
- [ ] 2022-07-14: https://www.mas.gov.sg/news/monetary-policy-statements/2022/mas-monetary-policy-statement-14jul22
- [ ] 2022-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2022/mas-monetary-policy-statement-14oct22
- [ ] 2023-04-14: https://www.mas.gov.sg/news/monetary-policy-statements/2023/mas-monetary-policy-statement-14apr23
- [ ] 2023-10-13: https://www.mas.gov.sg/news/monetary-policy-statements/2023/mas-monetary-policy-statement-13oct23
- [ ] 2024-01-29: https://www.mas.gov.sg/news/monetary-policy-statements/2024/mas-monetary-policy-statement-29jan24
- [ ] 2024-04-12: https://www.mas.gov.sg/news/monetary-policy-statements/2024/mas-monetary-policy-statement-12apr24 (unconfirmed slug)
- [ ] 2024-07-12: https://www.mas.gov.sg/news/monetary-policy-statements/2024/mas-monetary-policy-statement-12jul24 (unconfirmed slug)
- [ ] 2024-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2024/mas-monetary-policy-statement-14oct24 (unconfirmed slug)
- [ ] 2025-01-24: https://www.mas.gov.sg/news/monetary-policy-statements/2025/mas-monetary-policy-statement-24jan25 - off-cycle
- [ ] 2025-04-14: https://www.mas.gov.sg/news/monetary-policy-statements/2025/mas-monetary-policy-statement-14apr25
- [ ] 2025-07-14: https://www.mas.gov.sg/news/monetary-policy-statements/2025/mas-monetary-policy-statement-14jul25 (unconfirmed slug)
- [ ] 2025-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2025/mas-monetary-policy-statement-14oct25
- [ ] 2026-01-29: https://www.mas.gov.sg/news/monetary-policy-statements/2026/mas-monetary-policy-statement-29jan26
- [ ] 2026-04-14: https://www.mas.gov.sg/news/monetary-policy-statements/2026/mas-monetary-policy-statement-14apr26
- [ ] 2026-07-27: https://www.mas.gov.sg/news/monetary-policy-statements/2026/mas-monetary-policy-statement-27jul26
- [ ] 2026-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2026/mas-monetary-policy-statement-14oct26 (unconfirmed slug) - due Oct 2026; check the release calendar

### Stance gold set (20 statements; these are a subset of the checklist above)

These feed `tests/fixtures/mas_stance_gold.csv`: save the decision paragraph (verbatim) of each
and fill the columns url, date, decision_paragraph, label_direction [tighten|maintain|ease],
label_parameters, notes. Label by reading that paragraph only. URLs came from web-search
results; they were not opened. They give a spread of tighten / maintain / ease and
slope / centre / zero-appreciation wording. The extractor (`cbtone.decisions.mas`) is unit-tested
on illustrative phrasing only; the >= 18/20 claim is unverified until the gold file is filled
(`test_gold_set` skips while it is empty).

1. https://www.mas.gov.sg/news/monetary-policy-statements/2012/monetary-policy-statement-12-oct-12
2. https://www.mas.gov.sg/news/monetary-policy-statements/2015/monetary-policy-statement-28jan15
3. https://www.mas.gov.sg/news/monetary-policy-statements/2015/monetary-policy-statement-14oct15
4. https://www.mas.gov.sg/news/monetary-policy-statements/2016/mas-monetary-policy-statement-14oct16
5. https://www.mas.gov.sg/news/monetary-policy-statements/2019/mas-monetary-policy-statement-12apr19
6. https://www.mas.gov.sg/news/monetary-policy-statements/2019/mas-monetary-policy-statement-14oct19
7. https://www.mas.gov.sg/news/monetary-policy-statements/2020/mas-monetary-policy-statement-30mar20
8. https://www.mas.gov.sg/news/monetary-policy-statements/2021/mas-monetary-policy-statement-14apr21
9. https://www.mas.gov.sg/news/monetary-policy-statements/2021/mas-monetary-policy-statement-14oct21
10. https://www.mas.gov.sg/news/monetary-policy-statements/2022/mas-monetary-policy-statement-14apr22
11. https://www.mas.gov.sg/news/monetary-policy-statements/2022/mas-monetary-policy-statement-14jul22
12. https://www.mas.gov.sg/news/monetary-policy-statements/2022/mas-monetary-policy-statement-14oct22
13. https://www.mas.gov.sg/news/monetary-policy-statements/2023/mas-monetary-policy-statement-14apr23
14. https://www.mas.gov.sg/news/monetary-policy-statements/2023/mas-monetary-policy-statement-13oct23
15. https://www.mas.gov.sg/news/monetary-policy-statements/2024/mas-monetary-policy-statement-29jan24
16. https://www.mas.gov.sg/news/monetary-policy-statements/2025/mas-monetary-policy-statement-24jan25
17. https://www.mas.gov.sg/news/monetary-policy-statements/2025/mas-monetary-policy-statement-14apr25
18. https://www.mas.gov.sg/news/monetary-policy-statements/2025/mas-monetary-policy-statement-14oct25
19. https://www.mas.gov.sg/news/monetary-policy-statements/2026/mas-monetary-policy-statement-14apr26
20. https://www.mas.gov.sg/news/monetary-policy-statements/2026/mas-monetary-policy-statement-27jul26

Also useful: Oct 2018 (slight slope increase, 12 Oct 2018) and the Jan/Apr/Jul/Oct 2024 statements.

## PBoC - Monetary Policy Committee communiqués (2010 on)

`https://www.pbc.gov.cn/robots.txt` disallows all crawlers except Baiduspider
(`User-agent: * / Disallow: /`), so `PoliteFetcher` refuses every URL.

Save by hand (browser "Save page as", HTML) into `data/raw/pboc/manual/`, named
`<meeting-date>_<zh|en>.html`:

- zh index: https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/index.html
  (货币政策委员会例会 list; open each communiqué, 2010-> suffices).
- en: https://www.pbc.gov.cn/en/3688110/3688172/ (Monetary Policy Committee meeting items; where they exist).

Pair translations by using the same meeting date in the filename.

Then run `uv run cbtone fetch pboc`. PBoC is out of the headline set either way (DECISIONS D10); these files only enable the optional zh extension.
