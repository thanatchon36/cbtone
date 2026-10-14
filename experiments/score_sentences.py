"""Sentence-level LLM jobs (RESEARCH_QUESTIONS.md RQ4a/RQ4b/RQ5; budget per D18).

1. FOMC test split (496 sentences, CC-BY-NC, evaluation only): LLM P1 and dictionary.
2. SEA silver labels (200 sentences): pass A = P2, pass B = P3 (argmax labels), tie-break = P5
   where A and B disagree (MISSION §1.4). P1 is the scorer's own prompt and is not used for labels.
   P1 scores are also stored (reported for RQ5 but not used for H5, because of circularity).
3. RQ4a sentence sample (250, stratified by bank x language x doc type; excludes silver sentences):
   P1..P5 at T=0, P1 at T=0.7, P1 on the second model tag (qwen2.5:3b).
4. RQ4a document set (120 headline primary documents, stratified by bank): the same 7 configurations
   at document level (P1 T=0 qwen3 is the main run), plus sentence-level aggregation with P1
   (mean, decision_weighted, max_abs).

Outputs (identifiers and scores only; no licensed text) go to results/scores/.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import polars as pl

from cbtone.corpus import HEADLINE, load_frame, select, to_documents
from cbtone.eval.anchors import load_fomc_anchor
from cbtone.pipeline import Timer
from cbtone.scorers.base import ScoreCache, ToneScore
from cbtone.scorers.dictionary import DictionaryScorer
from cbtone.scorers.llm import LLMError, LLMScorer

OUT = Path("results/scores")
SEED = 20261014
CAP = 6000  # D20 (pre-registered default)
N_RQ4A_SENT = 1000  # D20 (pre-registered default)
N_RQ4A_DOCS = 120
CONFIGS: dict[str, dict[str, object]] = {
    "P1": {"prompt": "P1"},
    "P2": {"prompt": "P2"},
    "P3": {"prompt": "P3"},
    "P4": {"prompt": "P4"},
    "P5": {"prompt": "P5"},
    "P1_T0.7": {"prompt": "P1", "temperature": 0.7},
    "P1_qwen2.5": {"prompt": "P1", "model": "qwen2.5:3b"},
}


def _row(unit: str, config: str, s: ToneScore) -> dict[str, object]:
    return {
        "unit": unit,
        "config": config,
        "hawkish_p": s.hawkish_p,
        "dovish_p": s.dovish_p,
        "neutral_p": s.neutral_p,
        "index": s.index,
        "label": s.label,
        "prompt_id": s.prompt_id,
        "model_digest": s.model_digest,
    }


def _scorers(cache: ScoreCache, names: list[str]) -> dict[str, LLMScorer]:
    return {n: LLMScorer(cache=cache, evidence=False, **CONFIGS[n]) for n in names}  # type: ignore[arg-type]


def fomc(cache: ScoreCache) -> None:
    test = load_fomc_anchor(splits=("test",))
    llm = LLMScorer(cache=cache, evidence=False)
    dic = DictionaryScorer()
    rows = []
    for sid, text, gold in test.select("sentence_id", "sentence", "label").iter_rows():
        for name, sc in (("llm", llm), ("dict", dic)):
            r = _row(sid, name, sc.score_text(text, "en"))
            rows.append({**r, "gold": gold})
    pl.DataFrame(rows).write_parquet(OUT / "fomc_test.parquet")


def silver(cache: ScoreCache, sents: pl.DataFrame) -> None:
    ids = pl.read_csv("data/labels/sea_silver_sample.csv", comment_prefix="#")
    df = ids.join(sents, on=["doc_id", "para_idx", "sent_idx"], how="left")
    if df["text"].null_count():
        raise SystemExit("silver sentences missing from the local corpus copy")
    sc = _scorers(cache, ["P1", "P2", "P3", "P5"])
    rows, labels = [], []
    for r in df.iter_rows(named=True):
        lang = r["lang"]
        out = {k: sc[k].score_text(r["text"], lang) for k in ("P1", "P2", "P3")}
        a, b = out["P2"].label, out["P3"].label
        tie = None
        if a != b:
            tie = sc["P5"].score_text(r["text"], lang)
            out["P5"] = tie
        label = a if a == b else tie.label  # type: ignore[union-attr]
        labels.append(
            {
                "sample_id": r["sample_id"],
                "bank": r["bank"],
                "lang": lang,
                "doc_id": r["doc_id"],
                "para_idx": r["para_idx"],
                "sent_idx": r["sent_idx"],
                "label": label,
                "pass_a": a,
                "pass_b": b,
                "tie_break": tie.label if tie else None,
            }
        )
        rows.extend(_row(r["sample_id"], k, s) for k, s in out.items())
    pl.DataFrame(labels).write_parquet(OUT / "silver_labels.parquet")
    pl.DataFrame(rows).write_parquet(OUT / "silver_llm.parquet")
    dic = DictionaryScorer()
    drows = [
        _row(r["sample_id"], "dict", dic.score_text(r["text"], "en"))
        for r in df.filter(pl.col("lang") == "en").iter_rows(named=True)
    ]
    pl.DataFrame(drows).write_parquet(OUT / "silver_dict.parquet")


def rq4a_sentence_sample(frame: pl.DataFrame, sents: pl.DataFrame) -> pl.DataFrame:
    """Stratified (bank x language x doc type) sample of headline sentences, excluding silver."""
    silver_ids = pl.read_csv("data/labels/sea_silver_sample.csv", comment_prefix="#").select(
        "doc_id", "para_idx", "sent_idx"
    )
    meta = frame.filter(pl.col("bank").is_in(list(HEADLINE))).select(
        "doc_id", "bank", "language", "doc_type"
    )
    pool = (
        sents.join(meta, on="doc_id", how="inner")
        .join(silver_ids, on=["doc_id", "para_idx", "sent_idx"], how="anti")
        .filter(pl.col("text").str.count_matches(r"\S+") >= 6)
    )
    strata = (
        pool.group_by("bank", "language", "doc_type").len().sort("bank", "language", "doc_type")
    )
    per = max(1, N_RQ4A_SENT // strata.height)
    parts = []
    for bank, lang, dt, n in strata.iter_rows():
        sub = pool.filter(
            pl.col("bank") == bank, pl.col("language") == lang, pl.col("doc_type") == dt
        )
        parts.append(sub.sort("doc_id", "para_idx", "sent_idx").sample(min(per, n), seed=SEED))
    out = pl.concat(parts)
    if out.height < N_RQ4A_SENT:
        rest = pool.join(
            out.select("doc_id", "para_idx", "sent_idx"),
            on=["doc_id", "para_idx", "sent_idx"],
            how="anti",
        )
        out = pl.concat(
            [
                out,
                rest.sort("doc_id", "para_idx", "sent_idx").sample(
                    N_RQ4A_SENT - out.height, seed=SEED
                ),
            ]
        )
    return out.head(N_RQ4A_SENT).with_columns(
        unit=pl.format("{}:{}:{}", "doc_id", "para_idx", "sent_idx")
    )


def _safe(unit: str, config: str, fn: Callable[[], ToneScore]) -> dict[str, object]:
    """Score, or record the failure (LLMError) with a null index; never a silent default."""
    try:
        return {**_row(unit, config, fn()), "error": None}
    except LLMError as e:
        return {"unit": unit, "config": config, "index": None, "label": None, "error": str(e)[:200]}


def rq4a(cache: ScoreCache, frame: pl.DataFrame, sents: pl.DataFrame) -> None:
    sample = rq4a_sentence_sample(frame, sents)
    sc = _scorers(cache, list(CONFIGS))
    rows = []
    for r in sample.iter_rows(named=True):
        for name, s in sc.items():
            text, lang = r["text"], r["language"]
            row = _safe(r["unit"], name, lambda s=s, t=text, g=lang: s.score_text(t, g))
            rows.append({**row, "bank": r["bank"], "language": lang, "doc_type": r["doc_type"]})
    pl.DataFrame(rows, infer_schema_length=None).write_parquet(OUT / "rq4a_sentences.parquet")
    prim = select(frame, HEADLINE)
    base, extra = divmod(N_RQ4A_DOCS, len(HEADLINE))
    docs_f = pl.concat(
        [
            prim.filter(pl.col("bank") == b).sort("date").sample(base + (i < extra), seed=SEED)
            for i, b in enumerate(HEADLINE)
        ]
    )
    docs = to_documents(docs_f)
    drows, arows = [], []
    for d in docs:
        for name, s in sc.items():
            row = _safe(d.doc_id, name, lambda s=s, d=d: s.score_document(d, cap=CAP))
            drows.append({**row, "bank": d.bank})
        for strategy in ("mean", "decision_weighted", "max_abs"):
            p1 = sc["P1"]
            row = _safe(
                d.doc_id,
                f"agg_{strategy}",
                lambda d=d, st=strategy, p1=p1: p1.score_document_by_sentences(d, st, cap=CAP),
            )
            arows.append({**row, "bank": d.bank})
    pl.DataFrame(drows, infer_schema_length=None).write_parquet(OUT / "rq4a_docs.parquet")
    pl.DataFrame(arows, infer_schema_length=None).write_parquet(OUT / "rq4a_aggregation.parquet")


def main(jobs: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cache = ScoreCache()
    frame = load_frame()
    sents = pl.read_parquet("data/corpus/private/sentences.parquet").filter(
        pl.col("text").is_not_null()
    )
    pub = pl.read_parquet("data/corpus/sentences.parquet").filter(pl.col("text").is_not_null())
    sents = pl.concat([pub, sents]).unique(["doc_id", "para_idx", "sent_idx"], keep="first")
    timer = Timer()
    for job in jobs:
        with timer.stage(f"llm:{job}"):
            if job == "fomc":
                fomc(cache)
            elif job == "silver":
                silver(cache, sents)
            elif job == "rq4a":
                rq4a(cache, frame, sents)
        print(f"done: {job}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["fomc", "silver", "rq4a"])
