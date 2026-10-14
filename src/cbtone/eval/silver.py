"""Sample the 200-sentence SEA silver set (MISSION §1.4).

Only sentence *identifiers* are written (BI, BNM and MAS text is not redistributable, D8);
labels come later from two LLM passes plus a tie-break and are always called *silver*.
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

DEFAULT_QUOTAS: dict[tuple[str, str], int] = {
    ("mas", "en"): 60,
    ("bi", "en"): 35,
    ("bi", "id"): 35,
    ("bnm", "en"): 35,
    ("bnm", "ms"): 35,
}
MIN_WORDS = 6


def sample_silver(
    sentences: pl.DataFrame, quotas: Mapping[tuple[str, str], int], seed: int
) -> pl.DataFrame:
    """Stratified sample by (bank, lang): at most one sentence per document until every
    document in the stratum has contributed one, then a second, and so on.

    ``sentences`` has the snapshot's ``[doc_id, para_idx, sent_idx, text, lang]`` columns;
    sentences under ``MIN_WORDS`` words (headers, datelines) are excluded.
    """
    pool = sentences.with_columns(bank=pl.col("doc_id").str.split(":").list.first()).filter(
        pl.col("text").str.count_matches(r"\S+") >= MIN_WORDS
    )
    parts: list[pl.DataFrame] = []
    for (bank, lang), n in quotas.items():
        stratum = pool.filter(pl.col("bank") == bank, pl.col("lang") == lang)
        if stratum.height < n:
            raise ValueError(f"{bank}/{lang}: {stratum.height} eligible sentences < quota {n}")
        drawn = (
            stratum.sort("doc_id", "para_idx", "sent_idx")
            .sample(fraction=1.0, shuffle=True, seed=seed)
            .with_columns(_turn=pl.int_range(pl.len()).over("doc_id"))
            .with_row_index("_order")
            .sort("_turn", "_order")
            .head(n)
            .with_row_index("_k", offset=1)
        )
        parts.append(
            drawn.select(
                pl.format(
                    "{}-{}-{}",
                    pl.lit(bank),
                    pl.lit(lang),
                    pl.col("_k").cast(pl.String).str.zfill(3),
                ).alias("sample_id"),
                pl.lit(bank).alias("bank"),
                pl.lit(lang).alias("lang"),
                "doc_id",
                "para_idx",
                "sent_idx",
            )
        )
    return pl.concat(parts)
