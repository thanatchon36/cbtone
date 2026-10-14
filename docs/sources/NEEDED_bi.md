# Bank Indonesia: manual files needed (not a block)

bi.go.id allows crawling (robots.txt: `Allow: /`), but the index of all RDG decisions is a
paged ASP.NET table that only moves forward through form POSTs, which `PoliteFetcher` (GET only)
cannot do. Page 1 (latest 10 decisions) is fetched automatically; the rest must be saved by hand.

1. Open https://www.bi.go.id/en/statistik/indikator/BI-Rate.aspx in a browser.
2. Optionally set the Start/End date fields and press Search to cover 2005-07 onward.
3. For each page of the table (1, 2, 3, ... about 25 pages of 10 rows), use "Save page as"
   (HTML only is fine) and put the file in `data/raw/bi/manual/` (any name ending `.html`,
   e.g. `page02.html`).

`BIAdapter.list_urls` reads every `*.htm*` file in that folder, in addition to page 1. Each row
gives the decision date and a press-release link; the other-language twin is derived by swapping
`/en/` and `/id/`. Rows whose link is not a `news-release/Pages/sp_*.aspx` page (older decisions
may link elsewhere) are fetched as is and parsed if they have the same page layout; check the
row count against the number of documents after a full run.
