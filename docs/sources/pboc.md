# pboc - People's Bank of China

- **Status:** pbc.gov.cn's robots.txt disallows every crawler except Baiduspider (D10), so
  `cbtone.sources.pboc` **never requests pbc.gov.cn**. Since D12 (author-approved) it reads Internet
  Archive (Wayback Machine) copies, plus any hand-saved files in `data/raw/pboc/manual/`
  (`<meeting-date>_<zh|en>.html`), which take precedence.
- **Doc type:** `communique`, the Monetary Policy Committee (货币政策委员会) regular-meeting
  communiqué, one per meeting and language. LPR announcements are not implemented.
- **Languages:** zh (2009->), en (2021-> in the archive).
- **Date:** the meeting date from the text ("例会于4月7日在北京召开", "On June 28, ..."). Pages
  from 2009 to 2015 say only "日前在北京召开"; for those the date comes from PBoC's own table
  of meeting dates (see below), else from the release date the page states. Never the capture
  timestamp. A date outside the title's quarter (+ 60 days) rejects the capture.
- **Release time:** `published_at_utc` = the time the zh page states ("2023-04-14 17:23:42"),
  read as Asia/Shanghai (UTC+8, no DST). en pages state none, so `None`.
- **Pairing:** `parallel_id = pboc:<year>Q<n>:communique`, shared by the zh and en text.
- **Terms of use** (archived "法律声明", https://www.pbc.gov.cn/rmyh/109345/index.html, capture
  2026-02-12): the site's material is copyright PBoC; media and sites authorised by PBoC must
  credit "稿件来源：中国人民银行网站"; commercial sites may not link without permission; PBoC may
  amend material at any time; the Chinese text prevails over the English. No open licence, so
  **redistributable: no**. Commit URL + SHA-256 only.

## Internet Archive mode (D12)

`PbocAdapter.fetch(start, end)`:

1. loads manual files first;
2. loads PBoC's table "货币政策委员会例会召开时间 (1997年至今)" from its newest usable archived
   capture (`huobizhengceersi/214481/214543/218247/2847968`, last captured 2016-09; it covers
   1997 to 2015Q4): exact meeting dates for the pages that give no day;
3. lists candidate URLs with the Wayback CDX API (`PoliteFetcher.get`, cached under
   `data/raw/pboc/`; `filter=statuscode:200`, `collapse=digest`, `output=json`):
   - prefix queries for the three communiqué directories (below), keeping article URLs only
     (index/paging pages, assets and the other columns are dropped);
   - archived copies of column front pages (zh news column, en news column) are fetched and
     scanned for links whose title/text names a communiqué ("货币政策委员会召开YYYY年第N季度例会",
     "Monetary Policy Committee Holds QN YYYY Meeting"); these URLs get an exact CDX lookup;
4. for each candidate URL fetches the raw snapshot `https://web.archive.org/web/<ts>id_/<pbc url>`
   (newest capture first; up to 8 further captures if a capture is a shell, block page, HTTP
   error, a page that is not a communiqué, or has a date outside the title's quarter);
5. keeps one document per (meeting date, language) and per (year-quarter, language);
   `start_year`/`end_year` apply to the meeting date;
6. `Document.url` is the snapshot URL (the pbc.gov.cn URL is the part after `id_/`).

robots.txt or an HTTP 401/403/429 from archive.org stops the run (`BlockedError`); it is not
worked around. A 5xx/connect error on one capture is recorded in `adapter.skipped` and the next
capture is tried. Use `PoliteFetcher(min_interval_s=5)` while other adapters also use archive.org.
`use_archive=False` gives manual-only mode.

## Where the communiqués are (verified on archived pages, 2026-10-14)

| Period | zh location | Body selector | Notes |
|---|---|---|---|
| 2009 - Apr 2015 | `/publish/huobizhengceersi/3141/<year>/<id>/<id>_.html` | `font#zoom` | Title `h2`; release stamp `YYYY-MM-DD HH:MM:SS` in the header row; UTF-8 |
| May 2015 - 2017 | `/goutongjiaoliu/113456/113469/<id>/index.html` (news column) | `div#zoom` | No dedicated list; found via archived news front pages |
| 2017Q4 - 2026 | `/zhengcehuobisi/125207/3870933/3870936/<id-or-hash>/index.html` (例会信息) and, mirrored, the news column | `div#zoom` | `span#shijian` holds the release time; text states "（总第N次）例会于M月D日" |

| Period | en location | Body selector |
|---|---|---|
| 2021 - 2026 | `/en/3688229/3688311/3688329/<id>/index.html` (MPC Meetings) and the en news column `/en/3688110/3688172/` | `div.gitop` (title `h2.enTitle`) |

en wording: 2021-22 "The Monetary Policy Committee of the People's Bank of China (PBC) held the
first quarterly meeting of 2021 (its 92nd meeting) on March 24"; from 2023 "On June 28, the
Monetary Policy Committee of the People's Bank of China (PBOC) held the second quarterly meeting of
2023 (its 101st meeting)". The en page links to its Chinese version (`a.ChineseLink`).

The URL path `/zhengcehuobisi/125207/125213/125431/` is **not** the MPC: it is 公开市场业务
(open market operations).

## Coverage (live run, 2026-10-14, archive copies)

Expected: 66 regular meetings from 2010 to 2026Q3, from PBoC's own table (24 in 2010-15) and
the meeting numbers in the texts (#72 = 2015Q4, #80 = 2017Q4, #100 = 2023Q1, #112 = 2026Q1,
#114 = 2026Q3: 4 a year except 2018, which had none in Q1).

| Year | zh found | en found |
|---|---|---|
| 2010 | 4 | - |
| 2011 | 4 | - |
| 2012 | 4 | - |
| 2013 | 4 | - |
| 2014 | 4 | - |
| 2015 | 2 (Q1, Q4) | - |
| 2016 | 1 (Q1) | - |
| 2017 - 2020 | 0 | - |
| 2021 | 0 | 4 |
| 2022 | 0 | 2 (Q2, Q3) |
| 2023 | 4 | 3 (Q1-Q3) |
| 2024 | 2 (Q3, Q4) | 3 (Q1, Q3, Q4) |
| 2025 | 4 | 4 |
| 2026 | 2 (Q1, Q3) | 0 |

zh: 35 of 66 expected from 2010 on = **53 %**, below D12's 80 % threshold. The gaps are
2015Q2-Q3, 2016Q2 - 2022Q4 (26 meetings), 2024Q1-Q2 and 2026Q2 (31 in all). They are structural:
from May 2016 to about 2022 every archived capture of the article, its column and its parent
pages is a JavaScript anti-bot shell (a few KB with an `eval(...)` stub and no text), and the
migrated 2020-22 URLs with hash ids were never captured at all.

en: 16 of the 23 meetings since 2021Q1. Missing: 2022Q1 (archived, but the text says only "in
Beijing recently" and the page states no date, so it is rejected as undatable), 2022Q4, 2023Q4,
2024Q2 and 2026Q1-Q3 (not archived under the MPC Meetings column).

Date checks (2010-15): the text-less dates come from PBoC's table (e.g. 2012Q1 met 29 Mar, the
page was released 31 Mar; 2015Q4 met 23 Dec, released 28 Dec). 2023 on, dates are in the text and
agree with the quarter in the title. The latest Q4 communiqués are released days after the meeting
(2024Q4: met 27 Dec, page stamped 2025-01-03 12:15 CST).

## Tests and fixtures

`tests/test_source_pboc.py` is offline (a fake fetcher serves CDX and snapshot URLs). Fixtures in
`tests/fixtures/pboc/` are real raw `id_` snapshots: `zh_2012q1_old.html` (2009-15 layout),
`zh_2015q4_news.html` (news column), `zh_2023q1_new.html` (2017Q4+ layout), `en_2023q2.html`,
`shell_empty.html` (anti-bot JavaScript shell served as an index page) and
`nonmeeting_chronology.html` (a real `#zoom` page that is not a communiqué; also the source of the
meeting-date table test). GBK/GB2312 handling is tested by re-encoding a real page, because every
archived pbc.gov.cn page seen in this run (2009-2026) is UTF-8.
