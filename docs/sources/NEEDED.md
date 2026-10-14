# NEEDED: files a human must download by hand

Consolidated manual-download list. Automated access is blocked or unavailable for the sources
below (MISSION section 0; DECISIONS D7), so the author saves the pages in a normal browser.
Nothing here asks the pipeline to get around a block.

## MAS - Monetary Policy Statements (2001 to Oct 2026)

Most statements are now fetched from Internet Archive copies (DECISIONS D11; see
`docs/sources/mas.md`): 62 statements, Feb 2001 to Apr 2026, and every decision in MAS's own
"past monetary policy decisions" table (2001 to Mar 2020, archived 31 Mar 2020) is covered. Only
these are still missing (no usable archived copy: every capture of the page is the MAS
"Maintenance" bot page, or the statement is not archived yet). Save by hand into
`data/raw/mas/manual/` (File > Save Page As > "Webpage, HTML only", or print to PDF), keeping the
slug as the file name; manual files take precedence over archive copies. Then run
`uv run cbtone fetch mas`.

### Checklist
- [ ] 2026-07-27: https://www.mas.gov.sg/news/monetary-policy-statements/2026/mas-monetary-policy-statement-27jul26 - all 4 archived captures (Jul-Sep 2026) are "Maintenance" pages; the date comes from the slug (a search result), so check the day
- [ ] 2026-10-14: https://www.mas.gov.sg/news/monetary-policy-statements/2026/mas-monetary-policy-statement-14oct26 (unconfirmed slug) - due Oct 2026 (the date of the last run); no archived copy yet. Check the release calendar

### Stance gold set (20 statements)

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

All of these are archived except #20 (27 Jul 2026, see the checklist). Also useful: Oct 2018 (slight slope increase, 12 Oct 2018) and the Jan/Apr/Jul/Oct 2024 statements.

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
