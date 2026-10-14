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
