"""Event windows: change in a daily series around a timestamped release."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime

import polars as pl

from cbtone.markets.registry import REGISTRY, SeriesSpec

OUT_SCHEMA = {
    "series": pl.String,
    "unit": pl.String,
    "start_date": pl.Date,
    "end_date": pl.Date,
    "start_close": pl.Float64,
    "end_close": pl.Float64,
    "change": pl.Float64,
}


def event_window(
    series_df: pl.DataFrame,
    event_ts_utc: datetime,
    pre: int = -1,
    post: int = 1,
    *,
    registry: dict[str, SeriesSpec] | None = None,
    max_gap_days: int = 5,
) -> pl.DataFrame:
    """Change in each series from close ``t+pre`` to close ``t+post``.

    ``t`` is the first close (per the series' own close time zone, see the registry) that
    falls strictly after ``event_ts_utc``. So ``pre=-1`` is the last close at or before the
    release and ``post=1`` the close one trading day after ``t`` (the MISSION default
    [t-1, t+1]); ``post=0`` gives the tight [t-1, t] window. A release after a market's close
    (FOMC 14:00 ET vs. Singapore/Jakarta FX closes) therefore maps ``t`` to the next day for
    that market only.

    ``change`` is a log return for FX and a basis-point change for yields (inputs in
    percent). Series lacking data on either end, or whose ``t`` close is more than
    ``max_gap_days`` after the event (data hole), are omitted.
    """
    if event_ts_utc.tzinfo is None:
        raise ValueError("event_ts_utc must be timezone-aware")
    if pre >= post:
        raise ValueError("pre must be < post")
    reg = REGISTRY if registry is None else registry
    ts = event_ts_utc.astimezone(UTC)
    rows: list[dict[str, object]] = []
    for name in series_df["series"].unique(maintain_order=True):
        spec = reg[name]
        sub = series_df.filter(pl.col("series") == name).sort("date")
        dates: list[date] = sub["date"].to_list()
        closes: list[float] = sub["close"].to_list()
        i0 = next((i for i, d in enumerate(dates) if spec.close_utc(d) > ts), None)
        if i0 is None:
            continue
        if (dates[i0] - ts.date()).days > max_gap_days:
            continue
        a, b = i0 + pre, i0 + post
        if a < 0 or b >= len(dates):
            continue
        x, y = closes[a], closes[b]
        if spec.kind == "fx":
            if x <= 0 or y <= 0:
                continue
            change = math.log(y / x)
        else:
            change = (y - x) * 100.0
        rows.append(
            {
                "series": name,
                "unit": spec.unit,
                "start_date": dates[a],
                "end_date": dates[b],
                "start_close": x,
                "end_close": y,
                "change": change,
            }
        )
    return pl.DataFrame(rows, schema=OUT_SCHEMA)
