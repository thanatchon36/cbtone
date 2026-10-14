# Spec: market data (`src/cbtone/markets/`)

Read: MISSION.md §1.3, `src/cbtone/sources/base.py`.

- `fetch_fx(tickers, start, end) -> polars.DataFrame[date, series, close]` via `yfinance` (already
  installed; do NOT run `uv add` — parallel agents share pyproject.toml). Series: USDSGD=X, USDIDR=X,
  USDMYR=X, USDTHB=X, USDCNY=X, EURUSD=X, GBPUSD=X, AUDUSD=X, DX-Y.NYB (DXY). Cache the raw
  download as parquet under `data/raw/markets/` with a sidecar JSON (source, tickers, retrieved_at,
  sha256), so later runs are offline.
- `fetch_fred(series_ids, start, end)` via the public CSV endpoint
  `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>` through `PoliteFetcher` (bank key
  "fred"). Series: DGS2, DGS10 (US); IRLTLT01GBM156N etc. are monthly, which won't work for daily
  events, so look for daily 2y/10y for UK/EA/AU on FRED or other free official sources (BoE yield
  curve data, ECB SDW/Data Portal AAA curve, RBA F2 table). Record what's available daily and what
  isn't in `docs/sources/markets.md`. SG/MY/TH/ID yields: check whether MAS/BNM/BoT/BI publish daily
  yield CSVs reachable without a login; if not, record it and skip (FX only for those).
- `docs/sources/markets.md`: each series, source URL, licence/terms, timezone of the close,
  holiday calendar, gaps.
- `event_window(series_df, event_ts_utc, pre=-1, post=1)` → log-return / bp-change from the last
  close strictly before the release to the close `post` trading days after. Handle a release after
  the local market close (e.g. FOMC 14:00 ET vs Asian FX closes) correctly: the "t" close is the
  first close **after** the release timestamp. Each series has a close-time timezone in a registry.
- Tests offline with small fixtures; ruff + mypy --strict clean. Don't commit; report ≤ 250 words.
