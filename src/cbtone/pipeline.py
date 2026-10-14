"""Scoring pipeline and stage timing (MISSION §0 compute target: per-stage wall time logged).

``score_documents`` runs one scorer over documents and returns one row per document; failures are
recorded in an ``error`` column (never silently defaulted). ``Timer`` appends wall time per stage
to ``results/timing.json``.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from cbtone.schema import Document
from cbtone.scorers.base import DOC_CHAR_CAP, Scorer

TIMING = Path("results/timing.json")

SCORE_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "doc_id": pl.String,
    "bank": pl.String,
    "date": pl.Date,
    "doc_type": pl.String,
    "language": pl.String,
    "scorer_id": pl.String,
    "variant": pl.String,
    "prompt_id": pl.String,
    "model_digest": pl.String,
    "hawkish_p": pl.Float64,
    "dovish_p": pl.Float64,
    "neutral_p": pl.Float64,
    "index": pl.Float64,
    "error": pl.String,
}


def score_documents(
    docs: Iterable[Document],
    scorer: Scorer,
    *,
    variant: str = "",
    cap: int = DOC_CHAR_CAP,
    progress: Callable[[int], None] | None = None,
) -> pl.DataFrame:
    """Score each document's pre-registered policy text; unsupported languages are skipped."""
    rows: list[dict[str, object]] = []
    for i, doc in enumerate(docs):
        if not scorer.supports(doc.language):
            continue
        base = {
            "doc_id": doc.doc_id,
            "bank": doc.bank,
            "date": doc.date,
            "doc_type": doc.doc_type,
            "language": doc.language,
            "scorer_id": scorer.scorer_id,
            "variant": variant,
        }
        try:
            s = scorer.score_document(doc, cap=cap)
            rows.append(
                {
                    **base,
                    "prompt_id": s.prompt_id,
                    "model_digest": s.model_digest,
                    "hawkish_p": s.hawkish_p,
                    "dovish_p": s.dovish_p,
                    "neutral_p": s.neutral_p,
                    "index": s.index,
                    "error": None,
                }
            )
        except Exception as e:  # recorded per document, reported in results
            rows.append({**base, "error": f"{type(e).__name__}: {e}"})
        if progress is not None:
            progress(i + 1)
    return pl.DataFrame(rows, schema=SCORE_SCHEMA)


class Timer:
    """Append ``{stage, seconds, finished_at, meta}`` records to ``results/timing.json``."""

    def __init__(self, path: Path = TIMING) -> None:
        self.path = path

    def _load(self) -> list[dict[str, object]]:
        if self.path.exists():
            data = json.loads(self.path.read_text())
            if isinstance(data, list):
                return data
        return []

    @contextmanager
    def stage(self, name: str, **meta: object) -> Iterator[dict[str, object]]:
        info: dict[str, object] = dict(meta)
        t0 = time.perf_counter()
        try:
            yield info
        finally:
            records = [r for r in self._load() if r.get("stage") != name]
            records.append(
                {
                    "stage": name,
                    "seconds": round(time.perf_counter() - t0, 2),
                    "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "meta": info,
                }
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(records, indent=2, default=str))
