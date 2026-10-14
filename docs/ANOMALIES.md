# Anomalies

Data quirks found while building the pipeline, and how each is handled. Newest last.

## A1 — RBA statements before 2008 were released the morning after the meeting (2026-10-14)
- Pre-Dec-2007 RBA releases say "at its meeting yesterday". `RBAAdapter` sets `date` to the
  meeting date (page date − 1 day) and leaves `published_at_utc=None` (time not documented).
- **Risk:** an event window keyed on `date` would start before the text was public.
- **Rule for the events engine (to put in its spec):** a document with `published_at_utc=None`
  is keyed on its *release* date, not its meeting date. For RBA pre-2008 that is `date + 1`.
  Event studies on such documents are flagged "day-level timing" and reported separately in robustness.
- Before Dec 2007, releases exist only when the rate changed (1995 has none), so holds are not
  observable in RBA text for that period.

## A2 — BNM language is chosen by cookie (2026-10-14)
- `/ms/` 404s and `?languageId=` is ignored. `BNMAdapter` fetches through
  `/c/portal/update_language?...&languageId=en_US|ms_MY`, and those URLs become `Document.url`.
  The language is read from `<html lang>`, not trusted from the hint.

## A3 — BoE release times partly assumed (2026-10-14)
- 12:00 London for decision statements is documented from 2013 and *assumed* for 2000–2012.
  Stand-alone minutes before 6 Aug 2015 are 09:30, as cited in 2001/2013/2015 releases. The special
  March 2020 meetings have `published_at_utc=None`.
- Minutes with no meeting date on the page fall back to publication date − 1 (e.g. 2019-07-31).
- Robustness: re-run the BoE event study on 2013→ only.

## A4 — BoT: coverage starts 2021; one Thai minutes URL serves the wrong meeting (2026-10-14)
- The static MPC schedule pages start at 2021, so BoT text covers 2021→ only (about 36 meetings).
  BoT is opt-in and outside the headline set either way.
- The Thai minutes link for meeting 1/2021 (`MPC_Minutes_2564_1.pdf`) serves the 1/2567 (Feb 2024)
  minutes. `parse` drops a PDF whose title year disagrees with the decision year.
- Minutes paragraphs are inferred from line lengths, and PDF extraction leaves spaces inside Thai
  words. The text module's cleaning must handle this before any Thai sentence scoring.
- 14:00 Bangkok release is documented for current practice only and is applied to 2021→.

## A5 — BI text covers April 2016 onward only (2026-10-14)
- The BI-Rate indicator table, paged by POST, starts at 2016-04-21 (128 decisions to 2026-09). There is no
  index for the BI Rate era (Jul 2005 – Mar 2016; about 130 meetings), and the date filter is
  JavaScript-only. BI therefore enters the corpus from 2016, which roughly matches the switch to the
  7-day reverse repo rate (Aug 2016) as the policy rate. RQ1/RQ2 sample-size tables state this.
- BI pages that do not exist return HTTP 200 with a "404" body; `parse` returns `[]`.

## A6 — BoE decision releases 2000–2006 are one sentence (2026-10-14)
- Before about 2007, BoE releases on unchanged rates consist only of the decision sentence (~100 chars;
  the page and its PDF carry nothing else). An earlier parse dropped that sentence because it sits in the page
  lead (`div.page-description`); fixed, with regression fixtures for 2000 and 2010.
- For tone scoring these documents carry almost no tone signal. BoE tone analysis uses the minutes
  for 2000–2012, and statements from 2013 (when they become ~1,000+ chars). Pre-registered as such.
- `cbtone snapshot` prints a QA line for documents under 200 chars, and these are expected there.

## A7 — Yahoo FX bad ticks (2026-10-14)
- Yahoo daily FX contains decimal shifts (USD/IDR 888 on 2010-11-01), one-day spikes (EUR/USD 1.49
  on 2008-12-08 vs ~1.29), and a recurring stale USD/IDR value of 9,612.45 (Nov–Dec 2013).
- `markets.fx.clean_fx` drops a tick > 8 % off its centred 11-day median when it repeats an
  adjacent value exactly, or sits in a run of ≤ 5 such ticks whose neighbours are within 3 % of the median.
  Genuine moves (e.g. AUD/USD 27 Oct 2008, neighbours also down) are kept. 13 ticks were dropped. They are
  listed in `data/raw/markets/dropped_ticks.csv` (series, date, reason; no prices).
- FX series start in Dec 2003 for most pairs, so MAS statements from 2001–2003 have no FX window.

## A8 — MAS 2026 gaps (2026-10-14)
- 27 Jul 2026: all four Internet Archive captures are the MAS "Maintenance" bot page. 14 Oct 2026:
  not archived yet. The MAS series therefore ends at 14 Apr 2026.
- The decision table's newest capture ends at 14 Oct 2025, so 2026 MAS directions would come from the
  text extractor (development accuracy only, D14). These rows (`source="mas_text"`) are excluded from
  hypothesis tests (`RESEARCH_QUESTIONS.md` §0.3).

## A9 — BI masked-LLM AUROC exactly 1.000 in RQ1 (2026-10-14)
- RQ1 BI, scorer `llm_masked`: AUROC hike-vs-cut = 1.000, on only 20 out-of-sample hike/cut rows (11 hikes, 9 cuts).
  Perfect ranking of 20 points is plausible at this size. The unmasked LLM gets 0.939 and the dictionary 0.960 on the same rows.
- Checked: no leakage path. Predictions use only the training window (`rolling_origin` fits on rows < t). The masked text
  carries no date or rate level, and the AUROC uses held-out next decisions only.
- AUROC is a secondary metric. The primary log-loss gain for BI masked is +0.032 with CI [−0.049, 0.119], i.e. not
  significant. The value is reported as is, with its small n.
- SANITY-OK: rq1.bi.llm_masked.auroc

## A10 — BI: the tone surprise moves USD/IDR with the "wrong" sign (2026-10-14)
- RQ2, BI, LLM: β = −0.0039 (HAC p = 0.007, R² = 0.064; 120 day-level events). A more hawkish surprise coincides with
  rupiah *depreciation* over the release window. The pre-registered test is one-sided (β > 0), so the cell does not count
  as a success.
- Reported descriptively, with no causal reading. A plausible mechanical explanation, which the design cannot separate,
  is that hawkish statements and currency weakness occur in the same windows (two-day day-level windows; reverse timing).
  The paper does not comment on any bank's policy choices.
