"""Statistics used by the pre-registered analysis (RESEARCH_QUESTIONS.md §0.6, RQ3-RQ5).

- ``block_bootstrap_ci``: moving-block bootstrap (Künsch 1989) percentile CI of a statistic of
  one or more aligned arrays; block length 4, 2,000 replicates by default.
- ``holm``: Holm (1979) step-down adjusted p-values.
- ``icc_2_1``: ICC(2,1), two-way random effects, absolute agreement, single rater
  (Shrout & Fleiss 1979).
- ``krippendorff_alpha_interval``: Krippendorff's alpha, interval metric (Krippendorff 2004);
  missing values allowed.
- ``cross_lingual``: Spearman rho, mean |delta|, stance-flip rate (RQ3).
- ``macro_f1`` and ``macro_f1_ci``: 3-class macro-F1 with an i.i.d. bootstrap CI (RQ4b, RQ5).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

SEED = 20261014
LABELS = ("dovish", "neutral", "hawkish")


def _block_indices(n: int, block: int, rng: np.random.Generator) -> np.ndarray:
    block = max(1, min(block, n))
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=n_blocks)
    idx = (starts[:, None] + np.arange(block)[None, :]).ravel()
    return idx[:n]


def block_bootstrap_ci(
    stat: Callable[..., float],
    *arrays: Sequence[float] | np.ndarray,
    block: int = 4,
    reps: int = 2000,
    alpha: float = 0.05,
    seed: int = SEED,
) -> tuple[float, float, float]:
    """(point, lo, hi): ``stat(*arrays)`` and its moving-block bootstrap percentile CI.

    Arrays are resampled jointly (same block indices), preserving their alignment and the
    serial dependence of a bank's decision sequence.
    """
    arrs = [np.asarray(a, dtype=float) for a in arrays]
    n = len(arrs[0])
    if n == 0 or any(len(a) != n for a in arrs):
        raise ValueError("arrays must be non-empty and of equal length")
    point = float(stat(*arrs))
    rng = np.random.default_rng(seed)
    draws = np.empty(reps)
    for k in range(reps):
        idx = _block_indices(n, block, rng)
        draws[k] = stat(*(a[idx] for a in arrs))
    draws = draws[np.isfinite(draws)]
    lo, hi = np.quantile(draws, [alpha / 2, 1 - alpha / 2]) if len(draws) else (np.nan, np.nan)
    return point, float(lo), float(hi)


def mean_diff_ci(
    diff: Sequence[float], block: int = 4, reps: int = 2000, seed: int = SEED
) -> tuple[float, float, float]:
    """Block-bootstrap CI of the mean of a per-observation difference (e.g. log-loss gain)."""
    return block_bootstrap_ci(lambda d: float(np.mean(d)), diff, block=block, reps=reps, seed=seed)


def holm(pvalues: Sequence[float]) -> list[float]:
    """Holm-adjusted p-values, in the input order."""
    p = np.asarray(pvalues, dtype=float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return adj.tolist()


def icc_2_1(ratings: np.ndarray) -> float:
    """ICC(2,1) for an (n subjects x k raters) matrix without missing values."""
    x = np.asarray(ratings, dtype=float)
    if x.ndim != 2 or x.shape[0] < 2 or x.shape[1] < 2 or np.isnan(x).any():
        raise ValueError("need a complete n>=2 x k>=2 matrix")
    n, k = x.shape
    grand = x.mean()
    ss_rows = k * ((x.mean(axis=1) - grand) ** 2).sum()
    ss_cols = n * ((x.mean(axis=0) - grand) ** 2).sum()
    ss_err = ((x - grand) ** 2).sum() - ss_rows - ss_cols
    msr = ss_rows / (n - 1)
    msc = ss_cols / (k - 1)
    mse = ss_err / ((n - 1) * (k - 1))
    denom = msr + (k - 1) * mse + k * (msc - mse) / n
    return float((msr - mse) / denom) if denom != 0 else float("nan")


def krippendorff_alpha_interval(ratings: np.ndarray) -> float:
    """Krippendorff's alpha, interval metric, for (units x coders); NaN = missing."""
    x = np.asarray(ratings, dtype=float)
    units = [row[~np.isnan(row)] for row in x]
    units = [u for u in units if len(u) >= 2]
    if not units:
        return float("nan")
    values = np.concatenate(units)
    n = len(values)

    def pair_sq(a: np.ndarray) -> float:  # sum over ordered pairs i != j of (a_i - a_j)^2
        m = len(a)
        return float(2 * (m * np.sum(a * a) - np.sum(a) ** 2))

    d_o = sum(pair_sq(u) / (len(u) - 1) for u in units) / n
    d_e = pair_sq(values) / (n * (n - 1))
    return float(1.0 - d_o / d_e) if d_e > 0 else float("nan")


@dataclass(frozen=True)
class CrossLingual:
    n: int
    spearman: float
    mean_abs_diff: float
    flip_rate: float


def cross_lingual(
    native: Sequence[float], english: Sequence[float], dead_zone: float = 0.1
) -> CrossLingual:
    """RQ3 metrics on paired indices. A flip = opposite signs with both |index| > ``dead_zone``."""
    from scipy.stats import spearmanr

    a = np.asarray(native, dtype=float)
    b = np.asarray(english, dtype=float)
    if len(a) != len(b) or len(a) < 3:
        raise ValueError("need >= 3 aligned pairs")
    rho = spearmanr(a, b).statistic
    strong = (np.abs(a) > dead_zone) & (np.abs(b) > dead_zone)
    flips = strong & (np.sign(a) != np.sign(b))
    return CrossLingual(
        n=len(a),
        spearman=float(rho),
        mean_abs_diff=float(np.mean(np.abs(a - b))),
        flip_rate=float(flips.sum() / len(a)),
    )


def macro_f1(y_true: Sequence[str], y_pred: Sequence[str]) -> float:
    from sklearn.metrics import f1_score

    return float(
        f1_score(list(y_true), list(y_pred), labels=list(LABELS), average="macro", zero_division=0)
    )


def macro_f1_ci(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    y_pred_ref: Sequence[str] | None = None,
    reps: int = 2000,
    seed: int = SEED,
) -> tuple[float, float, float]:
    """Macro-F1 (minus the reference's, if ``y_pred_ref``) with an i.i.d. bootstrap CI."""
    t = np.asarray(y_true)
    p = np.asarray(y_pred)
    r = np.asarray(y_pred_ref) if y_pred_ref is not None else None

    def stat(idx: np.ndarray) -> float:
        f = macro_f1(t[idx], p[idx])
        return f - macro_f1(t[idx], r[idx]) if r is not None else f

    n = len(t)
    point = stat(np.arange(n))
    rng = np.random.default_rng(seed)
    draws = np.array([stat(rng.integers(0, n, size=n)) for _ in range(reps)])
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return float(point), float(lo), float(hi)
