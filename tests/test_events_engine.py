from datetime import UTC, date, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from cbtone.events.engine import (
    build_events,
    event_regression,
    event_timestamp,
    placebo_dates,
    placebo_r2,
    tone_surprise,
    window_moves,
)


def test_event_timestamp_exact_and_day_rules():
    ts, timing = event_timestamp(
        "fed", date(2024, 1, 31), datetime(2024, 1, 31, 19, tzinfo=UTC), "statement"
    )
    assert timing == "exact" and ts.hour == 19
    ts, timing = event_timestamp("mas", date(2024, 4, 12), None, "mps")
    assert timing == "day" and ts == datetime(2024, 4, 11, 16, tzinfo=UTC)  # 00:00 SGT
    ts, _ = event_timestamp(
        "rba", date(2001, 3, 6), None, "statement"
    )  # released next morning (A1)
    assert ts == datetime(2001, 3, 6, 13, tzinfo=UTC)  # 00:00 AEDT on 7 Mar
    ts, _ = event_timestamp("rba", date(2010, 3, 2), None, "statement")
    assert ts.date() == date(2010, 3, 1)  # no lag after Dec 2007; 00:00 AEDT = 13:00 UTC prev day


def test_build_events_frame():
    docs = pl.DataFrame(
        {
            "doc_id": ["a", "b"],
            "bank": ["fed", "bi"],
            "date": [date(2024, 1, 31), date(2024, 2, 21)],
            "doc_type": ["statement", "statement"],
            "language": ["en", "en"],
            "published_at_utc": [datetime(2024, 1, 31, 19, tzinfo=UTC), None],
        }
    )
    ev = build_events(docs)
    assert ev["timing"].to_list() == ["exact", "day"]


def _fx(series: str, closes: list[float], start: date = date(2024, 1, 1)) -> pl.DataFrame:
    days = [start + timedelta(days=i) for i in range(len(closes))]
    return pl.DataFrame({"date": days, "series": [series] * len(days), "close": closes})


def test_window_moves_sign_and_bracketing():
    # USD/SGD falls 1 % on 4 Jan: SGD appreciation must be a *positive* move
    df = _fx("USDSGD=X", [1.35, 1.35, 1.35, 1.3365, 1.3365, 1.3365])
    # day-level MAS release on 4 Jan (00:00 SGT = 3 Jan 11:00 ET, before the 3 Jan 17:00 ET close)
    ts, _ = event_timestamp("mas", date(2024, 1, 4), None, "mps")
    (m,) = window_moves(df, "USDSGD=X", [ts])
    assert m == pytest.approx(-np.log(1.3365 / 1.35))
    assert m > 0
    # yields in bp, sign +1
    y = _fx("DGS2", [4.0, 4.0, 4.1, 4.2, 4.2])
    (b,) = window_moves(y, "DGS2", [datetime(2024, 1, 2, 19, tzinfo=UTC)])
    # 14:00 ET is before the 15:30 ET close, so t = 2 Jan and the window is [1 Jan, 3 Jan]
    assert b == pytest.approx(10.0)


def test_window_moves_missing_data_is_none():
    df = _fx("EURUSD=X", [1.1, 1.1])
    assert window_moves(df, "EURUSD=X", [datetime(2030, 1, 1, tzinfo=UTC)]) == [None]


def test_tone_surprise_uses_only_prior_data():
    tone = [0.1] * 10 + [0.9]
    s = tone_surprise(tone, min_prior=8)
    assert s[:8] == [None] * 8
    assert s[-1] == pytest.approx(0.8)  # constant history: forecast 0.1
    # changing a future value never changes an earlier surprise
    s2 = tone_surprise([*tone, -5.0], min_prior=8)
    assert s2[:-1] == s


def test_tone_surprise_ar1():
    rng = np.random.default_rng(0)
    x = [0.0]
    for _ in range(200):
        x.append(0.5 * x[-1] + rng.normal(0, 0.1))
    s = [v for v in tone_surprise(x) if v is not None]
    assert abs(np.mean(s)) < 0.03 and np.std(s) < 0.13


def test_event_regression_recovers_slope():
    rng = np.random.default_rng(1)
    x = rng.normal(size=300)
    y = 2.0 * x + rng.normal(scale=0.5, size=300)
    r = event_regression(y, x)
    assert r.beta == pytest.approx(2.0, abs=0.1) and r.p_value < 1e-10
    assert 0.9 < r.r2 < 0.97 and r.sign_agreement > 0.85
    with pytest.raises(ValueError):
        event_regression([1.0], [1.0])


def test_placebo_dates_respect_gap_and_weekends():
    dec = [date(2024, 1, 15)]
    cand = [date(2024, 1, 1) + timedelta(days=i) for i in range(40)]
    picks = placebo_dates(dec, cand, 50, min_gap=5, seed=3)
    assert all(abs((p - dec[0]).days) >= 5 and p.weekday() < 5 for p in picks)
    assert placebo_dates(dec, [date(2024, 1, 15)], 3) == []


def test_placebo_r2_null_distribution():
    rng = np.random.default_rng(2)
    r2 = placebo_r2(rng.normal(size=60), list(rng.normal(size=500)), draws=300, seed=4)
    assert len(r2) == 300 and 0 < np.median(r2) < 0.05
    assert len(placebo_r2([1.0, 2.0], [1.0])) == 0
