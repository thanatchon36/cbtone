"""Offline tests for the Bank of England adapter (fixtures are trimmed real pages)."""

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pypdf.errors import DependencyError

from cbtone.schema import Document
from cbtone.sources import boe
from cbtone.sources.base import PoliteFetcher, RawResponse
from cbtone.sources.boe import BASE, SITEMAP_URL, BoEAdapter, release_time

FIX = Path(__file__).parent / "fixtures" / "boe"
BOILERPLATE = ["Share", "Last Update", "Skip to main", "Convert this page to PDF", "Back to top"]
MPC = f"{BASE}/monetary-policy-summary-and-minutes"


def _adapter(tmp_path: Path) -> BoEAdapter:
    return BoEAdapter(PoliteFetcher(raw_dir=tmp_path, offline=True))


def _raw(name: str, url: str | None = None) -> RawResponse:
    ctype = "application/pdf" if name.endswith(".pdf") else "text/html"
    return RawResponse(
        url=url or f"{BASE}/x/{name}",
        content=(FIX / name).read_bytes(),
        content_type=ctype,
        sha256="ab" * 32,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        from_cache=True,
    )


def _parse(tmp_path: Path, name: str, **hints: str) -> list[Document]:
    hints.setdefault("language", "en")
    return _adapter(tmp_path).parse(_raw(name), hints)


def _check(doc: Document, min_words: int, min_sections: int = 3) -> None:
    assert doc.bank == "boe" and doc.language == "en"
    assert len(doc.text.split()) >= min_words
    assert len(doc.sections) >= min_sections
    assert doc.text == "\n\n".join(s.text for s in doc.sections)
    for bad in BOILERPLATE:
        assert bad not in doc.text
    assert doc.sha256 == "ab" * 32 and doc.fetched_at.year == 2026


def hm(dt: datetime | None) -> str:
    assert dt is not None
    return dt.strftime("%H:%M")


# -- HTML parsing ------------------------------------------------------------------------
def test_statement_2013_press_release(tmp_path: Path) -> None:
    (doc,) = _parse(
        tmp_path, "statement_2013_08.html", doc_type="statement", date="2013-08-01",
        published="2013-08-01",
    )  # fmt: skip
    _check(doc, 200)
    assert doc.doc_type == "statement" and doc.date == date(2013, 8, 1)
    assert doc.title.startswith("Bank of England maintains Bank Rate at 0.5%")
    assert hm(doc.published_at_utc) == "11:00"  # 12:00 BST
    assert "voted to maintain the official Bank Rate paid on commercial bank reserves" in doc.text
    assert not any("pdf" in s.text.lower() for s in doc.sections)
    assert "Press release" not in doc.text.splitlines()[-1]


def test_statement_2015_br_separated_paragraphs(tmp_path: Path) -> None:
    (doc,) = _parse(
        tmp_path, "statement_2015_07.html", doc_type="statement", date="2015-07-09",
        published="2015-07-09",
    )  # fmt: skip
    _check(doc, 100, min_sections=4)
    assert "voted to maintain Bank Rate at 0.5%" in doc.text
    assert "published at 9.30 a.m. on Wednesday 22 July" in doc.text  # inside a longer paragraph


@pytest.mark.parametrize(
    ("name", "iso", "decision"),
    [
        ("statement_2000_03.html", "2000-03-09", "repo rate at 6.0%"),
        (
            "statement_2010_03.html",
            "2010-03-04",
            "Bank Rate paid on commercial bank reserves at 0.5%",
        ),
    ],
)
def test_statement_lead_sentence_kept_in_old_press_releases(
    tmp_path: Path, name: str, iso: str, decision: str
) -> None:
    raw = _raw(name, url=f"{BASE}/news/{iso[:4]}/x/mpc-x-{iso[:4]}")
    (doc,) = _adapter(tmp_path).parse(
        raw, {"doc_type": "statement", "date": iso, "published": iso, "language": "en"}
    )
    assert doc.text.startswith("The Bank of England's Monetary Policy Committee today voted")
    assert decision in doc.text and len(doc.text) > 100
    assert "will be published at 9.30" not in doc.text
    assert doc.sections[0].text in doc.text


def test_minutes_stub_html_when_no_pdf(tmp_path: Path) -> None:
    (doc,) = _parse(
        tmp_path, "minutes_stub_1999_04.html", doc_type="minutes", date="1999-04-08",
        published="1999-04-21",
    )  # fmt: skip
    assert doc.doc_type == "minutes" and doc.date == date(1999, 4, 8)
    assert hm(doc.published_at_utc) == "08:30"  # 09:30 BST
    assert "Willem Buiter voted against" in doc.text


def test_combined_2015_summary_only_html(tmp_path: Path) -> None:
    docs = _parse(
        tmp_path, "combined_2015_08.html", doc_type="statement", date="2015-08-06",
        published="2015-08-06",
    )  # fmt: skip
    assert [d.doc_type for d in docs] == ["statement"]
    _check(docs[0], 500)
    assert docs[0].sections[0].heading == "Monetary policy summary"
    assert "Summary and minutes of the meeting" not in docs[0].text
    assert hm(docs[0].published_at_utc) == "11:00"


def test_combined_2019_content_split_over_blocks(tmp_path: Path) -> None:
    (doc,) = _parse(
        tmp_path, "combined_2019_08.html", doc_type="statement", date="2019-08-01",
        published="2019-08-01",
    )  # fmt: skip
    _check(doc, 400)
    assert doc.text.startswith("The Bank of England\u2019s Monetary Policy Committee (MPC) sets")
    assert "Download the Inflation Report" not in doc.text
    assert "Monetary Policy Summary and minutes of the Monetary Policy Committee meeting" not in (
        s.heading for s in doc.sections
    )


def test_combined_2024_splits_statement_and_minutes(tmp_path: Path) -> None:
    docs = _parse(
        tmp_path, "combined_2024_12.html", doc_type="combined", date="2024-12-19",
        published="2024-12-19", meeting="2024-12-18",
    )  # fmt: skip
    by = {d.doc_type: d for d in docs}
    assert set(by) == {"statement", "minutes"}
    st, mi = by["statement"], by["minutes"]
    _check(st, 300)
    _check(mi, 3000, min_sections=40)
    assert st.date == date(2024, 12, 19) and mi.date == date(2024, 12, 18)
    assert hm(st.published_at_utc) == hm(mi.published_at_utc) == "12:00"
    assert "voted by a majority of 6\u20133 to maintain Bank Rate at 4.75%" in st.text
    assert "Before turning to its immediate policy decision" in mi.text
    assert "Before turning to its immediate policy decision" not in st.text
    assert mi.title.startswith("Minutes of the Monetary Policy Committee meeting ending")
    assert "The immediate policy decision" in {s.heading for s in mi.sections}
    assert st.doc_id == "boe:2024-12-19:statement:en"


def test_special_meeting_has_no_release_time(tmp_path: Path) -> None:
    (doc,) = _parse(
        tmp_path, "special_minutes_2020_03.html", doc_type="minutes", date="2020-03-10",
        published="2020-03-13", special="1",
    )  # fmt: skip
    assert doc.date == date(2020, 3, 10) and doc.published_at_utc is None
    assert "Term Funding" in doc.text


def test_placeholder_page_gives_nothing(tmp_path: Path) -> None:
    docs = _parse(
        tmp_path, "placeholder_2026_12.html", doc_type="statement", date="2026-12-17",
        published="2026-12-17",
    )  # fmt: skip
    assert docs == []


def test_missing_published_hint_gives_no_release_time(tmp_path: Path) -> None:
    (doc,) = _parse(
        tmp_path, "statement_2013_08.html", doc_type="statement", date="2013-08-01"
    )  # fmt: skip
    assert doc.published_at_utc is None and doc.date == date(2013, 8, 1)


# -- PDF parsing ---------------------------------------------------------------------------
def test_minutes_pdf_1999(tmp_path: Path) -> None:
    (doc,) = _parse(
        tmp_path, "minutes_1999_04.pdf", doc_type="minutes", date="1999-04-08",
        published="1999-04-21", title="Minutes of the MPC Meeting held on 7 and 8 April 1999",
    )  # fmt: skip
    _check(doc, 800, min_sections=8)
    assert doc.doc_type == "minutes" and doc.date == date(1999, 4, 8)
    assert doc.title.startswith("Minutes of the MPC Meeting held on 7 and 8")
    assert doc.sections[0].text.startswith("The Committee discussed the prospects for the world")
    assert "The world economy" in {s.heading for s in doc.sections}
    assert "Publication date" not in doc.text and "MINUTES OF" not in doc.text


def test_pdf_sections_2015_layout_drops_summary_and_footers() -> None:
    sections = BoEAdapter.pdf_sections((FIX / "combined_2015_08.txt").read_text())
    assert len(sections) >= 5
    assert sections[0].text.startswith("Before turning to its immediate policy decision")
    text = "\n".join(s.text for s in sections)
    assert "Monetary policy summary" not in text
    assert "Bank of England Minutes of the Monetary" not in text
    assert "Financial markets" in {s.heading for s in sections}


def test_pdf_sections_without_title_line_is_empty_or_numbered() -> None:
    assert BoEAdapter.pdf_sections("nothing numbered here\njust text") == []
    got = BoEAdapter.pdf_sections("1 First para.\n2 Second para\ncontinues here.\n")
    assert [s.text for s in got] == ["First para.", "Second para continues here."]


def test_pdf_needing_cryptography_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise DependencyError("cryptography>=3.1 is required for AES algorithm")

    monkeypatch.setattr(boe, "PdfReader", boom)
    with caplog.at_level(logging.WARNING):
        out = _parse(tmp_path, "minutes_1999_04.pdf", doc_type="minutes", date="1999-04-08")
    assert out == [] and "cryptography" in caplog.text


def test_unreadable_pdf_is_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    raw = RawResponse(
        url=f"{BASE}/x.pdf",
        content=b"%PDF-1.4 garbage",
        content_type="application/pdf",
        sha256="ab" * 32,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        from_cache=True,
    )
    with caplog.at_level(logging.WARNING):
        assert _adapter(tmp_path).parse(raw, {"doc_type": "minutes", "date": "1999-04-08"}) == []
    assert "unreadable" in caplog.text


# -- release-time rule ---------------------------------------------------------------------
def test_release_time_rule() -> None:
    assert hm(release_time("statement", date(2013, 8, 1))) == "11:00"  # BST
    assert hm(release_time("statement", date(2024, 12, 19))) == "12:00"  # GMT
    assert hm(release_time("minutes", date(2015, 7, 22))) == "08:30"  # 09:30 BST
    assert hm(release_time("minutes", date(2015, 1, 21))) == "09:30"  # GMT
    assert hm(release_time("minutes", date(2015, 8, 6))) == "11:00"  # combined, 12:00 BST
    assert release_time("minutes", date(2020, 3, 13), special=True) is None


# -- discovery -----------------------------------------------------------------------------
def _seed(f: PoliteFetcher, url: str, fixture: str, ctype: str = "text/html") -> None:
    body, meta = f._paths("boe", url)
    body.parent.mkdir(parents=True, exist_ok=True)
    body.write_bytes((FIX / fixture).read_bytes())
    meta.write_text(
        json.dumps(
            {
                "url": url,
                "content_type": ctype,
                "sha256": "00" * 32,
                "fetched_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            }
        )
    )


PAGES = {
    f"{BASE}/news/2013/august/mpc-august-2013": "statement_2013_08.html",
    f"{BASE}/news/2015/july/mpc-july-2015": "statement_2015_07.html",
    f"{BASE}/minutes/1999/monetary-policy-committee-april-1999": "minutes_stub_1999_04.html",
    f"{BASE}/minutes/2015/monetary-policy-committee-june-2015": "minutes_stub_2015_06.html",
    f"{MPC}/2015/mpc-august-2015": "combined_2015_08.html",
    f"{MPC}/2019/august-2019": "combined_2019_08.html",
    f"{MPC}/2020/13march-2020": "special_minutes_2020_03.html",
    f"{MPC}/2024/december-2024": "combined_2024_12.html",
    f"{MPC}/2026/december-2026": "placeholder_2026_12.html",
}


def _seeded(tmp_path: Path) -> BoEAdapter:
    f = PoliteFetcher(raw_dir=tmp_path, offline=True)
    _seed(f, SITEMAP_URL, "sitemap.xml", "text/xml")
    for url, fx in PAGES.items():
        _seed(f, url, fx)
    return BoEAdapter(f)


def test_parse_sitemap_keeps_only_mpc_pages() -> None:
    got = list(BoEAdapter.parse_sitemap((FIX / "sitemap.xml").read_text()))
    kinds = {k for k, _ in got}
    assert kinds == {"news", "minutes", "combined"}
    urls = {u for _, u in got}
    assert f"{BASE}/minutes/2005/minutes-april-2005" in urls
    assert f"{BASE}/minutes/2001/monetary-policy-committee-18-september-2001" in urls
    assert not any("court" in u or "mpc-dates" in u or u.endswith("/about") for u in urls)
    assert f"{MPC}/monetary-policy-summary-and-minutes" not in urls


def test_list_urls_1999_and_2013(tmp_path: Path) -> None:
    a = _seeded(tmp_path)
    (u99, h99), = a.list_urls(1999, 1999)  # fmt: skip
    assert u99.endswith("minutes-april-1999.pdf") and "1900-2000" in u99
    assert h99["doc_type"] == "minutes" and h99["date"] == "1999-04-08"
    assert h99["published"] == "1999-04-21" and h99["language"] == "en"
    (u13, h13), = a.list_urls(2013, 2013)  # fmt: skip
    assert u13.endswith("/news/2013/august/mpc-august-2013")
    assert h13["doc_type"] == "statement" and h13["date"] == "2013-08-01"


def test_list_urls_2015_mixes_eras_sorted_by_date(tmp_path: Path) -> None:
    got = [(u, h["doc_type"], h["date"]) for u, h in _seeded(tmp_path).list_urls(2015, 2015)]
    assert [(t, d) for _, t, d in got] == [
        ("minutes", "2015-06-03"),
        ("statement", "2015-07-09"),
        ("minutes", "2015-08-05"),
        ("statement", "2015-08-06"),
    ]
    assert got[0][0].endswith("minutes-june-2015.pdf")
    assert got[2][0].endswith("minutes-august-2015.pdf")


def test_list_urls_modern_years(tmp_path: Path) -> None:
    got = {(h["doc_type"], h["date"]): (u, h) for u, h in _seeded(tmp_path).list_urls(2018, 2030)}
    assert set(got) == {
        ("statement", "2019-08-01"),
        ("minutes", "2019-07-31"),  # no meeting date on the page -> day before publication
        ("minutes", "2020-03-10"),
        ("combined", "2024-12-19"),
    }  # the 2026 placeholder page is skipped
    assert got[("minutes", "2019-07-31")][0].endswith("/2019/august-2019.pdf")
    assert got[("minutes", "2020-03-10")][1]["special"] == "1"
    assert got[("combined", "2024-12-19")][1]["meeting"] == "2024-12-18"


def test_fetch_end_to_end_from_cache(tmp_path: Path) -> None:
    docs = list(_seeded(tmp_path).fetch(2024, 2024))
    assert [d.doc_type for d in docs] == ["minutes", "statement"] or [d.doc_type for d in docs] == [
        "statement",
        "minutes",
    ]
    assert {d.url for d in docs} == {f"{MPC}/2024/december-2024"}


@pytest.mark.network
def test_live_smoke(tmp_path: Path) -> None:
    f = PoliteFetcher(raw_dir=tmp_path)
    url = f"{MPC}/2024/december-2024"
    raw = f.get("boe", url)
    docs = BoEAdapter(f).parse(
        raw, {"doc_type": "combined", "date": "2024-12-19", "published": "2024-12-19"}
    )
    assert {d.doc_type for d in docs} == {"statement", "minutes"}
