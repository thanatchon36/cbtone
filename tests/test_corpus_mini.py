"""The committed tiny fixture corpus loads and the dictionary scorer runs on it (no network)."""

from pathlib import Path

import polars as pl
from typer.testing import CliRunner

from cbtone import corpus as corp
from cbtone.cli import app

MINI = Path(__file__).parent / "fixtures" / "corpus_mini"


def test_corpus_mini_loads() -> None:
    assert (MINI / "VERSION").read_text().strip().startswith("2026-10-14+")
    manifest = pl.read_parquet(MINI / "manifest.parquet")
    assert set(manifest["bank"]) == {"fed", "rba"}
    assert manifest["redistributable"].all()
    assert manifest["n_sentences"].min() > 0
    docs = corp.primary(["fed", "rba"], MINI)
    assert len(docs) == manifest.height == 5
    assert all(d.text for d in docs)
    assert pl.read_parquet(MINI / "sentences.parquet").height == manifest["n_sentences"].sum()


def test_dict_score_runs_on_corpus_mini(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)  # the score cache is created relative to the working directory
    out = tmp_path / "quick.parquet"
    res = CliRunner().invoke(
        app, ["score", "--scorer", "dict", "fed", "rba", "--corpus", str(MINI), "--out", str(out)]
    )
    assert res.exit_code == 0, res.output
    assert "scored 5 of 5 documents, 0 errors" in res.output
    df = pl.read_parquet(out)
    assert df.height == 5
    assert df["index"].is_between(-1, 1).all()
