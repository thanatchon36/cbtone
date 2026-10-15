"""RQ2 table: event regressions per bank x series x scorer; H2a/H2b verdicts; RQ4c for RQ2.

Needs data/raw/markets/daily.parquet (built locally by `cbtone markets`; not committed).
Writes results/rq2_rows.csv, results/rq2_events.parquet (ids, timing, surprises, signed
moves) and results/rq2.json.
"""

from __future__ import annotations

import numpy as np
import polars as pl
from _common import (
    CUTOFF,
    HEADLINE_LLM,
    RESULTS,
    banks,
    load_scores,
    present_labels,
    write_json,
    write_rows,
)

from cbtone.analysis import rq2
from cbtone.analysis.rq345 import survives_masked
from cbtone.corpus import HEADLINE, load_frame, select

MARKETS = "data/raw/markets/daily.parquet"


def pooled_beta(ev: pl.DataFrame, label: str, after=None) -> dict[str, float]:
    """Bank fixed-effects (within) FX regression pooled across headline banks; HAC lag 1."""
    import statsmodels.api as sm

    f = ev.drop_nulls(["move_fx", f"surprise_{label}"])
    if after is not None:
        f = f.filter(pl.col("date") > after)
    if f.height < 3:
        return {"n": f.height}
    f = f.with_columns(
        y=pl.col("move_fx") - pl.col("move_fx").mean().over("bank"),
        x=pl.col(f"surprise_{label}") - pl.col(f"surprise_{label}").mean().over("bank"),
    ).sort("date")
    fit = sm.OLS(f["y"].to_numpy(), f["x"].to_numpy()).fit(cov_type="HAC", cov_kwds={"maxlags": 1})
    b, se = float(fit.params[0]), float(fit.bse[0])
    return {
        "n": f.height,
        "beta": b,
        "lo": b - 1.96 * se,
        "hi": b + 1.96 * se,
        "p": float(fit.pvalues[0]),
    }


SERIES_LABEL = {  # display names, as in the paper's Table 4
    "DX-Y.NYB": "USD index",
    "DGS2": "US 2Y",
    "EURUSD=X": "EUR/USD",
    "EA2Y": "EA 2Y",
    "GBPUSD=X": "GBP/USD",
    "GB2Y": "UK 2Y",
    "AUDUSD=X": "AUD/USD",
    "AU2Y": "AU 2Y",
    "USDSGD=X": "USD/SGD",
    "USDIDR=X": "USD/IDR",
    "USDMYR=X": "USD/MYR",
}


def main() -> None:
    market = pl.read_parquet(MARKETS)
    decisions = pl.read_parquet("data/corpus/decisions.parquet")
    scores = load_scores()
    frame = load_frame()
    rows, events = [], []
    for bank in banks():
        labels = present_labels(scores, bank, ["dict", "llm", "llm_masked", "ft", "fomc_roberta"])
        if not {"dict", "llm"} <= set(labels):
            continue
        docs = select(frame, [bank])
        main_labels = {k: v for k, v in labels.items() if k != "llm_masked"}
        ev = rq2.bank_events(docs, scores, market, bank, main_labels)
        dec_dates = decisions.filter(pl.col("bank") == bank)["date"].to_list()
        rows += rq2.bank_rows(ev, market, bank, main_labels, dec_dates)
        if "llm_masked" in labels:
            evm = rq2.bank_events(
                docs,
                scores,
                market,
                bank,
                {"dict": labels["dict"], "llm_masked": labels["llm_masked"]},
            )
            rm = rq2.bank_rows(
                evm,
                market,
                bank,
                {"dict": labels["dict"], "llm_masked": labels["llm_masked"]},
                dec_dates,
            )
            rows += [r for r in rm if r["scorer"] == "llm_masked"]
            ev = ev.join(evm.select("doc_id", "surprise_llm_masked"), on="doc_id", how="left")
        keep = [c for c in ev.columns if c.startswith(("move_", "surprise_", "tone_"))]
        events.append(
            ev.select("doc_id", "bank", "date", "timing", *keep).with_columns(pl.col("bank"))
        )
        print(f"{bank}: {ev.height} events", flush=True)
    ev_all = pl.concat(events, how="diagonal_relaxed")
    ev_all.write_parquet(RESULTS / "rq2_events.parquet")
    hl_rows = [r for r in rows if r["bank"] in HEADLINE]
    v = rq2.verdict(hl_rows, llm="llm")
    hl = ev_all.filter(pl.col("bank").is_in(list(HEADLINE)))
    full = pooled_beta(hl, "llm")
    masked = pooled_beta(hl, "llm_masked") if "surprise_llm_masked" in hl.columns else {"n": 0}
    post = pooled_beta(hl, "llm", after=CUTOFF[HEADLINE_LLM])
    post_status = "ok" if post.get("n", 0) >= 30 and "beta" in post else "inconclusive"
    if post_status == "ok" and "beta" in full:
        overlap = post["lo"] <= full["hi"] and full["lo"] <= post["hi"]
        post_verdict = (
            "survives" if np.sign(post["beta"]) == np.sign(full["beta"]) and overlap else "fails"
        )
    else:
        post_verdict = "inconclusive"
    sm = (
        survives_masked(full["beta"], full["lo"], masked["beta"], masked["lo"], masked["hi"])
        if "beta" in full and "beta" in masked
        else False
    )
    rq4c = {
        "pooled_fx_beta": full,
        "masked_pooled_fx_beta": masked,
        "post_cutoff_pooled_fx_beta": post,
        "survives_masked": sm,
        "survives_post_cutoff": post_verdict,
    }
    rq4c["robust"] = sm and post_verdict == "survives"
    write_rows("rq2_rows", rows)
    # D21: pre-registered descriptive comparison of the LLM against the transformer scorer (ΔR²)
    cells = [
        r
        for r in hl_rows
        if r["scorer"] == "llm"
        and r["subset"] == "all"
        and r.get("powered")
        and "dr2_vs_transformer" in r
    ]
    tr_cells = [
        r
        for r in hl_rows
        if r["scorer"] == "fomc_roberta" and r["subset"] == "all" and r.get("powered") and "r2" in r
    ]
    transformer: dict[str, object] = {}
    if cells:

        def cell(r: dict[str, object]) -> dict[str, object]:
            return {
                "bank": r["bank"],
                "series": r["series"],
                "label": f"{SERIES_LABEL.get(str(r['series']), r['series'])}, "
                f"{str(r['bank']).upper()}",
                "dr2": r["dr2_vs_transformer"],
                "lo": r["dr2_tr_lo"],
                "hi": r["dr2_tr_hi"],
            }

        transformer = {
            "n_cells": len(cells),
            "n_ci_excluding_zero": sum(r["dr2_tr_lo"] > 0 or r["dr2_tr_hi"] < 0 for r in cells),
            "n_llm_higher": sum(r["dr2_vs_transformer"] > 0 for r in cells),
            "min": cell(min(cells, key=lambda r: r["dr2_vs_transformer"])),
            "max": cell(max(cells, key=lambda r: r["dr2_vs_transformer"])),
            "n_transformer_cells": len(tr_cells),
            "n_transformer_above_placebo": sum(
                r["r2"] > r.get("placebo_r2_p95", float("inf")) for r in tr_cells
            ),
        }
    write_json("rq2", {"verdict": v, "rq4c": rq4c, "transformer": transformer, "rows": rows})
    print(v, rq4c)


if __name__ == "__main__":
    main()
