"""RQ2 — does the tone surprise explain 1-day FX and 2y-yield moves around announcements?

Implements RESEARCH_QUESTIONS.md RQ2: tone surprise from an expanding AR(1) on prior documents;
signed [t-1, t+1] moves (§0.4 timing rule); OLS with HAC errors per (bank, series, scorer);
ΔR² (LLM - dictionary) with a paired block bootstrap; non-announcement-day placebo R².
H2a cell success: beta > 0, Holm-adjusted p < 0.05, R² above the placebo's 95th percentile.
H2b cell success: ΔR² > 0 with Holm-adjusted bootstrap p < 0.05.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from cbtone.analysis.common import Labels, tone_wide
from cbtone.eval import rules
from cbtone.eval.stats import SEED, _block_indices, holm
from cbtone.events.engine import (
    BANK_SERIES,
    BANK_TZ,
    build_events,
    event_regression,
    placebo_dates,
    placebo_r2,
    tone_surprise,
    window_moves,
)

BOE_ROBUST_FROM = date(2013, 1, 1)  # A3: BoE release times documented from 2013


def _r2(y: np.ndarray, x: np.ndarray) -> float:
    if len(y) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    c = np.corrcoef(x, y)[0, 1]
    return float(c * c)


def delta_r2_test(
    y: np.ndarray, x_a: np.ndarray, x_b: np.ndarray, reps: int = 2000, seed: int = SEED
) -> tuple[float, float, float, float]:
    """ΔR² = R²(y~x_a) - R²(y~x_b) on the same events; block bootstrap CI and two-sided p."""
    point = _r2(y, x_a) - _r2(y, x_b)
    rng = np.random.default_rng(seed)
    n = len(y)
    draws = []
    for _ in range(reps):
        idx = _block_indices(n, 4, rng)
        draws.append(_r2(y[idx], x_a[idx]) - _r2(y[idx], x_b[idx]))
    arr = np.asarray(draws, dtype=float)
    arr = arr[np.isfinite(arr)]
    if not len(arr):
        return point, float("nan"), float("nan"), 1.0
    lo, hi = np.quantile(arr, [0.025, 0.975])
    p = min(1.0, 2 * min(float(np.mean(arr <= 0)), float(np.mean(arr >= 0))))
    return float(point), float(lo), float(hi), p


def bank_events(
    docs: pl.DataFrame, scores: pl.DataFrame, market: pl.DataFrame, bank: str, labels: Labels
) -> pl.DataFrame:
    """One row per primary document: timing, signed moves, tone and surprise per label."""
    ev = build_events(docs.filter(pl.col("bank") == bank))
    tones = tone_wide(scores, bank, labels)
    ev = ev.join(tones, on="date", how="inner").sort("date")
    if ev.height == 0:
        return ev
    ts = ev["event_ts_utc"].to_list()
    for kind, series in BANK_SERIES[bank].items():
        ev = ev.with_columns(
            pl.Series(f"move_{kind}", window_moves(market, series, ts), dtype=pl.Float64)
        )
    for label in labels:
        s = tone_surprise(ev[f"tone_{label}"].to_list())
        ev = ev.with_columns(pl.Series(f"surprise_{label}", s, dtype=pl.Float64))
    return ev


def placebo_pool(
    market: pl.DataFrame, series: str, bank: str, decision_dates: Sequence[date], n: int = 1000
) -> list[float | None]:
    """Signed moves on ``n`` non-announcement business days (00:00 local, as day-level events)."""
    sub = market.filter(pl.col("series") == series)
    if sub.height == 0 or not decision_dates:
        return []
    lo, hi = min(decision_dates), max(decision_dates)
    cand = sub.filter(pl.col("date").is_between(lo, hi))["date"].to_list()
    days = placebo_dates(decision_dates, cand, n)
    tz = ZoneInfo(BANK_TZ[bank])
    ts = [datetime.combine(d, time(0, 0), tzinfo=tz) for d in days]
    return window_moves(market, series, ts)


def bank_rows(
    ev: pl.DataFrame,
    market: pl.DataFrame,
    bank: str,
    labels: Labels,
    decision_dates: Sequence[date],
    *,
    llm: str = "llm",
    dictionary: str = "dict",
    placebo_draws: int = 1000,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if ev.height == 0:
        return rows
    subsets: list[tuple[str, pl.DataFrame]] = [
        ("all", ev),
        ("exact", ev.filter(pl.col("timing") == "exact")),
    ]
    if bank == "boe":
        subsets.append(("from2013", ev.filter(pl.col("date") >= BOE_ROBUST_FROM)))
    for kind, series in BANK_SERIES[bank].items():
        pool = placebo_pool(market, series, bank, decision_dates)
        for subset, frame in subsets:
            for label in labels:
                cols = [f"move_{kind}", f"surprise_{label}"]
                f = frame.drop_nulls(cols)
                n = f.height
                row: dict[str, Any] = {
                    "bank": bank,
                    "series": series,
                    "kind": kind,
                    "subset": subset,
                    "scorer": label,
                    "n_events": n,
                    "powered": rules.rq2_powered(n),
                    "n_day_timing": int((f["timing"] == "day").sum()) if n else 0,
                }
                if n >= 3:
                    r = event_regression(f[cols[0]].to_list(), f[cols[1]].to_list())
                    row |= {
                        "beta": r.beta,
                        "se_hac": r.se_hac,
                        "t_stat": r.t_stat,
                        "p_value": r.p_value,
                        "r2": r.r2,
                        "sign_agreement": r.sign_agreement,
                        "sign_p_value": r.sign_p_value,
                    }
                    if subset == "all":
                        dist = placebo_r2(f[cols[1]].to_list(), pool, draws=placebo_draws)
                        row["placebo_r2_p95"] = (
                            float(np.quantile(dist, 0.95)) if len(dist) else np.nan
                        )
                if label != dictionary and dictionary in labels and n >= 3:
                    both = frame.drop_nulls(
                        [cols[0], f"surprise_{label}", f"surprise_{dictionary}"]
                    )
                    if both.height >= 3:
                        d = delta_r2_test(
                            both[cols[0]].to_numpy(),
                            both[f"surprise_{label}"].to_numpy(),
                            both[f"surprise_{dictionary}"].to_numpy(),
                        )
                        row["dr2_vs_dict"], row["dr2_lo"], row["dr2_hi"], row["p_dr2"] = d
                rows.append(row)
    return rows


def verdict(rows: Sequence[dict[str, Any]], llm: str = "llm") -> dict[str, Any]:
    """H2a / H2b over powered (bank, series) cells of the main subset, Holm-adjusted."""
    cells = [r for r in rows if r["scorer"] == llm and r["subset"] == "all" and "beta" in r]
    powered = {f"{r['bank']}:{r['series']}": bool(r["powered"]) for r in cells}
    pw = [r for r in cells if r["powered"]]
    # one-sided test of beta > 0 from the two-sided HAC p
    p_one = [r["p_value"] / 2 if r["beta"] > 0 else 1 - r["p_value"] / 2 for r in pw]
    adj_a = holm(p_one) if pw else []
    adj_b = holm([r.get("p_dr2", 1.0) for r in pw]) if pw else []
    s_a: dict[str, bool] = {}
    s_b: dict[str, bool] = {}
    for r, pa, pb in zip(pw, adj_a, adj_b, strict=True):
        key = f"{r['bank']}:{r['series']}"
        r["p_beta_holm"], r["p_dr2_holm"] = pa, pb
        placebo_ok = np.isfinite(r.get("placebo_r2_p95", np.nan)) and r["r2"] > r["placebo_r2_p95"]
        s_a[key] = r["beta"] > 0 and pa < 0.05 and bool(placebo_ok)
        s_b[key] = r.get("dr2_vs_dict", -1) > 0 and pb < 0.05
        r["h2a_success"], r["h2b_success"] = s_a[key], s_b[key]
    va, vb = rules.majority(s_a, powered), rules.majority(s_b, powered)
    return {
        "h2a": {"verdict": va.verdict, "n_powered": va.n_powered, "n_success": va.n_success},
        "h2b": {"verdict": vb.verdict, "n_powered": vb.n_powered, "n_success": vb.n_success},
    }
