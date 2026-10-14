"""Load the corpus snapshot (with locally held full text) and select analysis series.

``load_documents`` returns ``Document`` objects from ``data/corpus``. Withheld text (non-
redistributable banks, D8) is filled from ``private/`` when present. ``primary`` applies the
pre-registered primary-series table (RESEARCH_QUESTIONS.md §0.2).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from pathlib import Path

import polars as pl

from cbtone.schema import Document, Section

CORPUS = Path("data/corpus")
HEADLINE = ("fed", "ecb", "boe", "rba", "mas", "bi", "bnm")
OPT_IN = ("bot",)
EXPLORATORY = ("pboc",)
RBA_PRIMARY_FROM = date(2007, 12, 1)  # A1: earlier releases exist only for rate changes

# bank -> (doc_type, primary language); RESEARCH_QUESTIONS.md §0.2
PRIMARY: dict[str, tuple[str, str]] = {
    "fed": ("statement", "en"),
    "ecb": ("statement", "en"),
    "boe": ("minutes", "en"),
    "rba": ("statement", "en"),
    "mas": ("mps", "en"),
    "bi": ("statement", "en"),
    "bnm": ("statement", "en"),
    "bot": ("statement", "en"),
    "pboc": ("communique", "zh"),
}
NATIVE: dict[str, str] = {"bi": "id", "bnm": "ms", "bot": "th", "pboc": "en"}


def load_frame(corpus: Path = CORPUS) -> pl.DataFrame:
    """documents.parquet with withheld text, sections and title filled from ``private/``."""
    docs = pl.read_parquet(corpus / "documents.parquet")
    private = corpus / "private" / "documents.parquet"
    if not private.exists():
        return docs
    full = pl.read_parquet(private).select(
        "doc_id",
        pl.col("text").alias("_t"),
        pl.col("sections").alias("_s"),
    )
    return (
        docs.join(full, on="doc_id", how="left")
        .with_columns(
            text=pl.coalesce("text", "_t"),
            sections=pl.when(pl.col("text").is_null()).then("_s").otherwise("sections"),
        )
        .with_columns(sections=pl.coalesce("sections", "_s"))
        .drop("_t", "_s")
    )


def to_documents(frame: pl.DataFrame) -> list[Document]:
    out = []
    for r in frame.iter_rows(named=True):
        if r["text"] is None:
            continue
        out.append(
            Document(
                bank=r["bank"],
                date=r["date"],
                published_at_utc=r["published_at_utc"],
                doc_type=r["doc_type"],
                language=r["language"],
                parallel_id=r["parallel_id"],
                title=r["title"] or "",
                text=r["text"],
                sections=[Section(**s) for s in (r["sections"] or [])],
                url=r["url"],
                sha256=r["sha256"],
                fetched_at=r["fetched_at"],
            )
        )
    return out


def select(frame: pl.DataFrame, banks: Iterable[str], *, native: bool = False) -> pl.DataFrame:
    """Primary-series rows for ``banks`` (or the native-language twin when ``native``)."""
    parts = []
    for bank in banks:
        doc_type, lang = PRIMARY[bank]
        if native:
            if bank not in NATIVE:
                continue
            lang = NATIVE[bank]
        sub = frame.filter(
            pl.col("bank") == bank, pl.col("doc_type") == doc_type, pl.col("language") == lang
        )
        if bank == "rba":
            sub = sub.filter(pl.col("date") >= RBA_PRIMARY_FROM)
        parts.append(sub)
    return pl.concat(parts) if parts else frame.head(0)


def primary(
    banks: Iterable[str] = HEADLINE, corpus: Path = CORPUS, *, native: bool = False
) -> list[Document]:
    return to_documents(select(load_frame(corpus), banks, native=native))


def quick_sample(frame: pl.DataFrame, n: int = 60, seed: int = 20261014) -> pl.DataFrame:
    """Deterministic ``make quick`` sample: primary headline documents, spread evenly over banks."""
    prim = select(frame, HEADLINE)
    per = max(1, n // len(HEADLINE))
    parts = [
        prim.filter(pl.col("bank") == b).sample(
            min(per, prim.filter(pl.col("bank") == b).height), seed=seed
        )
        for b in HEADLINE
    ]
    out = pl.concat(parts)
    if out.height < n:
        rest = prim.join(out.select("doc_id"), on="doc_id", how="anti")
        out = pl.concat([out, rest.sample(min(n - out.height, rest.height), seed=seed)])
    return out.sort("bank", "date")
