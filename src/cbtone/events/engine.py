"""Event-study engine (MISSION §3 `cbtone.events`; RESEARCH_QUESTIONS.md §0.4, RQ2).

- ``event_timestamp``: the release instant of a document, or 00:00 local time on its release date
  when no time is known (§0.4), plus a ``timing`` flag (exact/day).
- ``window_moves``: vectorised [t-1, t+1] change of one daily series around many timestamps, signed
  so that positive = hawkish-consistent (domestic-currency appreciation, higher yields).
- ``tone_surprise``: tone minus its AR(1) forecast, fitted on prior documents only.
- ``event_regression``: OLS with Newey-West (HAC, lag 1) errors, R² and sign agreement
  (event-study design after Gürkaynak, Sack & Swanson 2005 and Kuttner 2001).
- ``placebo_r2``: the same regression on non-announcement days, for the placebo distribution.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from cbtone.markets.registry import REGISTRY, SeriesSpec

BANK_TZ: dict[str, str] = {
    "fed": "America/New_York",
    "ecb": "Europe/Berlin",
    "boe": "Europe/London",
    "rba": "Australia/Sydney",
    "mas": "Asia/Singapore",
    "bi": "Asia/Jakarta",
    "bnm": "Asia/Kuala_Lumpur",
    "bot": "Asia/Bangkok",
    "pboc": "Asia/Shanghai",
}

# RQ2 series per bank (RESEARCH_QUESTIONS.md RQ2): FX for all, 2y yields where available (D9).
BANK_SERIES: dict[str, dict[str, str]] = {
    "fed": {"fx": "DX-Y.NYB", "y2": "DGS2"},
    "ecb": {"fx": "EURUSD=X", "y2": "EA2Y"},
    "boe": {"fx": "GBPUSD=X", "y2": "GB2Y"},
    "rba": {"fx": "AUDUSD=X", "y2": "AU2Y"},
    "mas": {"fx": "USDSGD=X"},
    "bi": {"fx": "USDIDR=X"},
    "bnm": {"fx": "USDMYR=X"},
    "bot": {"fx": "USDTHB=X"},
    "pboc": {"fx": "USDCNY=X"},
}

# +1 when a rise in the series means the domestic currency appreciated (or the yield rose).
SERIES_SIGN: dict[str, int] = {
    "DX-Y.NYB": 1,  # USD index: up = USD stronger (Fed's domestic currency)
    "EURUSD=X": 1,
    "GBPUSD=X": 1,
    "AUDUSD=X": 1,
    "USDSGD=X": -1,
    "USDIDR=X": -1,
    "USDMYR=X": -1,
    "USDTHB=X": -1,
    "USDCNY=X": -1,
}

RBA_DAILY_RELEASES_FROM = date(2007, 12, 1)  # before this, releases came the next morning (A1)


def release_lag_days(bank: str, doc_date: date, doc_type: str) -> int:
    """Days between a document's ``date`` and its release date, where an adapter knows it."""
    if bank == "rba" and doc_type == "statement" and doc_date < RBA_DAILY_RELEASES_FROM:
        return 1
    return 0


def event_timestamp(
    bank: str, doc_date: date, published_at_utc: datetime | None, doc_type: str
) -> tuple[datetime, str]:
    """(UTC timestamp, timing) by the pre-registered rule (RESEARCH_QUESTIONS.md §0.4)."""
    if published_at_utc is not None:
        ts = published_at_utc if published_at_utc.tzinfo else published_at_utc.replace(tzinfo=UTC)
        return ts.astimezone(UTC), "exact"
    release = doc_date + timedelta(days=release_lag_days(bank, doc_date, doc_type))
    local = datetime.combine(release, time(0, 0), tzinfo=ZoneInfo(BANK_TZ[bank]))
    return local.astimezone(UTC), "day"


def build_events(docs: pl.DataFrame) -> pl.DataFrame:
    """One event per document: ``doc_id, bank, date, doc_type, language, event_ts_utc, timing``."""
    rows = []
    for r in docs.select(
        "doc_id", "bank", "date", "doc_type", "language", "published_at_utc"
    ).iter_rows(named=True):
        ts, timing = event_timestamp(r["bank"], r["date"], r["published_at_utc"], r["doc_type"])
        rows.append(
            {
                **{k: r[k] for k in ("doc_id", "bank", "date", "doc_type", "language")},
                "event_ts_utc": ts,
                "timing": timing,
            }
        )
    return pl.DataFrame(
        rows,
        schema={
            "doc_id": pl.String,
            "bank": pl.String,
            "date": pl.Date,
            "doc_type": pl.String,
            "language": pl.String,
            "event_ts_utc": pl.Datetime("us", "UTC"),
            "timing": pl.String,
        },
    )


def window_moves(
    series_df: pl.DataFrame,
    series: str,
    timestamps: Sequence[datetime],
    pre: int = -1,
    post: int = 1,
    *,
    max_gap_days: int = 5,
    registry: dict[str, SeriesSpec] | None = None,
) -> list[float | None]:
    """Signed change of ``series`` over closes [t+pre, t+post] for each timestamp.

    ``t`` is the first close strictly after the timestamp, as in ``markets.event_window``.
    FX: log return x ``SERIES_SIGN``; yields: change in bp. ``None`` where data are missing.
    """
    spec = (registry or REGISTRY)[series]
    sub = series_df.filter(pl.col("series") == series).sort("date")
    dates: list[date] = sub["date"].to_list()
    closes: list[float] = sub["close"].to_list()
    close_ts = [spec.close_utc(d).timestamp() for d in dates]
    sign = SERIES_SIGN.get(series, 1)
    out: list[float | None] = []
    for ts in timestamps:
        i0 = bisect.bisect_right(close_ts, ts.astimezone(UTC).timestamp())
        a, b = i0 + pre, i0 + post
        if i0 >= len(dates) or a < 0 or b >= len(dates):
            out.append(None)
            continue
        if (dates[i0] - ts.astimezone(UTC).date()).days > max_gap_days:
            out.append(None)
            continue
        x, y = closes[a], closes[b]
        if spec.kind == "fx":
            out.append(sign * math.log(y / x) if x > 0 and y > 0 else None)
        else:
            out.append((y - x) * 100.0)
    return out


def tone_surprise(tone: Sequence[float], min_prior: int = 8) -> list[float | None]:
    """tone_t - E[tone_t | tone_{t-1}] with AR(1) fitted by OLS on observations before t only.

    The first ``min_prior`` documents (and any whose AR fit is degenerate) get ``None``.
    """
    x = np.asarray(tone, dtype=float)
    out: list[float | None] = []
    for t in range(len(x)):
        if t < max(min_prior, 2):
            out.append(None)
            continue
        prev, cur = x[: t - 1], x[1:t]  # pairs (tone_{s-1}, tone_s) for s < t
        if len(prev) < 2 or np.ptp(prev) < 1e-12:
            out.append(float(x[t] - cur.mean()) if len(cur) else None)
            continue
        slope, intercept = np.polyfit(prev, cur, 1)
        out.append(float(x[t] - (intercept + slope * x[t - 1])))
    return out


@dataclass(frozen=True)
class EventResult:
    """One (bank, series, scorer) event regression; mirrors ``schemas/EventResult.json``."""

    n: int
    beta: float
    se_hac: float
    t_stat: float
    p_value: float
    r2: float
    sign_agreement: float
    sign_p_value: float


def event_regression(move: Sequence[float], surprise: Sequence[float]) -> EventResult:
    """move = a + b * surprise + e; Newey-West SE (lag 1); sign agreement vs 0.5 (binomial)."""
    import statsmodels.api as sm
    from scipy.stats import binomtest

    y = np.asarray(move, dtype=float)
    x = np.asarray(surprise, dtype=float)
    if len(y) != len(x) or len(y) < 3:
        raise ValueError("need >= 3 paired observations")
    fit = sm.OLS(y, sm.add_constant(x)).fit(cov_type="HAC", cov_kwds={"maxlags": 1})
    nz = (y != 0) & (x != 0)
    agree = int(np.sum(np.sign(y[nz]) == np.sign(x[nz])))
    n_nz = int(nz.sum())
    return EventResult(
        n=len(y),
        beta=float(fit.params[1]),
        se_hac=float(fit.bse[1]),
        t_stat=float(fit.tvalues[1]),
        p_value=float(fit.pvalues[1]),
        r2=float(fit.rsquared),
        sign_agreement=agree / n_nz if n_nz else float("nan"),
        sign_p_value=float(binomtest(agree, n_nz, 0.5).pvalue) if n_nz else float("nan"),
    )


def placebo_dates(
    decision_dates: Sequence[date],
    candidate_dates: Sequence[date],
    n: int,
    *,
    min_gap: int = 5,
    seed: int = 20261014,
) -> list[date]:
    """``n`` business days from ``candidate_dates``, each >= ``min_gap`` days from any decision."""
    dec = sorted(decision_dates)
    ok = []
    for d in candidate_dates:
        if d.weekday() >= 5:
            continue
        i = bisect.bisect_left(dec, d)
        near = [abs((dec[j] - d).days) for j in (i - 1, i) if 0 <= j < len(dec)]
        if not near or min(near) >= min_gap:
            ok.append(d)
    if not ok:
        return []
    rng = np.random.default_rng(seed)
    return [ok[i] for i in rng.choice(len(ok), size=n, replace=len(ok) < n)]


def placebo_r2(
    surprises: Sequence[float],
    placebo_moves: Sequence[float | None],
    draws: int = 1000,
    seed: int = 20261014,
) -> np.ndarray:
    """R² of the real surprises regressed on market moves of random non-announcement days.

    ``placebo_moves`` is a pool of signed moves on eligible placebo days; each draw pairs the
    surprises with a random sample (without replacement where possible) from the pool.
    """
    pool = np.asarray([m for m in placebo_moves if m is not None and np.isfinite(m)], dtype=float)
    s = np.asarray(surprises, dtype=float)
    if len(pool) < 3 or len(s) < 3:
        return np.array([])
    rng = np.random.default_rng(seed)
    out = np.empty(draws)
    for k in range(draws):
        y = rng.choice(pool, size=len(s), replace=len(pool) < len(s))
        c = np.corrcoef(s, y)[0, 1]
        out[k] = 0.0 if not np.isfinite(c) else c * c
    return out
