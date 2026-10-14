"""RQ1 — does tone at decision t improve out-of-sample prediction of decision t+1?

Implements RESEARCH_QUESTIONS.md RQ1: rolling-origin ordered logit per bank and scorer vs the
persistence baseline; ΔLL comparisons with block-bootstrap CIs and two-sided bootstrap p-values,
Holm-adjusted across powered headline banks; shuffled-date-tone and permuted-label placebos.
A bank counts for H1 when, for the LLM, both ΔLL(vs persistence) and ΔLL(vs dictionary) have a
positive point estimate with Holm-adjusted p < 0.05, and the real ΔLL(vs persistence) exceeds both
placebos' 95th percentiles.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import numpy as np
import polars as pl

from cbtone.analysis.common import Labels, decision_frame, tone_wide
from cbtone.eval import rules
from cbtone.eval.rolling import add_features, auroc_hike_vs_cut, rolling_origin
from cbtone.eval.stats import SEED, holm, mean_diff_test


def _mean(series: pl.Series) -> float:
    v = series.mean()
    return float(v) if isinstance(v, int | float) else float("nan")


def _placebo_chunk(args: tuple[pl.DataFrame, str, int, int, int]) -> list[float]:
    """ΔLL(model vs persistence) under ``kind`` permutation for permutation seeds [start, stop)."""
    df, kind, start, stop, seed = args
    out = []
    for k in range(start, stop):
        rng = np.random.default_rng(seed + k)
        if kind == "tone":
            perm = df.with_columns(tone=pl.Series(rng.permutation(df["tone"].to_numpy())))
            perm = add_features(perm.drop("dtone"))
        else:  # permuted labels: next_direction shuffled; last_direction re-derived from it
            nxt = rng.permutation(df["next_direction"].to_numpy())
            perm = df.with_columns(
                next_direction=pl.Series(nxt),
                last_direction=pl.Series(np.concatenate([[df["last_direction"][0]], nxt[:-1]])),
            )
        model = rolling_origin(perm, ["tone", "dtone"])
        base = rolling_origin(perm, None)
        out.append(_mean(base["logloss"] - model["logloss"]) if model.height else np.nan)
    return out


def placebo_dll(
    df: pl.DataFrame, kind: str, perms: int = 1000, seed: int = SEED, workers: int = 8
) -> np.ndarray:
    """Placebo distribution of ΔLL(model vs persistence); ``kind`` is "tone" or "labels"."""
    step = max(1, perms // (workers * 4))
    chunks = [(df, kind, s, min(s + step, perms), seed) for s in range(0, perms, step)]
    if workers <= 1:
        res = [_placebo_chunk(c) for c in chunks]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(_placebo_chunk, chunks))
    return np.array([v for chunk in res for v in chunk], dtype=float)


def bank_rows(
    decisions: pl.DataFrame,
    scores: pl.DataFrame,
    bank: str,
    labels: Labels,
    *,
    llm: str = "llm",
    dictionary: str = "dict",
    perms: int = 1000,
    workers: int = 8,
) -> tuple[list[dict[str, Any]], pl.DataFrame]:
    """Per-scorer result rows for one bank, and the aligned OOS predictions (long format)."""
    dec = decision_frame(decisions, bank)
    tones = tone_wide(scores, bank, labels)
    df = dec.join(tones, on="date", how="inner").sort("date")
    if df.height == 0:
        return [], pl.DataFrame()
    base = rolling_origin(df, None)
    n_oos = base.height
    n_hike = int((base["y"] == "hike").sum()) if n_oos else 0
    n_cut = int((base["y"] == "cut").sum()) if n_oos else 0
    powered = rules.rq1_powered(n_oos, n_hike, n_cut)
    preds = {"persistence": base}
    for label in labels:
        frame = add_features(df.with_columns(tone=pl.col(f"tone_{label}")))
        preds[label] = rolling_origin(frame, ["tone", "dtone"])
    rows: list[dict[str, Any]] = []
    for label, pred in preds.items():
        row: dict[str, Any] = {
            "bank": bank,
            "scorer": label,
            "n_decisions": df.height,
            "n_oos": n_oos,
            "n_oos_hike": n_hike,
            "n_oos_cut": n_cut,
            "powered": powered,
            "logloss": _mean(pred["logloss"]) if n_oos else np.nan,
            "auroc": auroc_hike_vs_cut(pred) if n_oos else np.nan,
            "fallback_share": _mean(pred["fallback"].cast(pl.Float64)) if n_oos else np.nan,
        }
        if label != "persistence" and n_oos:
            d = (base["logloss"] - pred["logloss"]).to_numpy()
            row["dll_vs_pers"], row["dll_vs_pers_lo"], row["dll_vs_pers_hi"], row["p_vs_pers"] = (
                mean_diff_test(d)
            )
            if label != dictionary and dictionary in preds:
                d2 = (preds[dictionary]["logloss"] - pred["logloss"]).to_numpy()
                (
                    row["dll_vs_dict"],
                    row["dll_vs_dict_lo"],
                    row["dll_vs_dict_hi"],
                    row["p_vs_dict"],
                ) = mean_diff_test(d2)
        rows.append(row)
    if n_oos and llm in labels:
        frame = add_features(df.with_columns(tone=pl.col(f"tone_{llm}")))
        for kind in ("tone", "labels"):
            dist = placebo_dll(frame, kind, perms=perms, workers=workers)
            p95 = float(np.nanquantile(dist, 0.95)) if np.isfinite(dist).any() else np.nan
            for row in rows:
                if row["scorer"] == llm:
                    row[f"placebo_{kind}_p95"] = p95
                    row[f"placebo_{kind}_n"] = int(np.isfinite(dist).sum())
    long = pl.concat(
        [
            p.with_columns(pl.lit(bank).alias("bank"), pl.lit(k).alias("scorer"))
            for k, p in preds.items()
        ]
    )
    return rows, long


def verdict(rows: Sequence[dict[str, Any]], llm: str = "llm") -> dict[str, Any]:
    """H1 verdict with Holm across powered banks (RESEARCH_QUESTIONS.md RQ1, §0.6, §0.7)."""
    llm_rows = [r for r in rows if r["scorer"] == llm and "dll_vs_pers" in r]
    powered = {r["bank"]: bool(r["powered"]) for r in llm_rows}
    pw = [r for r in llm_rows if r["powered"]]
    adj_pers = holm([r["p_vs_pers"] for r in pw]) if pw else []
    adj_dict = holm([r.get("p_vs_dict", 1.0) for r in pw]) if pw else []
    success: dict[str, bool] = {}
    for r, ap, ad in zip(pw, adj_pers, adj_dict, strict=True):
        r["p_vs_pers_holm"], r["p_vs_dict_holm"] = ap, ad
        placebo_ok = all(
            np.isfinite(r.get(f"placebo_{k}_p95", np.nan))
            and r["dll_vs_pers"] > r[f"placebo_{k}_p95"]
            for k in ("tone", "labels")
        )
        r["passes_placebo"] = placebo_ok
        success[r["bank"]] = (
            r["dll_vs_pers"] > 0
            and ap < 0.05
            and r.get("dll_vs_dict", -1) > 0
            and ad < 0.05
            and placebo_ok
        )
        r["h1_success"] = success[r["bank"]]
    v = rules.majority(success, powered)
    return {
        "verdict": v.verdict,
        "n_powered": v.n_powered,
        "n_success": v.n_success,
        "success": success,
    }
