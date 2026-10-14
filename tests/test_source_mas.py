"""Offline tests for the MAS adapter. Fixtures are SYNTHETIC (structure only, placeholder text)."""

import os
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

from cbtone.sources.base import PoliteFetcher
from cbtone.sources.mas import MasAdapter, date_from_name, date_from_text

FIX = Path(__file__).parent / "fixtures" / "mas"
BOILERPLATE = ["Share", "Last updated", "Skip to main", "Footer boilerplate", "Script boilerplate"]


def _adapter(tmp_path: Path) -> MasAdapter:
    return MasAdapter(PoliteFetcher(raw_dir=tmp_path, offline=True), manual_dir=tmp_path / "m")


def _load(tmp_path: Path, *names: str) -> list:
    m = tmp_path / "m"
    m.mkdir()
    for n in names:
        shutil.copy(FIX / n, m / n)
    return list(_adapter(tmp_path).load_manual())


def test_date_from_name() -> None:
    assert date_from_name("mps-2023-10-13.html") == date(2023, 10, 13)
    assert date_from_name("mas-monetary-policy-statement-13oct23.html") == date(2023, 10, 13)
    assert date_from_name("monetary-policy-statement-14-oct-10") == date(2010, 10, 14)
    assert date_from_name("monetary-policy-statement-28jan15") == date(2015, 1, 28)
    assert date_from_name("notes.html") is None


def test_date_from_text() -> None:
    assert date_from_text("Monetary Policy Statement, 13 October 2023") == date(2023, 10, 13)
    assert date_from_text("nothing") is None


def test_list_urls_empty(tmp_path: Path) -> None:
    assert list(_adapter(tmp_path).list_urls(2001, 2026)) == []


def test_slug_html(tmp_path: Path) -> None:
    (doc,) = _load(tmp_path, "mas-monetary-policy-statement-13oct23.html")
    assert (doc.bank, doc.doc_type, doc.language) == ("mas", "mps", "en")
    assert doc.date == date(2023, 10, 13)
    assert doc.doc_id == "mas:2023-10-13:mps:en"
    assert doc.url == (
        "https://www.mas.gov.sg/news/monetary-policy-statements/2023/"
        "mas-monetary-policy-statement-13oct23"
    )
    assert doc.title == "Synthetic Monetary Policy Statement"
    assert len(doc.sha256) == 64
    assert doc.fetched_at.tzinfo is UTC
    assert doc.published_at_utc is None


def test_boilerplate_and_sections(tmp_path: Path) -> None:
    (doc,) = _load(tmp_path, "mas-monetary-policy-statement-13oct23.html")
    for b in BOILERPLATE:
        assert b not in doc.text
    assert "Placeholder sentence gamma" in doc.text
    assert len(doc.sections) == 4
    assert doc.sections[0].heading == "Overview"
    assert doc.sections[2].heading == "Policy"
    assert doc.text == "\n\n".join(s.text for s in doc.sections)


def test_date_from_text_and_slug_url(tmp_path: Path) -> None:
    (doc,) = _load(tmp_path, "undated-page.html")
    assert doc.date == date(2022, 4, 14)
    assert doc.url.endswith("/monetary-policy-statements/2022/undated-page")


def test_fetch_year_filter_and_mtime(tmp_path: Path) -> None:
    _load(tmp_path, "mas-monetary-policy-statement-13oct23.html", "undated-page.html")
    p = tmp_path / "m" / "undated-page.html"
    ts = datetime(2026, 5, 1, tzinfo=UTC).timestamp()
    os.utime(p, (ts, ts))
    a = _adapter(tmp_path)
    assert [d.date.year for d in a.fetch(2023, 2023)] == [2023]
    (d22,) = a.fetch(2022, 2022)
    assert d22.fetched_at == datetime(2026, 5, 1, tzinfo=UTC)


def test_missing_dir_and_ignored_files(tmp_path: Path) -> None:
    assert list(_adapter(tmp_path).load_manual()) == []
    (tmp_path / "m").mkdir()
    (tmp_path / "m" / "readme.txt").write_text("x")
    assert list(_adapter(tmp_path).load_manual()) == []
