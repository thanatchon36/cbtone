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
