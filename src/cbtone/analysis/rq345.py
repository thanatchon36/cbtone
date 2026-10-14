"""RQ3 (cross-lingual consistency), RQ4 (reliability, contamination), RQ5 (transfer).

All thresholds come from ``cbtone.eval.rules`` (frozen at ``prereg-v1``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import numpy as np
import polars as pl

from cbtone.analysis.common import Labels, tone_wide
from cbtone.eval import rules
from cbtone.eval.stats import (
    cross_lingual,
    icc_2_1,
    krippendorff_alpha_interval,
    macro_f1,
    macro_f1_ci,
    mean_diff_test,
)


# -- RQ3 -----------------------------------------------------------------------------------------
def rq3_rows(scores: pl.DataFrame, banks: Sequence[str], labels: Labels) -> list[dict[str, Any]]:
    """Native vs English consistency per (bank, scorer); unsupported scorers -> not applicable."""
    rows: list[dict[str, Any]] = []
    for bank in banks:
        for label, key in labels.items():
            en = tone_wide(scores, bank, {label: key})
            nat = tone_wide(scores, bank, {label: key}, native=True)
            pairs = en.join(nat, on="date", how="inner", suffix="_native")
            row: dict[str, Any] = {"bank": bank, "scorer": label, "n_pairs": pairs.height}
            if pairs.height == 0:
                row["status"] = "not applicable"
            elif pairs.height < 3:
                row["status"] = "too few pairs"
            else:
                cl = cross_lingual(
                    pairs[f"tone_{label}_native"].to_list(), pairs[f"tone_{label}"].to_list()
                )
                row |= {
                    "status": "ok",
                    "powered": rules.rq3_powered(cl.n),
                    "spearman": cl.spearman,
                    "mean_abs_diff": cl.mean_abs_diff,
                    "flip_rate": cl.flip_rate,
                    "consistent": cl.spearman >= rules.RQ3_RHO and cl.flip_rate <= rules.RQ3_FLIP,
                }
            rows.append(row)
    return rows


def rq3_verdict(
    rows: Sequence[dict[str, Any]], llm: str = "llm", required: Sequence[str] = ("bi", "bnm")
) -> str:
    cells = {r["bank"]: r for r in rows if r["scorer"] == llm}
    if any(
        b not in cells or cells[b].get("status") != "ok" or not cells[b]["powered"]
        for b in required
    ):
        return "untestable"
    return "supported" if all(cells[b]["consistent"] for b in required) else "refuted"


# -- RQ4a ----------------------------------------------------------------------------------------
def stability(matrix: np.ndarray) -> dict[str, float]:
    """Krippendorff alpha (interval) and ICC(2,1) for (units x configurations)."""
    m = np.asarray(matrix, dtype=float)
    complete = m[~np.isnan(m).any(axis=1)]
    return {
        "n_units": int(m.shape[0]),
        "n_complete": int(complete.shape[0]),
        "alpha": krippendorff_alpha_interval(m),
        "icc_2_1": icc_2_1(complete) if complete.shape[0] >= 2 else float("nan"),
    }


def stability_matrix(
    scores: pl.DataFrame, unit: str, configs: Mapping[str, tuple[str, str]]
) -> np.ndarray:
    """Pivot ``index`` by ``unit`` x config (config -> (scorer_id/prompt filter, variant))."""
    cols = []
    for name, (prompt_prefix, variant) in configs.items():
        part = scores.filter(
            pl.col("prompt_id").str.starts_with(prompt_prefix), pl.col("variant") == variant
        ).select(unit, pl.col("index").alias(name))
        cols.append(part.unique(unit, keep="first"))
    out = cols[0]
    for c in cols[1:]:
        out = out.join(c, on=unit, how="full", coalesce=True)
    return out.drop(unit).to_numpy().astype(float)


# -- RQ4b / RQ5 ----------------------------------------------------------------------------------
def classification_rows(
    gold: Sequence[str], preds: Mapping[str, Sequence[str]], reference: str = "dict"
) -> list[dict[str, Any]]:
    """Macro-F1 (with bootstrap CI) per scorer, and the difference vs ``reference``."""
    rows = []
    for name, p in preds.items():
        f, lo, hi = macro_f1_ci(gold, p)
        row: dict[str, Any] = {
            "scorer": name,
            "n": len(gold),
            "macro_f1": f,
            "f1_lo": lo,
            "f1_hi": hi,
        }
        if name != reference and reference in preds:
            d, dlo, dhi = macro_f1_ci(gold, p, y_pred_ref=preds[reference])
            row |= {"df1_vs_ref": d, "df1_lo": dlo, "df1_hi": dhi}
        rows.append(row)
    return rows


def rq5_rows(
    fomc_f1: Mapping[str, float], silver: pl.DataFrame, preds: Mapping[str, Sequence[str]]
) -> list[dict[str, Any]]:
    """Silver macro-F1 per (scorer, bank[-lang]) and drop vs the scorer's FOMC macro-F1."""
    rows = []
    groups = silver.with_columns(group=pl.concat_str("bank", pl.lit("-"), "lang"))
    for scorer, p in preds.items():
        frame = groups.with_columns(pred=pl.Series(list(p)))
        for g in sorted(frame["group"].unique().to_list()):
            sub = frame.filter(pl.col("group") == g, pl.col("pred").is_not_null())
            if sub.height == 0:
                continue
            f1 = macro_f1(sub["label"].to_list(), sub["pred"].to_list())
            rows.append(
                {
                    "scorer": scorer,
                    "group": g,
                    "n": sub.height,
                    "powered": sub.height >= rules.RQ5_MIN_SILVER,
                    "silver_macro_f1": f1,
                    "fomc_macro_f1": fomc_f1.get(scorer, float("nan")),
                    "drop": fomc_f1.get(scorer, float("nan")) - f1,
                }
            )
    return rows


# -- RQ4c ----------------------------------------------------------------------------------------
def post_cutoff_dll(
    pred_long: pl.DataFrame, cutoff: date, model: str, reference: str
) -> dict[str, Any]:
    """Pooled post-cutoff ΔLL(model vs reference) across banks (rows dated after ``cutoff``)."""
    a = pred_long.filter(pl.col("scorer") == model, pl.col("date") > cutoff).select(
        "bank", "date", "logloss"
    )
    b = pred_long.filter(pl.col("scorer") == reference, pl.col("date") > cutoff).select(
        "bank", "date", pl.col("logloss").alias("ref")
    )
    j = a.join(b, on=["bank", "date"], how="inner").sort("bank", "date")
    if j.height == 0:
        return {"n": 0, "status": "inconclusive"}
    d, lo, hi, p = mean_diff_test((j["ref"] - j["logloss"]).to_numpy())
    status = "ok" if j.height >= rules.RQ4C_MIN_POST_CUTOFF else "inconclusive"
    return {"n": j.height, "dll": d, "lo": lo, "hi": hi, "p": p, "status": status}


def survives_masked(
    full: float, full_lo: float, masked: float, masked_lo: float, masked_hi: float
) -> bool:
    """Same sign, CI excluding zero, and >= 50 % of the unmasked effect (RQ4c)."""
    if not np.isfinite(masked) or not np.isfinite(full) or full == 0:
        return False
    same_sign = np.sign(masked) == np.sign(full)
    excl = (masked_lo > 0) if full > 0 else (masked_hi < 0)
    return bool(same_sign and excl and abs(masked) >= rules.RQ4C_MIN_SHARE * abs(full))


def survives_post_cutoff(
    full: float, full_lo: float, full_hi: float, post: Mapping[str, Any]
) -> str:
    """'survives' | 'fails' | 'inconclusive' (N < 30 post-cutoff decisions)."""
    if post.get("status") != "ok":
        return "inconclusive"
    overlap = post["lo"] <= full_hi and full_lo <= post["hi"]
    return "survives" if np.sign(post["dll"]) == np.sign(full) and overlap else "fails"
