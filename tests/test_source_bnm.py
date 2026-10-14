"""Offline tests for the BNM adapter (fixtures are trimmed real pages)."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from cbtone.schema import Document
from cbtone.sources.base import PoliteFetcher, RawResponse
from cbtone.sources.bnm import (
    INDEX_PAGE_ID,
    INDEX_PATH,
    BNMAdapter,
    parallel_id,
    release_time,
    update_language_url,
)

FIX = Path(__file__).parent / "fixtures" / "bnm"
BOILERPLATE = [
    "Embargo",
    "Print",
    "All rights reserved",
    "See also",
    "Lihat Juga",
    "Social Media",
    "Schedule of Monetary Policy Committee",
    "Jadual Mesyuarat",
    "Skip to Content",
]


def _adapter(tmp_path: Path) -> BNMAdapter:
    return BNMAdapter(PoliteFetcher(raw_dir=tmp_path, offline=True))


def _raw(content: bytes, url: str = "https://www.bnm.gov.my/x") -> RawResponse:
    return RawResponse(
        url=url,
        content=content,
        content_type="text/html",
        sha256="ab" * 32,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        from_cache=True,
    )


def _parse(tmp_path: Path, name: str, hints: dict[str, str]) -> Document:
    docs = _adapter(tmp_path).parse(_raw((FIX / name).read_bytes()), hints)
    assert len(docs) == 1
    return docs[0]


def _cache(fetcher: PoliteFetcher, url: str, content: bytes) -> None:
    body, meta = fetcher._paths("bnm", url)
    body.parent.mkdir(parents=True, exist_ok=True)
    body.write_bytes(content)
    meta.write_text(
        json.dumps(
            {
                "url": url,
                "content_type": "text/html",
                "sha256": "cd" * 32,
                "fetched_at": "2026-01-01T00:00:00+00:00",
            }
        )
    )


@pytest.mark.parametrize(
    ("name", "iso", "lang", "sentence", "utc_hhmm", "min_words"),
    [
        (
            "mps_2004_en.html",
            "2004-05-26",
            "en",
            "will therefore remain unchanged at 2.70%",
            "10:00",
            150,
        ),
        (
            "mps_2004_ms.html",
            "2004-05-26",
            "ms",
            "Pertumbuhan ekonomi yang kukuh disokong",
            "10:00",
            150,
        ),
        (
            "mps_2010_en.html",
            "2010-05-13",
            "en",
            "decided to raise the Overnight Policy Rate",
            "10:00",
            250,
        ),
        (
            "mps_2022_en.html",
            "2022-11-03",
            "en",
            "decided to increase the Overnight Policy Rate",
            "07:00",
            600,
        ),
        ("mps_2022_ms.html", "2022-11-03", "ms", "menaikkan Kadar Dasar Semalaman", "07:00", 600),
        (
            "mps_2026_en.html",
            "2026-09-03",
            "en",
            "decided to maintain the Overnight Policy Rate",
            "07:00",
            350,
        ),
    ],
)
def test_parse_statement(
    tmp_path: Path, name: str, iso: str, lang: str, sentence: str, utc_hhmm: str, min_words: int
) -> None:
    doc = _parse(tmp_path, name, {"date": iso, "language": lang, "doc_type": "statement"})
    assert doc.bank == "bnm" and doc.doc_type == "statement" and doc.language == lang
    assert doc.date == date.fromisoformat(iso)
    assert doc.title in {"Monetary Policy Statement", "Pernyataan Dasar Monetari"}
    assert doc.published_at_utc is not None
    assert doc.published_at_utc.strftime("%H:%M") == utc_hhmm
    assert doc.parallel_id == f"bnm:{iso}:statement"
    assert sentence in doc.text
    assert len(doc.text.split()) >= min_words
    assert len(doc.sections) >= 3
    assert doc.text == "\n\n".join(s.text for s in doc.sections)
    for bad in BOILERPLATE:
        assert bad not in doc.text
    assert doc.sha256 == "ab" * 32 and doc.fetched_at.year == 2026
    assert doc.url == "https://www.bnm.gov.my/x"


def test_old_page_single_paragraph_is_split(tmp_path: Path) -> None:
    doc = _parse(tmp_path, "mps_2004_en.html", {"date": "2004-05-26"})
    assert [s.text.split()[0] for s in doc.sections] == ["The", "Going", "Inflation", "The"]


def test_embargo_hour_is_1800_myt_then_1500(tmp_path: Path) -> None:
    old = _parse(tmp_path, "mps_2010_en.html", {"date": "2010-05-13"})
    new = _parse(tmp_path, "mps_2022_en.html", {"date": "2022-11-03"})
    assert old.published_at_utc == datetime(2010, 5, 13, 10, 0, tzinfo=UTC)
    assert new.published_at_utc == datetime(2022, 11, 3, 7, 0, tzinfo=UTC)


def test_translations_share_parallel_id(tmp_path: Path) -> None:
    en = _parse(tmp_path, "mps_2022_en.html", {"date": "2022-11-03"})
    ms = _parse(tmp_path, "mps_2022_ms.html", {"date": "2022-11-03"})
    assert en.parallel_id == ms.parallel_id == parallel_id(date(2022, 11, 3))
    assert {en.doc_id, ms.doc_id} == {
        "bnm:2022-11-03:statement:en",
        "bnm:2022-11-03:statement:ms",
    }


def test_language_comes_from_page_not_hint(tmp_path: Path) -> None:
    doc = _parse(tmp_path, "mps_2022_ms.html", {"date": "2022-11-03", "language": "en"})
    assert doc.language == "ms"


@pytest.mark.parametrize(
    ("name", "iso"),
    [("mps_2004_ms.html", "2004-05-26"), ("mps_2010_en.html", "2010-05-13")],
)
def test_date_from_header_without_hints(tmp_path: Path, name: str, iso: str) -> None:
    assert _parse(tmp_path, name, {}).date == date.fromisoformat(iso)


def test_missing_article_or_date_gives_nothing(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    assert a.parse(_raw(b"<html><body><p>nothing</p></body></html>"), {"date": "2020-01-01"}) == []
    html = (FIX / "mps_2004_en.html").read_text()
    stripped = html.replace("26 May 2004", "").replace("text-muted", "x")
    assert a.parse(_raw(stripped.encode()), {}) == []
    empty = '<html><body><div class="journal-content-article"><p> </p></div></body></html>'
    assert a.parse(_raw(empty.encode()), {"date": "2020-01-01"}) == []


def test_unparseable_header_date(tmp_path: Path) -> None:
    html = (FIX / "mps_2004_en.html").read_text().replace("26 May 2004\n", "31 Foo 2004\n")
    assert _adapter(tmp_path).parse(_raw(html.encode()), {}) == []


def test_no_embargo_time_means_no_timestamp(tmp_path: Path) -> None:
    html = (FIX / "mps_2004_en.html").read_text().replace(" 1800 ", " ")
    docs = _adapter(tmp_path).parse(_raw(html.encode()), {"date": "2004-05-26"})
    assert docs[0].published_at_utc is None


def test_missing_lang_falls_back_to_hint(tmp_path: Path) -> None:
    html = (FIX / "mps_2004_ms.html").read_text().replace(' lang="ms-MY"', "")
    docs = _adapter(tmp_path).parse(_raw(html.encode()), {"date": "2004-05-26", "language": "ms"})
    assert docs[0].language == "ms"


def test_release_time_and_urls() -> None:
    assert release_time(date(2022, 11, 3), "1500") == datetime(2022, 11, 3, 7, 0, tzinfo=UTC)
    url = update_language_url("/-/monetary-policy-statement-03112022", "ms")
    assert url == (
        "https://www.bnm.gov.my/c/portal/update_language?p_l_id=182"
        "&redirect=%2F-%2Fmonetary-policy-statement-03112022&languageId=ms_MY"
    )
    assert update_language_url("/a", "en", page_id=7).endswith("languageId=en_US")


@pytest.mark.parametrize("name", ["opr_index_en.html", "opr_index_ms.html"])
def test_parse_index(name: str) -> None:
    entries = list(BNMAdapter.parse_index((FIX / name).read_bytes()))
    assert len(entries) == 141
    dates = [d for d, _ in entries]
    assert min(dates) == date(2004, 5, 26) and max(dates) == date(2026, 9, 3)
    assert (date(2022, 11, 3), "/-/monetary-policy-statement-03112022") in entries


def test_parse_index_ignores_bad_links() -> None:
    html = (
        '<a href="/-/monetary-policy-statement-31022020">x</a>'
        '<a href="/-/other-page">y</a><a name="z">no href</a>'
        '<a href="/-/monetary-policy-statement-01032020">ok</a>'
    )
    assert list(BNMAdapter.parse_index(html)) == [
        (date(2020, 3, 1), "/-/monetary-policy-statement-01032020")
    ]


def _index_fetcher(tmp_path: Path) -> PoliteFetcher:
    f = PoliteFetcher(raw_dir=tmp_path, offline=True)
    _cache(
        f,
        update_language_url(INDEX_PATH, "en", page_id=INDEX_PAGE_ID),
        (FIX / "opr_index_en.html").read_bytes(),
    )
    return f


def test_list_urls_pairs_languages(tmp_path: Path) -> None:
    items = list(BNMAdapter(_index_fetcher(tmp_path)).list_urls(2022, 2022))
    assert len(items) == 12  # 6 meetings x 2 languages
    assert [h["language"] for _, h in items[:2]] == ["en", "ms"]
    assert items[0][1]["date"] == "2022-01-20" and items[-1][1]["date"] == "2022-11-03"
    assert items[0][1]["parallel_id"] == items[1][1]["parallel_id"] == "bnm:2022-01-20:statement"
    assert items[0][0].endswith("monetary-policy-statement-20012022&languageId=en_US")
    assert items[1][0].endswith("monetary-policy-statement-20012022&languageId=ms_MY")
    assert all(h["doc_type"] == "statement" for _, h in items)


def test_list_urls_year_bounds(tmp_path: Path) -> None:
    a = BNMAdapter(_index_fetcher(tmp_path))
    assert len(list(a.list_urls(1990, 2004))) == 6  # 3 meetings in 2004
    assert len(list(a.list_urls(2026, 2030))) == 10
    assert list(a.list_urls(2000, 2003)) == []


def test_fetch_end_to_end_offline(tmp_path: Path) -> None:
    f = _index_fetcher(tmp_path)
    for lang, name in (("en", "mps_2004_en.html"), ("ms", "mps_2004_ms.html")):
        url = update_language_url("/-/monetary-policy-statement-26052004", lang)
        _cache(f, url, (FIX / name).read_bytes())
    docs: list[Document] = []
    a = BNMAdapter(f)
    for url, hints in list(a.list_urls(2004, 2004))[:2]:
        docs += a.parse(f.get("bnm", url), hints)
    assert [d.language for d in docs] == ["en", "ms"]
    assert docs[0].parallel_id == docs[1].parallel_id
    assert all(d.fetched_at == datetime(2026, 1, 1, tzinfo=UTC) for d in docs)


@pytest.mark.network
def test_live_smoke(tmp_path: Path) -> None:
    fetcher = PoliteFetcher(raw_dir=tmp_path)
    a = BNMAdapter(fetcher)
    items = list(a.list_urls(2026, 2026))[:2]
    assert [h["language"] for _, h in items] == ["en", "ms"]
    docs = [d for url, h in items for d in a.parse(fetcher.get("bnm", url), h)]
    assert [d.language for d in docs] == ["en", "ms"]
    assert all(len(d.sections) >= 3 for d in docs)


def test_untranslated_placeholder_is_not_a_document(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    raw = _raw((FIX / "mps_2005_ms_placeholder.html").read_bytes())
    assert _adapter(tmp_path).parse(raw, {"date": "2005-12-15", "language": "ms"}) == []
    assert "placeholder" in caplog.text


def test_statement_asset_after_listing_asset(tmp_path: Path) -> None:
    # 2008-10-24: a "Press Releases" listing asset precedes the statement asset
    doc = _parse(tmp_path, "mps_2008_en_listing_first.html", {"date": "2008-10-24"})
    assert "Filter by year" not in doc.text and "Print" not in doc.text
    assert "leave the Overnight Policy Rate (OPR) unchanged at 3.50 percent" in doc.text
    assert doc.published_at_utc == datetime(2008, 10, 24, 3, 45, tzinfo=UTC)
    assert len(doc.sections) >= 3


def test_no_statement_article_returns_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    html = b'<div class="journal-content-article"><p>Press Releases</p></div>'
    assert _adapter(tmp_path).parse(_raw(html), {"date": "2008-10-24"}) == []
    assert "no statement article" in caplog.text


def test_long_paragraph_before_table_is_kept(tmp_path: Path) -> None:
    # 2007-11-26: the whole statement is one <p> directly followed by the meeting-schedule table
    doc = _parse(tmp_path, "mps_2007_en_table_after_text.html", {"date": "2007-11-26"})
    assert len(doc.sections) >= 4
    assert "leave the Overnight Policy Rate (OPR) unchanged at 3.50 percent" in doc.text
    assert "24 November 2008" not in doc.text
