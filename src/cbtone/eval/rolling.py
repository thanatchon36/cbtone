"""Rolling-origin prediction of the next policy decision (RESEARCH_QUESTIONS.md RQ1).

Ordered logit (cut < hold < hike) on (tone_t, Δtone_t, last_direction_t), refit at every step on
an expanding window whose initial size is 40 % of the bank's decisions (at least 30), predicting
one step ahead; persistence baseline = Laplace-smoothed P(next | last) from the same window.
Metrics: multiclass log-loss (primary) and AUROC hike-vs-cut (secondary).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import polars as pl

DIRS = ("cut", "hold", "hike")
EPS = 1e-6


def initial_window(n: int, frac: float = 0.4, minimum: int = 30) -> int:
    return max(minimum, math.ceil(frac * n))


def _persistence(train_last: Sequence[str], train_next: Sequence[str], last: str) -> np.ndarray:
    counts = np.ones(3)  # Laplace smoothing
    for lst, nxt in zip(train_last, train_next, strict=True):
        if lst == last:
            counts[DIRS.index(nxt)] += 1
    return np.asarray(counts / counts.sum(), dtype=float)


def _design(df: pl.DataFrame, features: Sequence[str]) -> np.ndarray:
    cols = [df[f].to_numpy().astype(float) for f in features]
    last = df["last_direction"].to_list()
    cols.append(np.array([1.0 if v == "hike" else 0.0 for v in last]))
    cols.append(np.array([1.0 if v == "cut" else 0.0 for v in last]))
    return np.column_stack(cols)


def _ordered_logit_predict(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    init: np.ndarray | None = None,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """(P(cut, hold, hike) for one test row, fitted params), or (None, None) if impossible.

    Needs all three classes in the training window; constant columns are dropped.
    """
    from cbtone.eval import ordinal

    if set(y_train.tolist()) != {0, 1, 2}:
        return None, None
    keep = x_train.std(axis=0) > 0
    if not keep.any():
        return None, None
    start = init if init is not None and len(init) == int(keep.sum()) + 2 else None
    params = ordinal.fit(x_train[:, keep], y_train, init=start)
    probs = ordinal.predict_proba(x_test[:, keep], params)[0]
    if not np.all(np.isfinite(probs)):
        return None, None
    return np.asarray(probs, dtype=float), params


def rolling_origin(
    df: pl.DataFrame,
    features: Sequence[str] | None,
    init_frac: float = 0.4,
    min_init: int = 30,
) -> pl.DataFrame:
    """One-step-ahead predictions for each decision after the initial window.

    ``df`` (one bank, sorted by date) needs ``date, last_direction, next_direction`` and the
    ``features`` columns. ``features=None`` gives the persistence baseline. Returns
    ``date, y, p_cut, p_hold, p_hike, logloss, fallback`` (fallback = ordered logit could not be
    fit at that step and persistence was used; reported, not hidden).
    """
    df = df.sort("date")
    n = df.height
    k0 = initial_window(n, init_frac, min_init)
    if n <= k0:
        return pl.DataFrame(
            schema={
                "date": pl.Date,
                "y": pl.String,
                "p_cut": pl.Float64,
                "p_hold": pl.Float64,
                "p_hike": pl.Float64,
                "logloss": pl.Float64,
                "fallback": pl.Boolean,
            }
        )
    y_all = np.array([DIRS.index(v) for v in df["next_direction"].to_list()])
    last_all = df["last_direction"].to_list()
    nxt_all = df["next_direction"].to_list()
    x_all = _design(df, features) if features else None
    rows = []
    warm: np.ndarray | None = None
    for t in range(k0, n):
        probs = None
        if x_all is not None:
            probs, fitted = _ordered_logit_predict(x_all[:t], y_all[:t], x_all[t : t + 1], warm)
            warm = fitted if fitted is not None else warm
        fallback = x_all is not None and probs is None
        if probs is None:
            probs = _persistence(last_all[:t], nxt_all[:t], last_all[t])
        probs = np.clip(probs, EPS, 1.0)
        probs = probs / probs.sum()
        rows.append(
            {
                "date": df["date"][t],
                "y": nxt_all[t],
                "p_cut": float(probs[0]),
                "p_hold": float(probs[1]),
                "p_hike": float(probs[2]),
                "logloss": float(-math.log(probs[y_all[t]])),
                "fallback": fallback,
            }
        )
    return pl.DataFrame(rows)


def auroc_hike_vs_cut(pred: pl.DataFrame) -> float:
    """AUROC on OOS rows whose actual next is hike or cut; score = P(hike) / (P(hike) + P(cut))."""
    from sklearn.metrics import roc_auc_score

    sub = pred.filter(pl.col("y").is_in(["hike", "cut"]))
    if sub["y"].n_unique() < 2:
        return float("nan")
    score = (sub["p_hike"] / (sub["p_hike"] + sub["p_cut"])).to_numpy()
    return float(roc_auc_score((sub["y"] == "hike").to_numpy(), score))


def add_features(df: pl.DataFrame, tone_col: str = "tone") -> pl.DataFrame:
    """Add ``Δtone`` (first difference within the frame; first row 0) and keep ``tone``."""
    return df.sort("date").with_columns(
        dtone=(pl.col(tone_col) - pl.col(tone_col).shift(1)).fill_null(0.0)
    )
