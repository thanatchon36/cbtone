"""RQ5: transfer of Fed-calibrated scorers to SEA banks (silver set) + "least Fed-like" distances.

Writes results/rq5_rows.csv, results/rq5_distance.csv and results/rq5.json.
"""

from __future__ import annotations

import json

import numpy as np
import polars as pl
from _common import RESULTS, SCORES, write_json, write_rows

from cbtone.analysis.rq345 import rq5_rows
from cbtone.corpus import HEADLINE, load_frame, select
from cbtone.eval import rules

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
N_PER_GROUP = 300
SEED = 20261014


def embedding_distances() -> list[dict[str, object]]:
    """Mean cosine distance of each bank-language's sentences to the Fed centroid (descriptive)."""
    import torch
    from transformers import AutoModel, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(EMBED_MODEL)
    model = AutoModel.from_pretrained(EMBED_MODEL).eval()
    frame = load_frame()
    sents = (
        pl.concat(
            [
                pl.read_parquet("data/corpus/sentences.parquet"),
                pl.read_parquet("data/corpus/private/sentences.parquet"),
            ]
        )
        .filter(pl.col("text").is_not_null())
        .unique(["doc_id", "para_idx", "sent_idx"])
    )
    groups = {}
    for bank in HEADLINE:
        for native in (False, True):
            docs = select(frame, [bank], native=native)
            if docs.height == 0:
                continue
            lang = docs["language"][0]
            s = sents.join(docs.select("doc_id"), on="doc_id").filter(
                pl.col("text").str.count_matches(r"\S+") >= 6
            )
            s = s.sort("doc_id", "para_idx", "sent_idx").sample(
                min(N_PER_GROUP, s.height), seed=SEED
            )
            groups[f"{bank}-{lang}"] = s["text"].to_list()

    def embed(texts: list[str]) -> np.ndarray:
        out = []
        with torch.no_grad():
            for i in range(0, len(texts), 32):
                enc = tok(
                    texts[i : i + 32],
                    padding=True,
                    truncation=True,
                    max_length=128,
                    return_tensors="pt",
                )
                h = model(**enc).last_hidden_state
                m = enc["attention_mask"].unsqueeze(-1)
                v = (h * m).sum(1) / m.sum(1)
                out.append(torch.nn.functional.normalize(v, dim=1).numpy())
        return np.vstack(out)

    emb = {g: embed(t) for g, t in groups.items()}
    fed = emb["fed-en"].mean(axis=0)
    fed /= np.linalg.norm(fed)
    return [
        {"group": g, "n": len(e), "mean_cosine_distance_to_fed": float(np.mean(1 - e @ fed))}
        for g, e in sorted(emb.items())
    ]


def main() -> None:
    labels = pl.read_parquet(SCORES / "silver_labels.parquet")
    rq4 = json.loads((RESULTS / "rq4.json").read_text())
    fomc_f1 = {r["scorer"]: r["macro_f1"] for r in rq4["rq4b"].get("rows", [])}
    preds: dict[str, list[str | None]] = {}
    llm = pl.read_parquet(SCORES / "silver_llm.parquet").filter(pl.col("config") == "P1")
    preds["llm"] = labels.join(
        llm.select(pl.col("unit").alias("sample_id"), "label"),
        on="sample_id",
        how="left",
        suffix="_p",
    )["label_p"].to_list()
    dic = pl.read_parquet(SCORES / "silver_dict.parquet")
    preds["dict"] = labels.join(
        dic.select(pl.col("unit").alias("sample_id"), "label"),
        on="sample_id",
        how="left",
        suffix="_p",
    )["label_p"].to_list()
    for name in ("ft", "fomc_roberta"):  # fomc_roberta: English sentences only (null elsewhere)
        path = SCORES / f"silver_{name}.parquet"
        if path.exists():
            p = pl.read_parquet(path)
            preds[name] = labels.join(
                p.select(pl.col("unit").alias("sample_id"), "label"),
                on="sample_id",
                how="left",
                suffix="_p",
            )["label_p"].to_list()
    rows = rq5_rows(fomc_f1, labels, preds)
    by = {(r["scorer"], r["group"]): r for r in rows}
    mas = by.get(("dict", "mas-en"))
    others = [by.get(("dict", g)) for g in ("bi-en", "bnm-en")]
    if not any(r["scorer"] == "fomc_roberta" for r in rows):
        verdict = "untestable"
        reason = (
            "FOMC-RoBERTa scores missing (run experiments/train_fomc_roberta.py); H5 requires it"
        )
    elif mas is None or not mas["powered"] or any(o is None or not o["powered"] for o in others):
        verdict, reason = (
            "untestable",
            "comparison cells underpowered (< 50 English silver sentences)",
        )
    else:
        verdict, reason = "computed", ""
    dict_note = {
        "mas_dict_drop": mas["drop"] if mas else None,
        "mas_dict_transfers_poorly": bool(mas and mas["drop"] >= rules.RQ5_DROP),
        "bi_en_n": others[0]["n"] if others[0] else 0,
        "bnm_en_n": others[1]["n"] if others[1] else 0,
    }
    ref = {g: by.get(("fomc_roberta", g)) for g in ("mas-en", "bi-en", "bnm-en")}
    ref_note = {f"{g.split('-')[0]}_drop": r["drop"] if r else None for g, r in ref.items()} | {
        "mas_transfers_poorly": bool(ref["mas-en"] and ref["mas-en"]["drop"] >= rules.RQ5_DROP),
        # the comparison H5 would make if BI-en / BNM-en were powered (descriptive here)
        "mas_drop_largest": bool(
            all(ref.values())
            and ref["mas-en"]["drop"] > max(ref["bi-en"]["drop"], ref["bnm-en"]["drop"])
        ),
    }
    try:
        dist = embedding_distances()
    except Exception as e:  # model download or torch missing: descriptive part only
        dist = [{"error": f"{type(e).__name__}: {e}"}]
    write_rows("rq5_rows", rows)
    write_rows("rq5_distance", dist)
    write_json(
        "rq5",
        {
            "verdict": verdict,
            "reason": reason,
            "dict": dict_note,
            "fomc_roberta": ref_note,
            "rows": rows,
            "distance": dist,
            "embedding_model": EMBED_MODEL,
            "label_agreement": {
                "pass_a_eq_b": float((labels["pass_a"] == labels["pass_b"]).mean()),
                "n": labels.height,
                "label_counts": dict(labels.group_by("label").len().iter_rows()),
            },
        },
    )
    print(verdict, reason, dict_note)


if __name__ == "__main__":
    main()
