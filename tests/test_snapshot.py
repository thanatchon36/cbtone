from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from cbtone.schema import Document, Section
from cbtone.sources.snapshot import build_snapshot

FETCHED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _doc(bank: str, day: int, lang: str = "en", sections: bool = False) -> Document:
    return Document.model_validate(
        {
            "bank": bank,
            "date": date(2024, 3, day),
            "doc_type": "statement",
            "language": lang,
            "title": f"{bank} {day}",
            "text": "Rates were held. Inflation eased.\n\nOutlook is balanced.",
            "sections": (
                [
                    Section(heading="Decision", text="Rates were held. Inflation eased."),
                    Section(text="Outlook is balanced."),
                ]
                if sections
                else []
            ),
            "url": f"https://example.org/{bank}/{day}",
            "sha256": "ab" * 32,
            "fetched_at": FETCHED,
        }
    )


def test_build_snapshot_files_and_content(tmp_path: Path):
    docs = [_doc("fed", 20), _doc("ecb", 7, sections=True)]
    version = build_snapshot(
        docs, tmp_path, {"fed": True, "ecb": True}, snapshot_date=date(2026, 5, 1)
    )
    assert (tmp_path / "VERSION").read_text().strip() == version
    assert version.startswith("2026-05-01+")
    d = pl.read_parquet(tmp_path / "documents.parquet")
    assert d["doc_id"].to_list() == ["ecb:2024-03-07:statement:en", "fed:2024-03-20:statement:en"]
    assert d["sections"].to_list()[0][0]["heading"] == "Decision"
    s = pl.read_parquet(tmp_path / "sentences.parquet")
    ecb = s.filter(pl.col("doc_id").str.starts_with("ecb"))
    assert ecb.select("para_idx", "sent_idx", "text").rows() == [
        (0, 0, "Rates were held."),
        (0, 1, "Inflation eased."),
        (1, 0, "Outlook is balanced."),
    ]
    assert set(s["lang"]) == {"en"}
    m = pl.read_parquet(tmp_path / "manifest.parquet")
    assert m["n_sentences"].to_list() == [3, 3]
    assert m["redistributable"].to_list() == [True, True]
    assert not (tmp_path / "private").exists()


def test_deterministic_and_order_independent(tmp_path: Path):
    docs = [_doc("fed", 20), _doc("ecb", 7), _doc("boe", 21)]
    kw = {"snapshot_date": date(2026, 5, 1), "default_redistributable": True}
    v1 = build_snapshot(docs, tmp_path / "a", **kw)  # type: ignore[arg-type]
    v2 = build_snapshot(list(reversed(docs)), tmp_path / "b", **kw)  # type: ignore[arg-type]
    assert v1 == v2
    for name in ("documents", "sentences", "manifest"):
        assert (tmp_path / "a" / f"{name}.parquet").read_bytes() == (
            tmp_path / "b" / f"{name}.parquet"
        ).read_bytes()
    docs2 = [*docs[:2], _doc("boe", 22)]
    assert build_snapshot(docs2, tmp_path / "c", **kw) != v1  # type: ignore[arg-type]


def test_non_redistributable_text_nulled_and_private_copy(tmp_path: Path):
    out = tmp_path / "corpus"
    build_snapshot(
        [_doc("fed", 20), _doc("bot", 5, lang="th", sections=True)],
        out,
        {"fed": True, "bot": False},
        snapshot_date=date(2026, 5, 1),
    )
    d = pl.read_parquet(out / "documents.parquet").sort("bank")
    bot = d.filter(pl.col("bank") == "bot").row(0, named=True)
    assert bot["text"] is None and bot["sections"] is None
    assert bot["title"] == "bot 5"
    assert d.filter(pl.col("bank") == "fed")["text"][0] is not None
    s = pl.read_parquet(out / "sentences.parquet")
    assert s.filter(pl.col("doc_id").str.starts_with("bot"))["text"].null_count() > 0
    assert s.filter(pl.col("doc_id").str.starts_with("fed"))["text"].null_count() == 0
    pd = pl.read_parquet(out / "private" / "documents.parquet")
    assert pd["bank"].to_list() == ["bot"] and pd["text"][0].startswith("Rates")
    ps = pl.read_parquet(out / "private" / "sentences.parquet")
    assert ps["text"].null_count() == 0 and ps.height > 0
    m = pl.read_parquet(out / "manifest.parquet").sort("bank")
    assert m["redistributable"].to_list() == [False, True]
    assert m["n_chars"].to_list()[0] > 0  # manifest keeps counts


def test_default_is_fail_closed(tmp_path: Path):
    build_snapshot([_doc("fed", 20)], tmp_path, snapshot_date=date(2026, 5, 1))
    assert pl.read_parquet(tmp_path / "documents.parquet")["text"][0] is None
    assert (tmp_path / "private" / "documents.parquet").exists()


def test_duplicate_doc_id_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="duplicate"):
        build_snapshot([_doc("fed", 20), _doc("fed", 20)], tmp_path)
