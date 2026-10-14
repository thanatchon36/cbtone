# Spec: policy decisions table (`src/cbtone/decisions/`)

Read: MISSION.md §1.2, `src/cbtone/schema.py`, `src/cbtone/sources/base.py`.

## Output schema
Add `Decision` to a new `src/cbtone/decisions/schema.py` (do not edit `cbtone/schema.py`):
`bank, date, direction ∈ {hike, hold, cut}, magnitude_bp: float, rate_after: float | None,
next_direction | None, next_date | None, source ∈ {bis, bank, mas_text}, policy_instrument: str`
(e.g. "fed funds target (upper)", "ECB DFR", "S$NEER band").
Do NOT run `uv add` (shared pyproject.toml); list needed deps in your report.
Writer: `build_decisions(...) -> polars.DataFrame` → `data/corpus/decisions.parquet`.

## BIS policy rates
- BIS "Central bank policy rates" dataset, daily (`WS_CBPOL`), via the BIS SDMX/stats API or the bulk
  CSV download (find the current public URL on data.bis.org; fetch through `PoliteFetcher`, bank key
  "bis"). Countries: US, XM (euro area), GB, AU, ID, MY, CN, TH. Singapore has no policy rate (MAS),
  so it's handled separately.
- Decision = a day on which the rate changes (hike/cut, magnitude in bp). **Holds** cannot be seen in
  the rate series alone, so hold dates come from the bank's meeting calendar = dates of
  `statement`/`mps` documents in `data/corpus/documents.parquet` (function takes a list of
  `(bank, date)` meeting dates as input, so it's testable without the corpus). Rule: meeting date with no rate change
  within [date, date+3 calendar days] → hold; a rate change with no meeting within ±3 days →
  unscheduled (`direction` as observed, flag column `unscheduled=True`).
- Fed: use the upper bound of the target range (2008-12→); ECB: deposit facility rate is the BIS
  series? Check which ECB rate BIS reports (MRO) and record it; document ECB's 2024 DFR-as-signal
  convention in the docstring.
- `next_direction`/`next_date` = the following row per bank.

## MAS stance extractor
- `mas_stance(text) -> MasStance(direction ∈ {tighten, maintain, ease}, parameters: set[{slope,
  width, centre}], confidence)` rule-based on MPS phrasing ("increase the rate of appreciation of the
  S$NEER policy band", "maintain the rate of appreciation", "reduce the slope", "re-centre", "widen",
  "zero percent appreciation" …). Map tighten→hike, maintain→hold, ease→cut for the decisions table
  with `magnitude_bp=NaN`.
- `tests/fixtures/mas_stance_gold.csv` — 20 MPS paragraphs (public text, cite URL per row) with hand
  labels; the extractor must reach ≥ 18/20. Labels are made by reading the public statement's
  decision paragraph only. The main session reviews this file.

## Tests
Offline only: small BIS CSV fixture (a few hundred rows), synthetic meeting dates, MAS fixture.
`mypy --strict`, ruff clean. Don't commit; report ≤ 250 words.
