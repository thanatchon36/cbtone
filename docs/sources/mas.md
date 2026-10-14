# MAS — Monetary Authority of Singapore

- **Status:** blocked for automated fetching (D7): www.mas.gov.sg serves an HTTP 200 "Maintenance"
  bot page. `cbtone.sources.mas` loads hand-saved files from `data/raw/mas/manual/`
  (list in `docs/sources/NEEDED.md`). It never fetches mas.gov.sg or archive.org.
- **Doc type:** Monetary Policy Statement (2001→; semi-annual, quarterly from 2024, plus off-cycle).
- **Language:** en.
- **Date:** from the slug (`...-DDmonYY`, `...-DD-mon-YY`, `mps-YYYY-MM-DD`), else from the statement text.
- **Release time:** not documented; `published_at_utc=None`. MAS statements are usually released at
  08:00 SGT before the market opens, but that is not verified, so event windows use day-level timing.
- **Terms of use** (https://www.mas.gov.sg/terms-of-use): prior written permission is needed to
  reproduce or distribute content, apart from a personal, non-commercial single copy.
  **Redistributable: no.** Commit the URL and SHA-256 only.
- **Fixtures:** synthetic (`tests/fixtures/mas/`), since no real page could be fetched.
