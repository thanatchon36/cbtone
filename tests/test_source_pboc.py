"""Offline tests for the pboc adapter (synthetic fixture: pbc.gov.cn blocks crawlers)."""

from datetime import UTC, date, datetime
from pathlib import Path

from cbtone.sources.base import PoliteFetcher, RawResponse
from cbtone.sources.pboc import PbocAdapter

FIX = Path(__file__).parent / "fixtures" / "pboc"


def test_parse_synthetic_zh(tmp_path: Path) -> None:
    a = PbocAdapter(PoliteFetcher(raw_dir=tmp_path, offline=True), manual_dir=tmp_path)
    for enc in ("utf-8", "gb18030"):
        content = (FIX / "synthetic_zh.html").read_text().encode(enc)
        raw = RawResponse("file:///x", content, "text/html", "ab" * 32, datetime.now(UTC), True)
        hints = {
            "doc_type": "communique",
            "date": "2024-03-01",
            "language": "zh",
            "parallel_id": "pboc:2024-03-21:communique",
        }
        (doc,) = a.parse(raw, hints)
        assert doc.date == date(2024, 3, 21) and doc.language == "zh"
        assert len(doc.sections) == 3 and "打印" not in doc.text
        assert "稳健的货币政策" in doc.text


def test_list_manual(tmp_path: Path) -> None:
    (tmp_path / "2024-03-21_zh.html").write_text("x")
    (tmp_path / "junk.txt").write_text("x")
    a = PbocAdapter(PoliteFetcher(raw_dir=tmp_path, offline=True), manual_dir=tmp_path)
    out = list(a.list_urls(2024, 2024))
    assert len(out) == 1 and out[0][1]["parallel_id"] == "pboc:2024-03-21:communique"
    assert list(a.list_urls(2020, 2021)) == []
