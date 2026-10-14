"""Train the FineTunedScorer on LLM silver labels, then score documents, FOMC test and silver set.

Training data (MISSION §3, LICENSES): LLM P1 labels (argmax, T=0) on the RQ4a sentence sample
and on the
sentences of the 120 RQ4a documents, both already scored (cache hits only, no new LLM calls).
The SEA silver sentences (RQ5 evaluation) and all FOMC data (CC-BY-NC) are excluded.
Writes data/models/ft-xlmr/ (git-ignored), results/ft_train_report.json, results/scores/ft*.parquet,
and appends 'ft' rows to results/scores/fomc_test.parquet.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import polars as pl
from _common import RESULTS, SCORES

from cbtone.corpus import HEADLINE, load_frame, select, to_documents
from cbtone.eval.anchors import load_fomc_anchor
from cbtone.pipeline import Timer
from cbtone.scorers.base import ScoreCache
from cbtone.scorers.finetuned import FineTunedScorer, train
from cbtone.scorers.llm import LLMScorer

MODEL_DIR = Path("data/models/ft-xlmr")
SEED = 20261014
CAP = 3000


def training_frame() -> pl.DataFrame:
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
    rq4a = pl.read_parquet(SCORES / "rq4a_sentences.parquet").filter(pl.col("config") == "P1")
    units = rq4a.select("unit", "label", pl.col("language").alias("lang"))
    s = sents.with_columns(unit=pl.format("{}:{}:{}", "doc_id", "para_idx", "sent_idx"))
    part_a = units.join(s.select("unit", "text"), on="unit", how="inner").select(
        "text", "lang", "label"
    )
    # sentences of the 120 RQ4a documents, P1 labels from the cache
    llm = LLMScorer(cache=ScoreCache(), evidence=False)
    doc_ids = pl.read_parquet(SCORES / "rq4a_docs.parquet")["unit"].unique().to_list()
    frame = load_frame()
    docs = to_documents(select(frame, HEADLINE).filter(pl.col("doc_id").is_in(doc_ids)))
    rows = []
    calls_before = llm.calls_made
    for d in docs:
        pairs = llm.document_sentences(d, CAP)
        scores = llm.score_sentences([t for t, _ in pairs], d.language)
        rows += [
            {"text": t, "lang": d.language, "label": sc.label}
            for (t, _), sc in zip(pairs, scores, strict=True)
        ]
    if llm.calls_made != calls_before:
        print(f"warning: {llm.calls_made - calls_before} uncached LLM calls building training data")
    part_b = pl.DataFrame(rows)
    df = pl.concat([part_a, part_b]).unique("text", keep="first")
    silver_ids = pl.read_csv("data/labels/sea_silver_sample.csv", comment_prefix="#")
    silver_text = silver_ids.join(sents, on=["doc_id", "para_idx", "sent_idx"])["text"].to_list()
    df = df.filter(~pl.col("text").is_in(silver_text)).with_columns(
        source=pl.lit("llm_silver_qwen3_P1")
    )
    return df


def main() -> None:
    timer = Timer()
    df = training_frame()
    print(df.group_by("label").len().sort("label"), df.height)
    with timer.stage("ft:train", n=df.height):
        report = train(df, MODEL_DIR, seed=SEED, max_minutes=30)
    (RESULTS / "ft_train_report.json").write_text(report.model_dump_json(indent=2))
    with timer.stage("ft:score"):
        run = [
            "uv",
            "run",
            "--no-sync",
            "cbtone",
            "score",
            "--scorer",
            "ft",
            "--model-dir",
            str(MODEL_DIR),
        ]
        allb = ["fed", "ecb", "boe", "rba", "mas", "bi", "bnm", "bot", "pboc"]
        subprocess.run([*run, *allb, "--out", str(SCORES / "ft.parquet")], check=True)
        subprocess.run(
            [*run, *allb, "--native", "--out", str(SCORES / "ft-native.parquet")], check=True
        )
        ft = FineTunedScorer.load(MODEL_DIR)
        test = load_fomc_anchor(splits=("test",))
        fomc = pl.read_parquet(SCORES / "fomc_test.parquet").filter(pl.col("config") != "ft")
        add = []
        texts = test["sentence"].to_list()
        for (sid, gold), s in zip(
            test.select("sentence_id", "label").iter_rows(),
            ft.score_sentences(texts, "en"),
            strict=True,
        ):
            add.append(
                {
                    "unit": sid,
                    "config": "ft",
                    "hawkish_p": s.hawkish_p,
                    "dovish_p": s.dovish_p,
                    "neutral_p": s.neutral_p,
                    "index": s.index,
                    "label": s.label,
                    "prompt_id": None,
                    "model_digest": s.model_digest,
                    "gold": gold,
                }
            )
        pl.concat([fomc, pl.DataFrame(add)], how="diagonal_relaxed").write_parquet(
            SCORES / "fomc_test.parquet"
        )
        labels = pl.read_parquet(SCORES / "silver_labels.parquet")
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
        sil = labels.join(sents, on=["doc_id", "para_idx", "sent_idx"])
        srows = []
        for r in sil.iter_rows(named=True):
            s = ft.score_text(r["text"], r["lang"])
            srows.append(
                {"unit": r["sample_id"], "config": "ft", "index": s.index, "label": s.label}
            )
        pl.DataFrame(srows).write_parquet(SCORES / "silver_ft.parquet")
    print(json.loads(report.model_dump_json()))


if __name__ == "__main__":
    main()
