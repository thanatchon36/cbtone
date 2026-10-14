# BoT source notes

Adapter: `src/cbtone/sources/bot.py` (`BoTAdapter`, bank `bot`; English and Thai). Opt-in:
excluded from headline results (`include_bot: false`); the adapter itself meets the full contract.

## Document types
- `statement`: the Monetary Policy Committee (MPC, กนง.) decision press release, "Monetary Policy
  Committee's Decision n/YYYY" / "ผลการประชุมคณะกรรมการนโยบายการเงิน ครั้งที่ n/YYYY", read out
  by the MPC secretary. HTML.
- `minutes`: "Edited Minutes of the Monetary Policy Committee Meeting" (Thai: "รายงานการประชุม
  ... (ฉบับย่อ)"), published about two weeks after the meeting. PDF (text-based); sections carry
  the PDF's sub-headings.
Not collected: Monetary Policy Reports, forum slides/videos, the policy-rate xlsx table.

## Languages and pairing
`en` and `th`, one `Document` per language. Both schedule pages
(`/en/...` and `/th/...mpc-meeting.html`) list the same meetings in the same rows, so a decision's
two language versions are paired by decision date: `parallel_id = "bot:<date>:<doc_type>"`
(identical across `en`/`th`). Statement and minutes pairs are separate (different `doc_type`).
Thai pages use Buddhist-era years (2569 = 2026); the adapter converts them (`parse_date`).

## URL patterns
- Index (static HTML, one table per year, 2021 onwards, both languages):
  `https://www.bot.or.th/{en,th}/our-roles/monetary-policy/mpc-meeting.html`. Row = meeting
  number, announcement date, "Press Release" link, "Minutes" PDF link (+ report/slides links,
  ignored). Rows for future meetings have dates but no links and are skipped.
- Statement (hrefs come from the index; pages differ by era, the adapter does not construct them):
  - to ~mid-2025: `/{lang}/news-and-media/news/news-YYYYMMDD[-n].html`
  - from Aug 2025: `/{lang}/news-and-media/news/mpc/news-YYYYMMDD-<hash>.html`
- Minutes PDF: `/content/dam/bot/documents/{lang}/our-roles/monetary-policy/mpc-publication/
  edited-minutes/MPC_Minutes_<YYYY>_<n>.pdf` (Thai file name uses the Buddhist year) to mid-2025,
  then `/content/dam/bot/documents/{lang}/research-and-publications/reports/monetary-policy/
  minutes-mpc/mpc-minutes-<YYYY>-<n>.pdf`.
- Sitemaps `https://www.bot.or.th/{en,th}.sitemap.xml` only list the 2025+ `/news/mpc/` pages,
  so they cannot supply earlier history.

## Coverage
2021 to present: 36 meetings (2021: 8 incl. two extra; 2022-2025: 6 each; 2026: 4 so far) = about
72 statements and 72 minutes (2 languages each), about 144 documents. A full run is 2 index
requests plus about 144 document requests (roughly 5 minutes at the 2 s interval).
Gaps: 2020 and earlier are not discoverable from any static index (the "Past Schedules" tables
start at 2021; the news listing is JavaScript-driven; the edited-minutes page says "from 1/2011 to
present" but links nothing statically). Older documents would need a human-supplied URL list.

## Layout eras
- Statement body is the largest `div.cmp-text` of the page (the page's other `cmp-text` blocks are
  title/navigation widgets). Paragraphs are `<p>`; the `<title>` is the document title.
  The body ends with a sign-off ("Bank of Thailand" / "ธนาคารแห่งประเทศไทย" + a date line), which
  is dropped. From 2025, footnotes follow the sign-off and are kept as sections with
  `heading="Footnotes"` (`"เชิงอรรถ"` in Thai). Contact box and related-tag widgets are outside the body.
- Minutes: PDF text has no paragraph marks. `minutes_sections` rebuilds them: a paragraph ends at
  a clearly short line; a short, unpunctuated block-start line is a heading; footnotes ("2/ ..."
  or "1 Text"), page numbers, the attendance list and everything after the sign-off
  ("Monetary Policy Group" / "สายนโยบายการเงิน", then annex charts) are dropped. Thai lines are
  joined without a space inside words. Known limitation: in Thai minutes a heading that directly
  follows a full-width last line (for example the "monetary policy consideration" heading) cannot be
  told from the paragraph's last short line and is absorbed into the previous paragraph. PDF text
  extraction also leaves stray spaces/odd glyphs inside words (for example "proje cted", "ต ่า");
  the text module cleans these.

## Dates and release time (`published_at_utc`)
- `date` = the MPC decision/announcement date from the schedule row (Wednesday of the meeting
  week; the minutes cover the same meeting, so they use the same date, e.g. 26 Aug 2026 for the
  21 and 26 August 2026 meeting). Publication date of the minutes ("Publication Date: ...") is
  not stored.
- Statements: 14:00 `Asia/Bangkok` (UTC+7, no DST), i.e. 07:00 UTC. Source
  (https://www.bot.or.th/en/our-roles/monetary-policy/mpc-publication.html): "The MPC's Decision is
  published at 2:00 PM on the day of the MPC Meeting. The MPC secretary holds the press conference
  at 2:30 PM on the day of the MPC Meeting." Corroboration: the 2025 and 2026 pages have a
  replication timestamp of 07:00 UTC. The rule is documented for the current practice; it is applied
  to all adapter years (2021-) without per-year evidence.
- Minutes: `None` (only a date is published).

## Politeness
robots.txt (`User-agent: *`) disallows only `/_layouts/`, `/_vti_bin/`, `/_catalogs/`; no
Crawl-delay. The fetcher's default 2 s interval is kept. No block, 403 or bot page was seen, so no
manual mode (`NEEDED_bot.md`) was needed.

## Anomaly
The Thai minutes URL listed for meeting 1/2021
(`.../th/.../edited-minutes/MPC_Minutes_2564_1.pdf`) serves the minutes of meeting 1/2567 (2 and 7
Feb 2024) when probed on 2026-10-14. `parse` therefore compares the "n/YYYY" in the PDF title
with the decision year and returns `[]` on a mismatch, so that document is skipped (the English
2021 minutes are fine). Other Thai 2021-2023 minutes URLs were not probed and may have the
same fault; the guard covers them.

## Terms of use
https://www.bot.or.th/en/terms-and-condition.html (Thai: `/th/terms-and-condition.html`), clause 1:
"BOT is pleased to allow Users to visit the Site and download and copy the information, documents
and materials (collectively, "Materials") from the Site for User use subject to the terms and
conditions outlined below, and also subject to more specific restrictions that may apply to
specific material within this Site." Clause 2: opinions in the Materials "are those of the various
authors of the work and are not necessarily those of BOT." There is no grant to republish or
redistribute, and no licence (Creative Commons or similar) is stated.

Redistributable: no. The terms allow downloading and copying for the user's own use only; releasing
the raw text in the public dataset would need BoT's written permission. Use for analysis is fine;
publish derived features, not the text. (A reasonable fair-use reading of quoting short passages
is outside this note.)
