"""RQ4a (stability) and RQ4b (FOMC agreement) tables. RQ4c lives in rq1/rq2 outputs.

Writes results/rq4.json and results/rq4b_rows.csv.
"""

from __future__ import annotations

import json

import numpy as np
import polars as pl
from _common import RESULTS, SCORES, write_json, write_rows

from cbtone.analysis.rq345 import classification_rows, stability
from cbtone.eval import rules


def _matrix(df: pl.DataFrame, configs: list[str]) -> np.ndarray:
    wide = df.filter(pl.col("config").is_in(configs)).pivot(
        on="config", index="unit", values="index"
    )
    return wide.select([c for c in configs if c in wide.columns]).to_numpy().astype(float)


def rq4a() -> dict[str, object]:
    out: dict[str, object] = {}
    prompts = ["P1", "P2", "P3", "P4", "P5"]
    for name in ("sentences", "docs"):
        path = SCORES / f"rq4a_{name}.parquet"
        if not path.exists():
            out[name] = {"status": "missing"}
            continue
        df = pl.read_parquet(path)
        res = {
            "prompts": stability(_matrix(df, prompts)),
            "temperature": stability(_matrix(df, ["P1", "P1_T0.7"])),
            "model_tag": stability(_matrix(df, ["P1", "P1_qwen2.5"])),
        }
        p = res["prompts"]
        res["h4a_prompts_pass"] = bool(
            p["alpha"] >= rules.RQ4A_ALPHA and p["icc_2_1"] >= rules.RQ4A_ICC
        )
        out[name] = res
    agg_path = SCORES / "rq4a_aggregation.parquet"
    if agg_path.exists() and (SCORES / "rq4a_docs.parquet").exists():
        from scipy.stats import spearmanr

        agg = pl.read_parquet(agg_path).pivot(on="config", index="unit", values="index")
        doc = pl.read_parquet(SCORES / "rq4a_docs.parquet").filter(pl.col("config") == "P1")
        agg = agg.join(doc.select("unit", pl.col("index").alias("document")), on="unit")
        cols = ["agg_mean", "agg_decision_weighted", "agg_max_abs", "document"]
        rho = {
            f"{a}~{b}": float(spearmanr(agg[a], agg[b]).statistic)
            for i, a in enumerate(cols)
            for b in cols[i + 1 :]
        }
        out["aggregation"] = {
            "n": agg.height,
            "spearman": rho,
            "all_pass": all(v >= rules.RQ4A_RHO for v in rho.values()),
        }
    return out


def rq4b() -> tuple[dict[str, object], list[dict[str, object]]]:
    path = SCORES / "fomc_test.parquet"
    if not path.exists():
        return {"status": "missing"}, []
    df = pl.read_parquet(path)
    wide = df.pivot(on="config", index=["unit", "gold"], values="label")
    preds = {c: wide[c].to_list() for c in wide.columns if c not in ("unit", "gold")}
    rows = classification_rows(wide["gold"].to_list(), preds, reference="dict")
    llm = next((r for r in rows if r["scorer"] == "llm"), None)
    verdict = "untestable"
    if llm is not None:
        ok = llm["macro_f1"] >= rules.RQ4B_MIN_F1 and llm.get("df1_lo", -1) > 0
        verdict = "supported" if ok else "refuted"
    out = {"verdict": verdict, "n": wide.height, "dedup": dedup_f1(wide, preds)}
    report = RESULTS / "fomc_roberta_train_report.json"
    if report.exists():  # D21: local replication of FOMC-RoBERTa
        r = json.loads(report.read_text())
        out["fomc_roberta_train"] = {
            k: r[k]
            for k in (
                "base_model",
                "selected_seed",
                "test_macro_f1_seed_mean",
                "test_macro_f1_seed_sd",
                "lr",
                "batch_size",
            )
        } | {
            "n_seeds": len(r["runs"]),
            "best_epoch": next(
                x["best_epoch"] for x in r["runs"] if x["seed"] == r["selected_seed"]
            ),
            "val_macro_f1": max(x["val_macro_f1"] for x in r["runs"]),
            "skipped_steps": sum(x.get("skipped_steps", 0) for x in r["runs"]),
        }
    return out, rows


def dedup_f1(wide: pl.DataFrame, preds: dict[str, list[str]]) -> dict[str, object]:
    """Macro-F1 on test sentences that do not also occur verbatim in train (D21 sensitivity)."""
    from cbtone.eval.anchors import load_fomc_anchor
    from cbtone.eval.stats import macro_f1

    fomc = load_fomc_anchor(splits=("train", "test"))
    train = set(fomc.filter(pl.col("split") == "train")["sentence"].to_list())
    text = dict(
        fomc.filter(pl.col("split") == "test").select("sentence_id", "sentence").iter_rows()
    )
    keep = [text[u] not in train for u in wide["unit"].to_list()]
    gold = [g for g, k in zip(wide["gold"].to_list(), keep, strict=True) if k]
    out: dict[str, object] = {"n": len(gold), "n_in_train": len(keep) - len(gold)}
    for name, p in preds.items():
        out[name] = macro_f1(gold, [x for x, k in zip(p, keep, strict=True) if k])
    return out


def main() -> None:
    a = rq4a()
    b, rows = rq4b()
    write_rows("rq4b_rows", rows)
    write_json("rq4", {"rq4a": a, "rq4b": b | {"rows": rows}})
    print(a)
    print(b)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
