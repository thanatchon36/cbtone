"""RQ1 table: next-decision prediction per bank and scorer, H1 verdict, RQ4c checks for RQ1.

Writes results/rq1_rows.csv, results/rq1_predictions.parquet and results/rq1.json.
"""

from __future__ import annotations

import os

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

from cbtone.analysis import rq1
from cbtone.analysis.rq345 import post_cutoff_dll, survives_masked, survives_post_cutoff
from cbtone.corpus import HEADLINE
from cbtone.eval.stats import mean_diff_test

PERMS = int(os.environ.get("CBTONE_PERMS", "1000"))
WORKERS = int(os.environ.get("CBTONE_WORKERS", "8"))


def main() -> None:
    decisions = pl.read_parquet("data/corpus/decisions.parquet")
    scores = load_scores()
    rows, preds = [], []
    for bank in banks():
        labels = present_labels(scores, bank, ["dict", "llm", "ft", "fomc_roberta"])
        if not {"dict", "llm"} <= set(labels):
            print(f"{bank}: missing dict/llm scores, skipped")
            continue
        r, p = rq1.bank_rows(decisions, scores, bank, labels, perms=PERMS, workers=WORKERS)
        rows += r
        preds.append(p)
        masked = present_labels(scores, bank, ["dict", "llm_masked"])
        if "llm_masked" in masked:
            rm, pm = rq1.bank_rows(
                decisions, scores, bank, masked, llm="llm_masked", perms=0, workers=1
            )
            rows += [x for x in rm if x["scorer"] == "llm_masked"]
            preds.append(pm.filter(pl.col("scorer") == "llm_masked"))
        print(f"{bank}: done", flush=True)
    headline_rows = [r for r in rows if r["bank"] in HEADLINE]
    v = rq1.verdict(headline_rows, llm="llm")
    pred_long = pl.concat(preds) if preds else pl.DataFrame()
    pred_long.write_parquet(RESULTS / "rq1_predictions.parquet")

    # RQ4c for RQ1 (pooled headline ΔLL, LLM vs dictionary)
    hl = pred_long.filter(pl.col("bank").is_in(list(HEADLINE)))
    a = hl.filter(pl.col("scorer") == "llm").select("bank", "date", "logloss")
    b = hl.filter(pl.col("scorer") == "dict").select("bank", "date", pl.col("logloss").alias("ref"))
    j = a.join(b, on=["bank", "date"]).sort("bank", "date")
    full = mean_diff_test((j["ref"] - j["logloss"]).to_numpy()) if j.height else (float("nan"),) * 4
    am = hl.filter(pl.col("scorer") == "llm_masked").select("bank", "date", "logloss")
    jm = am.join(b, on=["bank", "date"]).sort("bank", "date")
    masked = (
        mean_diff_test((jm["ref"] - jm["logloss"]).to_numpy()) if jm.height else (float("nan"),) * 4
    )
    post = post_cutoff_dll(hl, CUTOFF[HEADLINE_LLM], "llm", "dict")
    rq4c = {
        "pooled_dll_llm_vs_dict": dict(zip(("dll", "lo", "hi", "p"), full, strict=True))
        | {"n": j.height},
        "masked_pooled_dll_vs_dict": dict(zip(("dll", "lo", "hi", "p"), masked, strict=True))
        | {"n": jm.height},
        "post_cutoff": post,
        "cutoff": CUTOFF[HEADLINE_LLM],
        "survives_masked": survives_masked(full[0], full[1], masked[0], masked[1], masked[2]),
        "survives_post_cutoff": survives_post_cutoff(full[0], full[1], full[2], post),
    }
    rq4c["robust"] = rq4c["survives_masked"] and rq4c["survives_post_cutoff"] == "survives"
    write_rows("rq1_rows", rows)
    write_json("rq1", {"verdict": v, "rq4c": rq4c, "perms": PERMS, "rows": rows})
    print(v, rq4c["survives_masked"], rq4c["survives_post_cutoff"])


if __name__ == "__main__":
    main()
