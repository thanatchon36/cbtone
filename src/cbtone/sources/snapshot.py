"""Versioned corpus snapshot: documents/sentences/manifest parquet + VERSION (MISSION.md §1.1, §3).

Banks whose terms do not allow redistribution get null text columns in the committed
parquet files; a full-text copy of just those rows is written to ``<out_dir>/private/``
(``data/corpus/private/`` by default, git-ignored).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl

from cbtone.schema import Document
from cbtone.text.split import split_paragraphs, split_sentences

_SECTION = pl.Struct({"heading": pl.String, "text": pl.String})
_DT = pl.Datetime("us", "UTC")

_DOC_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "doc_id": pl.String,
    "bank": pl.String,
    "date": pl.Date,
    "published_at_utc": _DT,
    "doc_type": pl.String,
    "language": pl.String,
    "parallel_id": pl.String,
    "title": pl.String,
    "text": pl.String,
    "sections": pl.List(_SECTION),
    "url": pl.String,
    "sha256": pl.String,
    "fetched_at": _DT,
}
_SENT_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "doc_id": pl.String,
    "para_idx": pl.Int32,
    "sent_idx": pl.Int32,
    "text": pl.String,
    "lang": pl.String,
}
_MANIFEST_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "doc_id": pl.String,
    "bank": pl.String,
    "date": pl.Date,
    "doc_type": pl.String,
    "language": pl.String,
    "url": pl.String,
    "sha256": pl.String,
    "fetched_at": _DT,
    "n_chars": pl.Int64,
    "n_sentences": pl.Int64,
    "redistributable": pl.Boolean,
}


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _paragraphs(doc: Document) -> list[str]:
    if doc.sections:
        return [s.text for s in doc.sections if s.text.strip()]
    return split_paragraphs(doc.text)


def build_snapshot(
    documents: Iterable[Document],
    out_dir: Path | str,
    redistributable: Mapping[str, bool] | None = None,
    *,
    default_redistributable: bool = False,
    snapshot_date: date | None = None,
    private_dir: Path | str | None = None,
) -> str:
    """Write the corpus snapshot to ``out_dir`` and return the VERSION string.

    ``redistributable`` maps bank -> bool; banks not listed use
    ``default_redistributable`` (False: fail closed). Rows are sorted by ``doc_id``
    (duplicates raise ``ValueError``) so output is deterministic for a given input.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    priv = Path(private_dir) if private_dir is not None else out / "private"
    flags = redistributable or {}

    docs = sorted(documents, key=lambda d: d.doc_id)
    ids = [d.doc_id for d in docs]
    if len(set(ids)) != len(ids):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"duplicate doc_id(s): {dup}")

    doc_rows: list[dict[str, object]] = []
    sent_rows: list[dict[str, object]] = []
    man_rows: list[dict[str, object]] = []
    for d in docs:
        redis = flags.get(d.bank, default_redistributable)
        n_sent = 0
        for p_idx, para in enumerate(_paragraphs(d)):
            for s_idx, sent in enumerate(split_sentences(para, d.language)):
                sent_rows.append(
                    {
                        "doc_id": d.doc_id,
                        "para_idx": p_idx,
                        "sent_idx": s_idx,
                        "text": sent,
                        "lang": d.language,
                    }
                )
                n_sent += 1
        doc_rows.append(
            {
                "doc_id": d.doc_id,
                "bank": d.bank,
                "date": d.date,
                "published_at_utc": _utc(d.published_at_utc),
                "doc_type": d.doc_type,
                "language": d.language,
                "parallel_id": d.parallel_id,
                "title": d.title,
                "text": d.text,
                "sections": [{"heading": s.heading, "text": s.text} for s in d.sections],
                "url": d.url,
                "sha256": d.sha256,
                "fetched_at": _utc(d.fetched_at),
            }
        )
        man_rows.append(
            {
                "doc_id": d.doc_id,
                "bank": d.bank,
                "date": d.date,
                "doc_type": d.doc_type,
                "language": d.language,
                "url": d.url,
                "sha256": d.sha256,
                "fetched_at": _utc(d.fetched_at),
                "n_chars": len(d.text),
                "n_sentences": n_sent,
                "redistributable": redis,
            }
        )

    documents_df = pl.DataFrame(doc_rows, schema=_DOC_SCHEMA)
    sentences_df = pl.DataFrame(sent_rows, schema=_SENT_SCHEMA)
    manifest_df = pl.DataFrame(man_rows, schema=_MANIFEST_SCHEMA)

    closed = {r["doc_id"] for r in man_rows if not r["redistributable"]}
    if closed:
        priv.mkdir(parents=True, exist_ok=True)
        in_closed = pl.col("doc_id").is_in(sorted(str(c) for c in closed))
        documents_df.filter(in_closed).write_parquet(priv / "documents.parquet")
        sentences_df.filter(in_closed).write_parquet(priv / "sentences.parquet")
        documents_df = documents_df.with_columns(
            pl.when(in_closed).then(None).otherwise(pl.col("text")).alias("text"),
            pl.when(in_closed)
            .then(pl.lit(None, dtype=pl.List(_SECTION)))
            .otherwise(pl.col("sections"))
            .alias("sections"),
        )
        sentences_df = sentences_df.with_columns(
            pl.when(in_closed).then(None).otherwise(pl.col("text")).alias("text")
        )

    documents_df.write_parquet(out / "documents.parquet")
    sentences_df.write_parquet(out / "sentences.parquet")
    manifest_df.write_parquet(out / "manifest.parquet")

    digest = hashlib.sha256()
    for row in manifest_df.sort("doc_id").iter_rows(named=True):
        digest.update(json.dumps(row, sort_keys=True, default=str).encode("utf-8") + b"\n")
    stamp = (snapshot_date or datetime.now(UTC).date()).isoformat()
    version = f"{stamp}+{digest.hexdigest()}"
    (out / "VERSION").write_text(version + "\n", encoding="utf-8")
    return version
