"""Human-labelled FOMC anchor set (Shah, Paturi & Chava 2023; MISSION §1.4).

``gtfintechlab/fomc_communication`` is **CC-BY-NC-4.0**: evaluation only (RQ4b, RQ5),
downloaded at run time into ``data/cache/`` (git-ignored), never redistributed and never
used to train released weights (docs/sources/LICENSES.md). Pinned to a dataset revision so
reruns score the same sentences.
"""

from __future__ import annotations

import io
from pathlib import Path

import polars as pl

from cbtone.sources.base import PoliteFetcher

FOMC_REPO = "gtfintechlab/fomc_communication"
FOMC_REVISION = "6b0283f55f0005a6d38d49f271d795c21fccc1a3"  # 2024-12-16
CACHE_DIR = Path("data/cache")
LABELS = {0: "dovish", 1: "hawkish", 2: "neutral"}  # dataset card: LABEL_0/1/2


def fomc_url(split: str) -> str:
    return f"https://huggingface.co/datasets/{FOMC_REPO}/resolve/{FOMC_REVISION}/{split}.csv"


def parse_fomc_csv(content: bytes, split: str) -> pl.DataFrame:
    """``[sentence_id, sentence, year, label, split]`` with label in dovish/hawkish/neutral."""
    raw = pl.read_csv(io.BytesIO(content.removeprefix(b"\xef\xbb\xbf")))
    bad = set(raw["label"].unique().to_list()) - set(LABELS)
    if bad:
        raise ValueError(f"unexpected label value(s) {sorted(bad)} in {split}.csv")
    # The source ``index`` column is not unique (test.csv: 496 rows, 424 distinct values), so the
    # id is ``split:row:index`` - row position for uniqueness, source index for traceability.
    return raw.with_row_index("_row").select(
        pl.format("{}:{}:{}", pl.lit(split), pl.col("_row"), pl.col("index")).alias("sentence_id"),
        pl.col("sentence").cast(pl.String),
        pl.col("year").cast(pl.Int32),
        pl.col("label").replace_strict(LABELS, return_dtype=pl.String),
        pl.lit(split).alias("split"),
    )


def load_fomc_anchor(
    fetcher: PoliteFetcher | None = None, splits: tuple[str, ...] = ("train", "test")
) -> pl.DataFrame:
    """Download (or read from cache) and concatenate the requested splits."""
    f = fetcher or PoliteFetcher(raw_dir=CACHE_DIR)
    return pl.concat([parse_fomc_csv(f.get("fomc_anchor", fomc_url(s)).content, s) for s in splits])
