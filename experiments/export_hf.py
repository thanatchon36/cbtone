"""Export the fine-tuned scorer and its training sentences for the Hugging Face Hub.

Writes data/hf/ (git-ignored):
  model/    the ft-xlmr checkpoint used in the paper (copied from data/models/ft-xlmr/) + README.md
  dataset/  public.parquet    sentences from sources whose terms allow redistribution, with text
            ids_only.parquet  the remaining sentences as (doc_id, para_idx, sent_idx, url, sha256,
                              label) without text; `cbtone fetch` + `cbtone snapshot` rebuild it
            README.md

The training frame is rebuilt exactly as experiments/train_ft.py builds it (LLM labels come from the
score cache, so set CBTONE_SCORE_CACHE to the cache used for the run). Upload is a separate, manual
step (`hf upload`); this script never touches the network.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import polars as pl
from _common import RESULTS
from train_ft import MODEL_DIR, training_frame

from cbtone.corpus import load_frame

OUT = Path("data/hf")
CARDS = Path("experiments/hf_cards")
LICENCE = {
    "fed": "Public domain (federalreserve.gov/disclaimer.htm); cite the Board of Governors",
    "rba": "CC BY 4.0 (rba.gov.au/copyright); attribution: Reserve Bank of Australia",
    "ecb": "Reproduction permitted with the source acknowledged (ecb.europa.eu disclaimer)",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def locate(df: pl.DataFrame) -> pl.DataFrame:
    """Attach (doc_id, para_idx, sent_idx, redistributable) to each training sentence by text."""
    pub = pl.read_parquet("data/corpus/sentences.parquet").with_columns(
        redistributable=pl.lit(True)
    )
    priv = pl.read_parquet("data/corpus/private/sentences.parquet").with_columns(
        redistributable=pl.lit(False)
    )
    src = (
        pl.concat([pub, priv])
        # a sentence that also occurs in a redistributable document is attributed to it
        .sort(
            "redistributable",
            "doc_id",
            "para_idx",
            "sent_idx",
            descending=[True, False, False, False],
        )
        .unique("text", keep="first", maintain_order=True)
        .select("text", "doc_id", "para_idx", "sent_idx", "redistributable")
    )
    return df.join(src, on="text", how="left")


def main() -> int:
    report = json.loads((RESULTS / "ft_train_report.json").read_text())
    weights = MODEL_DIR / "model.safetensors"
    digest = sha256(weights)
    if digest != report["model_digest"]:
        sys.exit(f"{weights} sha256 {digest} != paper model_digest {report['model_digest']}")

    df = locate(training_frame())
    meta = load_frame().select("doc_id", "bank", "date", "doc_type", "url", "sha256")
    df = df.join(meta, on="doc_id", how="left").with_columns(
        pl.col("date").cast(pl.Utf8),
        sentence_sha256=pl.col("text").map_elements(
            lambda t: hashlib.sha256(t.encode()).hexdigest(), return_dtype=pl.Utf8
        ),
    )
    located = df.filter(pl.col("doc_id").is_not_null())
    cols = ["bank", "doc_id", "date", "doc_type", "para_idx", "sent_idx", "lang", "label"]
    public = (
        located.filter(pl.col("redistributable"))
        .with_columns(
            source_licence=pl.col("bank").replace_strict(LICENCE, default=None),
        )
        .select(*cols, "text", "url", "sha256", "source_licence")
        .rename({"sha256": "doc_sha256"})
        .sort("bank", "date", "para_idx", "sent_idx")
    )
    ids_only = (
        located.filter(~pl.col("redistributable"))
        .select(*cols, "url", "sha256", "sentence_sha256")
        .rename({"sha256": "doc_sha256"})
        .sort("bank", "date", "para_idx", "sent_idx")
    )
    if public["source_licence"].null_count():
        sys.exit("public rows from a bank without a recorded licence")

    (OUT / "dataset").mkdir(parents=True, exist_ok=True)
    public.write_parquet(OUT / "dataset" / "public.parquet")
    ids_only.write_parquet(OUT / "dataset" / "ids_only.parquet")
    model_out = OUT / "model"
    if model_out.exists():
        shutil.rmtree(model_out)
    shutil.copytree(MODEL_DIR, model_out)
    shutil.copyfile(CARDS / "model.md", model_out / "README.md")
    shutil.copyfile(CARDS / "dataset.md", OUT / "dataset" / "README.md")

    stats = {
        "n_total": df.height,
        "n_located": located.height,
        "n_unlocated": df.height - located.height,
        "n_public": public.height,
        "n_ids_only": ids_only.height,
        "by_bank": {
            f"{b}|{r}": n
            for b, r, n in located.group_by("bank", "redistributable")
            .len()
            .sort("bank")
            .iter_rows()
        },
        "labels": dict(df.group_by("label").len().sort("label").iter_rows()),
        "langs": dict(df.group_by("lang").len().sort("lang").iter_rows()),
        "model_digest": digest,
    }
    (OUT / "stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
