"""Shared loading for experiment scripts. Outputs go to results/ (ids and numbers only)."""

from __future__ import annotations

import json
import math
import os
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from cbtone.corpus import HEADLINE

os.chdir(Path(__file__).resolve().parent.parent)  # all paths below are repo-relative
RESULTS = Path("results")
SCORES = Path(os.environ.get("CBTONE_SCORES", RESULTS / "scores"))
CONFIG = Path("config/paper.yaml")
CUTOFF = {"qwen3:4b": date(2025, 4, 29), "qwen2.5:3b": date(2024, 9, 19)}  # §0.5 release dates
HEADLINE_LLM = "qwen3:4b"

# label -> (scorer_id, variant)
LABELS_ALL: dict[str, tuple[str, str]] = {
    "dict": ("dict-v1", ""),
    "llm": ("llm", ""),
    "llm_masked": ("llm", "masked"),
    "ft": ("ft-xlmr", ""),
    "fomc_roberta": ("fomc-roberta-repl", ""),  # local replication (DECISIONS D21)
}


def config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG.read_text())


def banks() -> list[str]:
    cfg = config()
    out = list(HEADLINE)
    if cfg.get("include_bot"):
        out.append("bot")
    return out


def load_scores(native: bool = False) -> pl.DataFrame:
    """All document score files (primary, or native twins) concatenated."""
    pat = "*-native.parquet" if native else "*.parquet"
    files = [p for p in SCORES.glob(pat) if native or not p.stem.endswith("-native")]
    files = [
        p
        for p in files
        if p.stem.split("-")[0] in {"dict", "llm", "ft", "fomc"} and "quick" not in p.stem
    ]
    frames = [pl.read_parquet(p) for p in sorted(files)]
    return pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame()


def present_labels(
    scores: pl.DataFrame, bank: str, wanted: list[str]
) -> dict[str, tuple[str, str]]:
    """Labels from ``wanted`` that have error-free scores for ``bank``."""
    out = {}
    for label in wanted:
        sid, var = LABELS_ALL[label]
        ok = scores.filter(
            pl.col("bank") == bank,
            pl.col("scorer_id") == sid,
            pl.col("variant") == var,
            pl.col("error").is_null(),
        )
        if ok.height:
            out[label] = (sid, var)
    return out


def _clean(o: Any) -> Any:
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [_clean(v) for v in o]
    if isinstance(o, date):
        return o.isoformat()
    if hasattr(o, "item"):  # numpy scalars
        return _clean(o.item())
    return o


def write_json(name: str, obj: Any) -> Path:
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{name}.json"
    path.write_text(json.dumps(_clean(obj), indent=2, sort_keys=True))
    return path


def write_rows(name: str, rows: list[dict[str, Any]]) -> None:
    if rows:
        pl.DataFrame(_clean(rows), infer_schema_length=None).write_csv(RESULTS / f"{name}.csv")
