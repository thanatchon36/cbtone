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
    import yfinance as yf  # type: ignore[import-untyped]

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
