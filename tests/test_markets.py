"""Offline tests for cbtone.markets (fixtures under tests/fixtures/markets)."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from cbtone.markets import event_window, fetch_fx
from cbtone.markets.registry import REGISTRY, SeriesSpec
from cbtone.markets.yields import (
    parse_boe_workbook,
    parse_ecb,
    parse_fred,
    parse_rba_f2,
)

FIX = Path(__file__).parent / "fixtures" / "markets"


# -- parsers ---------------------------------------------------------------------
def test_parse_fred_skips_missing() -> None:
    recs = parse_fred((FIX / "fred_dgs2.csv").read_text(), "DGS2")
    assert recs == [
        (date(2025, 1, 2), "DGS2", 4.25),
        (date(2025, 1, 3), "DGS2", 4.28),
        (date(2025, 1, 7), "DGS2", 4.30),
    ]


def test_parse_ecb_skips_empty() -> None:
    recs = parse_ecb((FIX / "ecb_2y.csv").read_text(), "EA2Y")
    assert [(r[0], r[2]) for r in recs] == [(date(2025, 1, 2), 2.10), (date(2025, 1, 3), 2.15)]


def test_parse_rba_f2_selects_series_by_id() -> None:
    recs = parse_rba_f2((FIX / "rba_f2.csv").read_text(encoding="utf-8"))
    got = {(d, s): v for d, s, v in recs}
    assert got[(date(2013, 5, 20), "AU10Y")] == 3.229
    assert (date(2013, 5, 20), "AU2Y") not in got  # blank early history
    assert got[(date(2025, 1, 2), "AU2Y")] == 3.80
    assert got[(date(2025, 1, 3), "AU10Y")] == 4.33
    assert all(s in ("AU2Y", "AU10Y") for _, s, _ in recs)


def test_parse_boe_workbook_2y_10y() -> None:
    recs = parse_boe_workbook((FIX / "boe_glc_small.xlsx").read_bytes())
    got = {(d, s): v for d, s, v in recs}
    assert got[(date(2025, 1, 2), "GB2Y")] == 4.25
    assert got[(date(2025, 1, 2), "GB10Y")] == 4.60
    assert (date(2025, 1, 3), "GB10Y") not in got  # blank cell
    assert got[(date(2025, 1, 6), "GB10Y")] == 4.70
    assert len(recs) == 5


# -- FX cache --------------------------------------------------------------------
def _fake_download(tickers: list[str], start: date, end_excl: date) -> pd.DataFrame:
    idx = pd.date_range(start, end_excl - timedelta(days=1), freq="B", tz="Europe/London")
    cols = pd.MultiIndex.from_product([tickers, ["Open", "Close"]])
    df = pd.DataFrame(1.0, index=idx, columns=cols)
    for i, t in enumerate(tickers):
        df[(t, "Close")] = [1.30 + 0.01 * i + 0.001 * k for k in range(len(idx))]
    df.iloc[1, df.columns.get_loc((tickers[0], "Close"))] = float("nan")
    return df


def test_fetch_fx_caches_and_goes_offline(tmp_path: Path) -> None:
    calls: list[int] = []

    def dl(t: list[str], s: date, e: date) -> pd.DataFrame:
        calls.append(1)
        return _fake_download(t, s, e)

    tk = ["USDSGD=X", "EURUSD=X"]
    a = fetch_fx(tk, date(2025, 1, 6), date(2025, 1, 10), cache_dir=tmp_path, downloader=dl)
    assert a.columns == ["date", "series", "close"]
    assert a.schema["date"] == pl.Date
    assert a.filter(pl.col("series") == "USDSGD=X").height == 4  # NaN dropped
    assert a.filter(pl.col("series") == "EURUSD=X").height == 5
    meta = list(tmp_path.glob("*.json"))
    assert len(meta) == 1 and {"source", "tickers", "retrieved_at", "sha256"} <= set(
        pl.read_json(meta[0]).columns
    )
    b = fetch_fx(tk, date(2025, 1, 6), date(2025, 1, 10), cache_dir=tmp_path, offline=True)
    assert b.equals(a) and len(calls) == 1
    with pytest.raises(FileNotFoundError):
        fetch_fx(tk, date(2024, 1, 1), date(2024, 1, 5), cache_dir=tmp_path, offline=True)


# -- event_window ----------------------------------------------------------------
def _series(name: str, start: date, vals: list[float]) -> pl.DataFrame:
    days = [d for d in (start + timedelta(days=i) for i in range(len(vals) * 2)) if d.weekday() < 5]
    return pl.DataFrame(
        {"date": days[: len(vals)], "series": name, "close": vals},
        schema={"date": pl.Date, "series": pl.String, "close": pl.Float64},
    )


# FOMC 2025-01-29 14:00 ET = 19:00 UTC (Wednesday)
FOMC = datetime(2025, 1, 29, 19, 0, tzinfo=UTC)


def test_release_after_close_maps_t_per_market() -> None:
    start = date(2025, 1, 27)  # Mon: 27 28 29 30 31
    us = _series("DGS2", start, [4.10, 4.20, 4.30, 4.50, 4.80])
    uk = _series("GB2Y", start, [4.10, 4.20, 4.30, 4.50, 4.80])
    au = _series("AU2Y", start, [4.10, 4.20, 4.30, 4.50, 4.80])
    df = pl.concat([us, uk, au])
    out = event_window(df, FOMC, pre=-1, post=0).sort("series").to_dicts()
    by = {r["series"]: r for r in out}
    # US 15:30 ET close (20:30 UTC) is after 19:00 UTC: t = Jan 29, base = Jan 28
    assert (by["DGS2"]["start_date"], by["DGS2"]["end_date"]) == (
        date(2025, 1, 28),
        date(2025, 1, 29),
    )
    # London 16:00 close (16:00 UTC) and Sydney close are before the release: t = Jan 30
    assert (by["GB2Y"]["start_date"], by["GB2Y"]["end_date"]) == (
        date(2025, 1, 29),
        date(2025, 1, 30),
    )
    assert (by["AU2Y"]["start_date"], by["AU2Y"]["end_date"]) == (
        date(2025, 1, 29),
        date(2025, 1, 30),
    )
    assert by["DGS2"]["change"] == pytest.approx(10.0)  # (4.30-4.20)*100 bp
    assert by["GB2Y"]["change"] == pytest.approx(20.0)
    assert by["DGS2"]["unit"] == "bp"


def test_default_window_is_t_minus_1_to_t_plus_1() -> None:
    us = _series("DGS2", date(2025, 1, 27), [4.10, 4.20, 4.30, 4.50, 4.80])
    r = event_window(us, FOMC).to_dicts()[0]
    assert (r["start_date"], r["end_date"]) == (date(2025, 1, 28), date(2025, 1, 30))
    assert r["change"] == pytest.approx(30.0)


def test_asian_close_series_uses_next_day_for_us_release() -> None:
    sg = SeriesSpec("SGDX", "fx", "Asia/Singapore", time(17, 0), "test", "Singapore 17:00 close")
    df = _series("SGDX", date(2025, 1, 27), [1.34, 1.35, 1.36, 1.37, 1.38])
    r = event_window(df, FOMC, post=0, registry={"SGDX": sg}).to_dicts()[0]
    # 17:00 SGT Jan 29 = 09:00 UTC < 19:00 UTC, so t = Jan 30
    assert (r["start_date"], r["end_date"]) == (date(2025, 1, 29), date(2025, 1, 30))
    assert r["change"] == pytest.approx(math.log(1.37 / 1.36))
    assert r["unit"] == "log_return"


def test_release_before_close_same_day_and_fx() -> None:
    # ECB-style 13:45 CET release on Thursday is before the NY 17:00 FX close of that day
    ts = datetime(2025, 1, 30, 12, 45, tzinfo=UTC)
    fx = _series("EURUSD=X", date(2025, 1, 27), [1.04, 1.05, 1.03, 1.02, 1.01])
    r = event_window(fx, ts, post=0).to_dicts()[0]
    assert r["end_date"] == date(2025, 1, 30)
    assert r["change"] == pytest.approx(math.log(1.02 / 1.03))


def test_event_window_edge_cases() -> None:
    us = _series("DGS2", date(2025, 1, 27), [4.1, 4.2, 4.3, 4.5, 4.8])
    with pytest.raises(ValueError):
        event_window(us, datetime(2025, 1, 29, 19, 0))
    with pytest.raises(ValueError):
        event_window(us, FOMC, pre=1, post=1)
    assert event_window(us, datetime(2025, 3, 1, tzinfo=UTC)).is_empty()  # beyond data
    assert event_window(us, datetime(2025, 1, 27, 1, 0, tzinfo=UTC)).is_empty()  # no t-1 close
    assert event_window(us, FOMC, post=3).is_empty()  # not enough closes after


def test_registry_close_utc_handles_dst() -> None:
    spec = REGISTRY["DGS2"]
    assert spec.close_utc(date(2025, 1, 29)) == datetime(2025, 1, 29, 20, 30, tzinfo=UTC)
    assert spec.close_utc(date(2025, 7, 1)) == datetime(2025, 7, 1, 19, 30, tzinfo=UTC)
