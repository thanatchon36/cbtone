# NEEDED: MAS Monetary Policy Statements for the stance gold set

`www.mas.gov.sg` returned a "Maintenance / service currently unavailable" page (HTTP 200) to the
polite fetcher for both the MPS index and a statement page (robots.txt itself allows crawling,
Crawl-delay 2). Treated as blocked; not circumvented.

Please save the decision paragraph (verbatim) of each statement below and fill
`tests/fixtures/mas_stance_gold.csv` (columns: url, date, decision_paragraph, label_direction
[tighten|maintain|ease], label_parameters, notes). Label by reading that paragraph only.
URLs come from web-search results for mas.gov.sg; they were not opened. The 20 give a spread of
tighten / maintain / ease and slope / centre / zero-appreciation wording.

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

Also useful (not in the 20): Oct 2018 (slight slope increase, 12 Oct 2018) and Jan/Apr/Jul/Oct 2024
statements; the index is https://www.mas.gov.sg/monetary-policy/past-monetary-policy-decisions.
The extractor (`cbtone.decisions.mas`) is unit-tested on illustrative phrasing only; the >= 18/20
claim is unverified until this file is filled (`test_gold_set` skips while it is empty).
