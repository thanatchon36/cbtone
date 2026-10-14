"""Offline tests for the Bank Indonesia adapter (fixtures are trimmed real pages)."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from cbtone.schema import Document
from cbtone.sources.base import PoliteFetcher, RawResponse
from cbtone.sources.bi import BASE, INDEX_URL, BIAdapter, parse_date

FIX = Path(__file__).parent / "fixtures" / "bi"
BOILERPLATE = [
    "Share",
    "Last Update",
    "Skip to main",
    "Hits:",
    "Sumber Data",
    "Was this page useful",
]


def _adapter(tmp_path: Path) -> BIAdapter:
    return BIAdapter(PoliteFetcher(raw_dir=tmp_path, offline=True))


def _raw(name: str, url: str) -> RawResponse:
    return RawResponse(
        url=url,
        content=(FIX / f"{name}.html").read_bytes(),
        content_type="text/html",
        sha256="ab" * 32,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        from_cache=True,
    )


def _parse(tmp_path: Path, name: str, lang: str, iso: str, **extra: str) -> Document:
    hints = {"doc_type": "statement", "date": iso, "language": lang, **extra}
    docs = _adapter(tmp_path).parse(_raw(name, f"{BASE}/{lang}/x/{name}.aspx"), hints)
    assert len(docs) == 1
    return docs[0]


@pytest.mark.parametrize(
    ("name", "lang", "iso", "sentence", "title_start", "min_words"),
    [
        (
            "stmt_2025_en",
            "en",
            "2025-09-17",
            "to lower the BI-Rate by 25 bps to 4.75%",
            "BI-Rate lowered",
            600,
        ),
        (
            "stmt_2025_id",
            "id",
            "2025-09-17",
            "menurunkan BI-Rate sebesar 25 bps",
            "BI-Rate Turun",
            600,
        ),
        ("stmt_2018_en", "en", "2018-08-15", "5.50%", "BI 7-day Reverse Repo", 300),
        ("stmt_2018_id", "id", "2018-08-15", "5,50%", "BI 7-Day Reverse Repo", 300),
    ],
)
def test_statement(
    tmp_path: Path, name: str, lang: str, iso: str, sentence: str, title_start: str, min_words: int
) -> None:
    doc = _parse(tmp_path, name, lang, iso)
    assert doc.bank == "bi" and doc.doc_type == "statement" and doc.language == lang
    assert doc.date == date.fromisoformat(iso)
    assert doc.published_at_utc is None
    assert doc.parallel_id == f"bi:{iso}:statement"
    assert doc.title.startswith(title_start)
    assert sentence in doc.text
    assert len(doc.text.split()) >= min_words
    assert len(doc.sections) >= 5
    assert doc.text == "\n\n".join(s.text for s in doc.sections)
    for bad in BOILERPLATE:
        assert bad not in doc.text
    assert not any(s.text.startswith("No") and "DKom" in s.text for s in doc.sections)
    assert "​" not in doc.text
    assert doc.sha256 == "ab" * 32 and doc.fetched_at.year == 2026


def test_signatories_dropped_footnote_kept(tmp_path: Path) -> None:
    en = _parse(tmp_path, "stmt_2025_en", "en", "2025-09-17")
    texts = [s.text for s in en.sections]
    assert any(t.startswith("Jakarta,") for t in texts)
    assert "Executive Director" not in en.text
    assert texts[-1].startswith("[1]")
    idn = _parse(tmp_path, "stmt_2018_id", "id", "2018-08-15")
    assert idn.sections[-1].text.startswith("Jakarta, 15 Agustus 2018")
    assert not idn.sections[-1].text.lower().endswith("komunikasi")
    assert "Direktur Eksekutif" not in idn.text


def test_nested_list_items_not_duplicated(tmp_path: Path) -> None:
    doc = _parse(tmp_path, "stmt_2025_en", "en", "2025-09-17")
    items = [s.text for s in doc.sections if s.text.startswith("Strengthening the pro-market")]
    assert len(items) == 1
    assert "managing the interest rate structure" not in items[0]


def test_date_and_language_from_page_when_no_hints(tmp_path: Path) -> None:
    raw = _raw("stmt_2018_id", f"{BASE}/id/publikasi/ruang-media/news-release/Pages/sp_206618.aspx")
    docs = _adapter(tmp_path).parse(raw, {})
    assert docs[0].date == date(2018, 8, 15) and docs[0].language == "id"
    assert docs[0].parallel_id == "bi:2018-08-15:statement"
    raw_en = _raw("stmt_2018_en", f"{BASE}/en/x.aspx")
    assert _adapter(tmp_path).parse(raw_en, {})[0].language == "en"


def test_old_iru_single_paragraph_page(tmp_path: Path) -> None:
    doc = _parse(tmp_path, "iru_2006_en", "en", "2006-09-05")
    assert "50 bps reduction in the BI Rate from 11.75% to 11.25%" in doc.text
    assert doc.title.startswith("PRESS RELEASE")


def test_page_without_release_body_returns_nothing(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    html = b"<html><head><title>404</title></head><body><p>Not found</p></body></html>"
    raw = RawResponse(f"{BASE}/id/x.aspx", html, "text/html", "00" * 32, datetime.now(UTC), False)
    assert a.parse(raw, {"date": "2020-01-01"}) == []
    no_date = _raw("stmt_2018_en", f"{BASE}/en/x.aspx")
    stripped = RawResponse(
        no_date.url,
        no_date.content.replace(b"thumb-detail__desc-title", b"zzz"),
        "text/html",
        "00" * 32,
        datetime.now(UTC),
        False,
    )
    assert a.parse(stripped, {}) == []
    empty = RawResponse(
        no_date.url,
        b'<div class="page-description"><div class="ms-rtestate-field">'
        b"<p>No: 1/2/DKom</p></div></div>",
        "text/html",
        "00" * 32,
        datetime.now(UTC),
        False,
    )
    assert a.parse(empty, {"date": "2020-01-01"}) == []


def test_parse_date_languages() -> None:
    assert parse_date("23 September 2026") == date(2026, 9, 23)
    assert parse_date("17 Agustus 2018") == date(2018, 8, 17)
    assert parse_date("5 Mei 2010") == date(2010, 5, 5)
    assert parse_date("5 Foo 2010") is None
    assert parse_date("no date") is None


def _seed(f: PoliteFetcher, url: str, content: bytes) -> None:
    body, meta = f._paths("bi", url)
    body.parent.mkdir(parents=True, exist_ok=True)
    body.write_bytes(content)
    meta.write_text(
        json.dumps(
            {
                "url": url,
                "content_type": "text/html",
                "sha256": "00" * 32,
                "fetched_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            }
        )
    )


def test_parse_index_rows() -> None:
    rows = list(BIAdapter.parse_index((FIX / "index_birate.html").read_bytes()))
    assert len(rows) == 10
    d, rate, href = rows[0]
    assert d == date(2026, 9, 23) and rate == "5.75 %"
    assert href.startswith("/en/publikasi/ruang-media/news-release/Pages/sp_")
    assert rows[-1][0] == date(2026, 1, 21)


def test_list_urls_offline_with_manual_pages(tmp_path: Path) -> None:
    f = PoliteFetcher(raw_dir=tmp_path, offline=True)
    _seed(f, INDEX_URL, (FIX / "index_birate.html").read_bytes())
    manual = tmp_path / "bi" / "manual"
    manual.mkdir(parents=True)
    (manual / "page2.html").write_text(
        "<table><tr><td>17 September 2025</td><td>4.75 %</td>"
        '<td><a href="/id/publikasi/ruang-media/news-release/Pages/sp_2721925.aspx?utm=x">'
        "View</a></td></tr>"
        "<tr><td>3 Februari 2010</td><td>6.50 %</td>"
        '<td><a href="/id/iru/email-archive/Pages/old.aspx">View</a></td></tr>'
        "<tr><td>4 Maret 2010</td><td>6.50 %</td><td>-</td></tr></table>"
    )
    (manual / "dup.htm").write_text((manual / "page2.html").read_text())
    items = list(BIAdapter(f).list_urls(2010, 2026))
    assert len({u for u, _ in items}) == len(items)
    by_date = {}
    for url, h in items:
        by_date.setdefault(h["date"], []).append((url, h))
        assert h["doc_type"] == "statement" and h["parallel_id"] == f"bi:{h['date']}:statement"
    assert len(by_date["2026-09-23"]) == 2
    en, idn = by_date["2026-09-23"]
    assert en[1]["language"] == "en" and idn[1]["language"] == "id"
    assert en[0].replace("/en/", "/id/") == idn[0]
    assert [h["language"] for _, h in by_date["2025-09-17"]] == ["en", "id"]
    assert all("?" not in u for u, _ in items)
    # non-release link: kept as is, single language taken from the path
    assert [(u, h["language"]) for u, h in by_date["2010-02-03"]] == [
        (f"{BASE}/id/iru/email-archive/Pages/old.aspx", "id")
    ]
    assert "2010-03-04" not in by_date
    assert {h["date"][:4] for _, h in items} == {"2010", "2025", "2026"}
    only_2025 = list(BIAdapter(f).list_urls(2025, 2025))
    assert {h["date"] for _, h in only_2025} == {"2025-09-17"}


def test_list_urls_without_manual_dir(tmp_path: Path) -> None:
    f = PoliteFetcher(raw_dir=tmp_path, offline=True)
    _seed(f, INDEX_URL, (FIX / "index_birate.html").read_bytes())
    assert len(list(BIAdapter(f).list_urls(2026, 2026))) == 20


@pytest.mark.network
def test_live_smoke(tmp_path: Path) -> None:
    f = PoliteFetcher(raw_dir=tmp_path)
    a = BIAdapter(f)
    docs = []
    for url, hints in a.list_urls(2026, 2026):
        docs.extend(a.parse(f.get("bi", url), hints))
        if len(docs) >= 2:
            break
    assert docs and docs[0].text
