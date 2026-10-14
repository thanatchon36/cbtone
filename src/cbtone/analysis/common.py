"""Shared helpers: decision frames and wide tone tables keyed by (bank, date)."""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from cbtone.corpus import NATIVE, PRIMARY, RBA_PRIMARY_FROM

# label -> (scorer_id, variant) for the score parquet files
Labels = Mapping[str, tuple[str, str]]


def decision_frame(decisions: pl.DataFrame, bank: str) -> pl.DataFrame:
    """Decisions of ``bank`` for RQ1: has a next decision; not from the MAS extractor (§0.3)."""
    d = decisions.filter(
        pl.col("bank") == bank,
        pl.col("source") != "mas_text",
        pl.col("next_direction").is_not_null(),
    )
    if bank == "rba":
        d = d.filter(pl.col("date") >= RBA_PRIMARY_FROM)
    return (
        d.select("date", pl.col("direction").alias("last_direction"), "next_direction")
        .unique("date", keep="first")
        .sort("date")
    )


def tone_wide(
    scores: pl.DataFrame, bank: str, labels: Labels, *, native: bool = False
) -> pl.DataFrame:
    """``date`` + one ``tone_<label>`` column per label, primary series only (no nulls kept)."""
    doc_type, lang = PRIMARY[bank]
    if native:
        if bank not in NATIVE:
            return pl.DataFrame(schema={"date": pl.Date})
        lang = NATIVE[bank]
    base = scores.filter(
        pl.col("bank") == bank,
        pl.col("doc_type") == doc_type,
        pl.col("language") == lang,
        pl.col("error").is_null(),
    )
    out: pl.DataFrame | None = None
    for label, (scorer_id, variant) in labels.items():
        part = (
            base.filter(pl.col("scorer_id") == scorer_id, pl.col("variant") == variant)
            .select("date", pl.col("index").alias(f"tone_{label}"))
            .unique("date", keep="first")
        )
        out = part if out is None else out.join(part, on="date", how="inner")
    if out is None:
        return pl.DataFrame(schema={"date": pl.Date})
    return out.sort("date")
