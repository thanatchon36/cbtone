"""Daily FX / dollar-index closes via yfinance, cached as parquet for offline reruns."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

SCHEMA = {"date": pl.Date, "series": pl.String, "close": pl.Float64}
DEFAULT_DIR = Path("data/raw/markets")

Downloader = Callable[[list[str], date, date], Any]


def empty_frame() -> pl.DataFrame:
    return pl.DataFrame(schema=SCHEMA)


def _yf_download(tickers: list[str], start: date, end_exclusive: date) -> Any:
    import yfinance as yf

    return yf.download(
        tickers,
        start=start.isoformat(),
        end=end_exclusive.isoformat(),
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=False,
    )


def _tidy(raw: Any, tickers: list[str]) -> pl.DataFrame:
    """Convert a yfinance frame (single or MultiIndex columns) to long [date, series, close]."""
    recs: list[tuple[date, str, float]] = []
    multi = getattr(raw.columns, "nlevels", 1) > 1
    for t in tickers:
        try:
            col = raw[t]["Close"] if multi else raw["Close"]
        except KeyError:
            continue
        for ts, val in col.dropna().items():
            recs.append((ts.date(), t, float(val)))
    if not recs:
        return empty_frame()
    d, s, c = zip(*recs, strict=True)
    return pl.DataFrame({"date": list(d), "series": list(s), "close": list(c)}, schema=SCHEMA)


def _cache_paths(
    cache_dir: Path, tickers: Sequence[str], start: date, end: date
) -> tuple[Path, Path]:
    key = hashlib.sha256(f"{sorted(tickers)}|{start}|{end}".encode()).hexdigest()[:16]
    return cache_dir / f"fx_{key}.parquet", cache_dir / f"fx_{key}.json"


def fetch_fx(
    tickers: Sequence[str],
    start: date,
    end: date,
    *,
    cache_dir: Path = DEFAULT_DIR,
    offline: bool = False,
    refresh: bool = False,
    downloader: Downloader | None = None,
) -> pl.DataFrame:
    """Daily closes for ``tickers`` over [start, end] inclusive as ``[date, series, close]``.

    The tidy result is cached as parquet under ``cache_dir`` with a JSON sidecar (source,
    tickers, retrieved_at, sha256 of the parquet bytes). A cache hit never touches the network.
    """
    tk = list(dict.fromkeys(tickers))
    pq, meta = _cache_paths(cache_dir, tk, start, end)
    if pq.exists() and meta.exists() and not refresh:
        return pl.read_parquet(pq)
    if offline:
        raise FileNotFoundError(f"offline and not cached: FX {tk} {start}..{end}")
    raw = (downloader or _yf_download)(tk, start, end + timedelta(days=1))
    df = _tidy(raw, tk).filter(pl.col("date").is_between(start, end)).sort("series", "date")
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(pq)
    meta.write_text(
        json.dumps(
            {
                "source": "yfinance (Yahoo Finance)",
                "tickers": tk,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "retrieved_at": datetime.now(UTC).isoformat(),
                "sha256": hashlib.sha256(pq.read_bytes()).hexdigest(),
                "rows": df.height,
            },
            indent=2,
        )
    )
    return df


# -- bad-tick filter (Yahoo FX has decimal shifts, one-day spikes and stale plateaus) ------

SPIKE_DEV = 0.08  # |close / centred 11-day median - 1| above this is suspicious ...
CALM_DEV = 0.03  # ... and bad if the points either side of the suspicious run are this calm
MEDIAN_WINDOW = 11
MAX_RUN = 5  # longest run of consecutive suspicious ticks treated as bad data


def clean_fx(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Drop bad FX ticks; return ``(clean, dropped[series, date, reason])``.

    A tick is suspicious when it deviates > ``SPIKE_DEV`` from its centred rolling median. It is
    dropped when it repeats an adjacent value exactly (``stale``), or when it sits in a run of at
    most ``MAX_RUN`` suspicious ticks whose neighbours on both sides are calm (``spike`` for a
    single tick, ``run`` otherwise). Genuine moves, where the surrounding days move too, are kept.
    Non-FX series (yields) pass through unchanged.
    """
    from cbtone.markets.registry import REGISTRY

    names = df["series"].unique().to_list()
    fx = [s for s in names if (REGISTRY[s].kind == "fx" if s in REGISTRY else s.endswith("=X"))]
    med = pl.col("close").rolling_median(MEDIAN_WINDOW, center=True, min_samples=5)
    by = "series"
    t = (
        df.with_row_index("_i")
        .sort(by, "date")
        .with_columns(_dev=(pl.col("close") / med.over(by) - 1).abs())
        .with_columns(_sus=pl.col(by).is_in(fx) & (pl.col("_dev") > SPIKE_DEV))
        .with_columns(
            _run=(pl.col("_sus") != pl.col("_sus").shift(1)).fill_null(True).cum_sum().over(by)
        )
        .with_columns(
            _len=pl.len().over(by, "_run"),
            _stale=(pl.col("close") == pl.col("close").shift(1).over(by))
            | (pl.col("close") == pl.col("close").shift(-1).over(by)),
        )
    )
    # deviation of the points just before and just after each run
    edges = (
        t.with_columns(
            _before=pl.col("_dev").shift(1).over(by), _after=pl.col("_dev").shift(-1).over(by)
        )
        .group_by(by, "_run")
        .agg(pl.col("_before").first(), pl.col("_after").last())
    )
    t = t.join(edges, on=[by, "_run"], how="left")
    calm = (pl.col("_before").fill_null(0) <= CALM_DEV) & (
        pl.col("_after").fill_null(0) <= CALM_DEV
    )
    isolated = pl.col("_sus") & (pl.col("_len") <= MAX_RUN) & calm
    t = t.with_columns(
        _reason=pl.when(pl.col("_sus") & pl.col("_stale"))
        .then(pl.lit("stale"))
        .when(isolated & (pl.col("_len") == 1))
        .then(pl.lit("spike"))
        .when(isolated)
        .then(pl.lit("run"))
        .otherwise(None)
    )
    dropped = t.filter(pl.col("_reason").is_not_null()).sort(by, "date")
    clean = t.filter(pl.col("_reason").is_null()).sort("_i").select(df.columns)
    return clean, dropped.select(by, "date", pl.col("_reason").alias("reason"))
