"""Offline tests for the RBA adapter (fixtures are trimmed real pages)."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from cbtone.schema import Document
from cbtone.sources.base import PoliteFetcher, RawResponse
from cbtone.sources.rba import BASE, RBAAdapter, statement_release_time

FIX = Path(__file__).parent / "fixtures" / "rba"
BOILERPLATE = ["Share", "Last Update", "Skip to main", "Enquiries", "Communications Department"]


def _adapter(tmp_path: Path, **kw: object) -> RBAAdapter:
    return RBAAdapter(PoliteFetcher(raw_dir=tmp_path, offline=True, **kw))  # type: ignore[arg-type]


def _raw(name: str, url: str | None = None) -> RawResponse:
    return RawResponse(
        url=url or f"{BASE}/x/{name}.html",
        content=(FIX / f"{name}.html").read_bytes(),
        content_type="text/html",
        sha256="ab" * 32,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        from_cache=True,
    )


def _parse(tmp_path: Path, name: str, doc_type: str, iso: str) -> Document:
    docs = _adapter(tmp_path).parse(_raw(name), {"doc_type": doc_type, "date": iso})
    assert len(docs) == 1
    return docs[0]


def _check_common(doc: Document, min_words: int, min_sections: int = 3) -> None:
    assert doc.bank == "rba" and doc.language == "en"
    assert len(doc.text.split()) >= min_words
    assert len(doc.sections) >= min_sections
    assert doc.text == "\n\n".join(s.text for s in doc.sections)
    for bad in BOILERPLATE:
        assert bad not in doc.text
    assert doc.sha256 == "ab" * 32 and doc.fetched_at.year == 2026


@pytest.mark.parametrize(
    ("name", "iso", "d", "sentence", "utc", "min_words"),
    [
        # 2000: released the day after the meeting; no documented time
        ("statement_2000", "2000-08-02", "2000-08-01", "to 6.25 per cent", None, 250),
        # 2007: first statement after a hold; meeting 4 Dec, release 5 Dec, time undocumented
        ("statement_2007", "2007-12-05", "2007-12-04", "leave the cash rate", None, 250),
        ("statement_2023", "2023-10-03", "2023-10-03", "4.10 per cent", "2023-10-03T03:30", 250),
        ("statement_2024", "2024-12-10", "2024-12-10", "4.35 per cent", "2024-12-10T03:30", 500),
        (
            "statement_2026",
            "2026-09-29",
            "2026-09-29",
            "increase the cash rate",
            "2026-09-29T04:30",
            400,
        ),
    ],
)
def test_statement(
    tmp_path: Path, name: str, iso: str, d: str, sentence: str, utc: str | None, min_words: int
) -> None:
    doc = _parse(tmp_path, name, "statement", iso)
    assert doc.doc_type == "statement" and doc.date == date.fromisoformat(d)
    assert sentence in doc.text
    assert doc.title.startswith("Statement by")
    if utc is None:
        assert doc.published_at_utc is None
    else:
        assert doc.published_at_utc is not None
        assert doc.published_at_utc.strftime("%Y-%m-%dT%H:%M") == utc
    _check_common(doc, min_words, min_sections=2 if name == "statement_2000" else 3)
    assert "Related" not in doc.text and "More on the" not in doc.text


def test_statement_headings(tmp_path: Path) -> None:
    doc = _parse(tmp_path, "statement_2024", "statement", "2024-12-10")
    headings = {s.heading for s in doc.sections}
    assert "Underlying inflation remains too high." in headings
    assert doc.sections[0].heading is None
    doc26 = _parse(tmp_path, "statement_2026", "statement", "2026-09-29")
    assert "Decision" in {s.heading for s in doc26.sections}
    assert doc26.title == "Statement by the Monetary Policy Board: Monetary Policy Decision"


def test_statement_list_items_are_sections(tmp_path: Path) -> None:
    doc = _parse(tmp_path, "statement_2000", "statement", "2000-08-02")
    assert any(s.text.startswith("Over the past twelve months") for s in doc.sections)


@pytest.mark.parametrize(
    ("name", "iso", "sentence", "first_heading"),
    [
        ("minutes_2006", "2006-10-03", "puzzling set of figures", "Economic Conditions"),
        (
            "minutes_2024",
            "2024-12-10",
            "central banks in most advanced economies",
            "Financial conditions",
        ),
    ],
)
def test_minutes(tmp_path: Path, name: str, iso: str, sentence: str, first_heading: str) -> None:
    doc = _parse(tmp_path, name, "minutes", iso)
    assert doc.doc_type == "minutes" and doc.date == date.fromisoformat(iso)
    assert doc.published_at_utc is None
    _check_common(doc, 1500, min_sections=10)
    assert sentence in doc.text
    assert doc.sections[0].heading == first_heading
    # attendance lists and the "minutes approved" line are dropped
    headings = {(s.heading or "").lower() for s in doc.sections}
    assert not headings & {"present", "members participating", "others participating", "minutes"}
    assert "Hybrid" not in doc.text and "Sydney \u2013 3 October" not in doc.text
    assert "Related contents" not in doc.text and "More on the" not in doc.text


def test_press_conference(tmp_path: Path) -> None:
    doc = _parse(tmp_path, "pc_2024", "press_conference", "2024-12-10")
    assert doc.doc_type == "press_conference" and doc.date == date(2024, 12, 10)
    assert doc.published_at_utc is None
    _check_common(doc, 1000, min_sections=10)
    intro = [s for s in doc.sections if s.heading is None]
    qa = [s for s in doc.sections if s.heading == "Q&A"]
    assert len(intro) >= 1 and len(qa) >= 8
    assert doc.sections[: len(intro)] == intro
    assert intro[0].text.startswith("Good afternoon, everyone.")
    assert all(": " in s.text[:40] for s in qa)
    assert qa[0].text.startswith("David Chau: ")
    assert any(s.text.startswith("Michele Bullock: ") for s in qa)
    assert not any(s.text.split(": ", 1)[1].startswith("- ") for s in qa)
    assert "Watch video" not in doc.text and "Audio" not in doc.text


def test_parse_edge_cases(tmp_path: Path) -> None:
    ad = _adapter(tmp_path)
    empty = RawResponse(
        url=f"{BASE}/x", content=b"<html><body><p>x</p></body></html>", content_type="text/html",
        sha256="0" * 64, fetched_at=datetime(2026, 1, 1, tzinfo=UTC), from_cache=True,
    )  # fmt: skip
    for dt in ("statement", "minutes", "press_conference"):
        assert ad.parse(empty, {"doc_type": dt, "date": "2020-01-01"}) == []
    # transcript block without a speech-part div and with an empty paragraph
    odd = empty.__class__(
        url=f"{BASE}/x",
        content=(
            b'<div id="content"><h1>T</h1><div class="page-transcript">'
            b'<h3 class="speaker">A</h3><h3 class="speaker">B</h3>'
            b'<div class="speech-part"><p> </p><p>Hello\x92 there</p></div></div></div>'
        ),
        content_type="text/html",
        sha256="0" * 64,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        from_cache=True,
    )
    (doc,) = ad.parse(odd, {"doc_type": "press_conference", "date": "2024-02-06"})
    assert doc.text == "Hello\u2019 there"  # C1 control chars map through cp1252


def test_bad_embedded_datetime_falls_back_to_rule(tmp_path: Path) -> None:
    html = (FIX / "statement_2024.html").read_text().replace("2024-12-10", "2024-12-10T25:99+10:00")
    raw = RawResponse(
        url=f"{BASE}/x", content=html.encode(), content_type="text/html", sha256="0" * 64,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC), from_cache=True,
    )  # fmt: skip
    (doc,) = _adapter(tmp_path).parse(raw, {"doc_type": "statement", "date": "2024-12-10"})
    assert doc.published_at_utc == datetime(2024, 12, 10, 3, 30, tzinfo=UTC)


def test_release_time_rule() -> None:
    assert statement_release_time(date(2007, 12, 5)) is None
    # AEDT (summer) 14:30 = 03:30 UTC; AEST (winter) 14:30 = 04:30 UTC
    assert statement_release_time(date(2012, 12, 4)) == datetime(2012, 12, 4, 3, 30, tzinfo=UTC)
    assert statement_release_time(date(2012, 7, 3)) == datetime(2012, 7, 3, 4, 30, tzinfo=UTC)


def test_minutes_date() -> None:
    f = RBAAdapter.minutes_date
    assert f("/monetary-policy/rba-board-minutes/2006/03102006.html") == date(2006, 10, 3)
    assert f("/monetary-policy/rba-board-minutes/2024/2024-12-10.html") == date(2024, 12, 10)
    assert f("/monetary-policy/rba-board-minutes/2024/other.html") is None


# -- discovery -------------------------------------------------------------
def _seed(fetcher: PoliteFetcher, url: str, fixture: str) -> None:
    body, meta = fetcher._paths("rba", url)
    body.parent.mkdir(parents=True, exist_ok=True)
    body.write_bytes((FIX / fixture).read_bytes())
    meta.write_text(
        json.dumps(
            {
                "url": url,
                "content_type": "text/html",
                "sha256": "00",
                "fetched_at": "2026-01-01T00:00:00+00:00",
            }
        )
    )


def test_list_urls_offline(tmp_path: Path) -> None:
    f = PoliteFetcher(raw_dir=tmp_path, offline=True)
    _seed(f, f"{BASE}/monetary-policy/int-rate-decisions/2000/", "index_decisions_2000.html")
    _seed(f, f"{BASE}/monetary-policy/int-rate-decisions/2024/", "index_decisions_2024.html")
    _seed(f, f"{BASE}/media-releases/2024/mr-24-27.html", "statement_2024.html")
    _seed(
        f, f"{BASE}/media-releases/2024/mr-24-24.html", "statement_2023.html"
    )  # no media conf link
    _seed(f, f"{BASE}/monetary-policy/int-rate-decisions/2006/", "index_decisions_2006.html")
    _seed(f, f"{BASE}/monetary-policy/rba-board-minutes/2006/", "index_minutes_2006.html")
    _seed(f, f"{BASE}/monetary-policy/rba-board-minutes/2024/", "index_minutes_2024.html")
    ad = RBAAdapter(f)

    old = list(ad.list_urls(2000, 2000))
    assert [h["date"] for _, h in old] == ["2000-02-02", "2000-04-05", "2000-05-03", "2000-08-02"]
    assert old[-1][0] == f"{BASE}/media-releases/2000/mr-00-13.html"
    assert all(h["doc_type"] == "statement" and h["language"] == "en" for _, h in old)

    new = list(ad.list_urls(2024, 2024))
    got = [(h["doc_type"], h["date"]) for _, h in new]
    assert got == [
        ("statement", "2024-11-05"),
        ("statement", "2024-12-10"),
        ("press_conference", "2024-12-10"),
        ("minutes", "2024-11-05"),
        ("minutes", "2024-12-10"),
    ]
    urls = dict(zip(got, [u for u, _ in new], strict=True))
    assert (
        urls[("press_conference", "2024-12-10")] == f"{BASE}/speeches/2024/mc-gov-2024-12-10.html"
    )
    assert urls[("minutes", "2024-12-10")].endswith("/rba-board-minutes/2024/2024-12-10.html")

    m06 = [h for _, h in ad.list_urls(2006, 2006) if h["doc_type"] == "minutes"]
    assert [h["date"] for h in m06] == ["2006-10-03", "2006-11-07", "2006-12-05"]


def test_list_urls_skips_missing_years_and_pre_start(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404 if request.url.path != "/robots.txt" else 200, text="")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    ad = RBAAdapter(PoliteFetcher(raw_dir=tmp_path, min_interval_s=0, client=client))
    assert list(ad.list_urls(2090, 2090)) == []
    assert list(ad.list_urls(1900, 1889)) == []


def test_list_urls_server_error_propagates(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500 if request.url.path != "/robots.txt" else 200, text="")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    ad = RBAAdapter(PoliteFetcher(raw_dir=tmp_path, min_interval_s=0, client=client))
    with pytest.raises(httpx.HTTPStatusError):
        list(ad.list_urls(2024, 2024))


def test_fetch_end_to_end_offline(tmp_path: Path) -> None:
    f = PoliteFetcher(raw_dir=tmp_path, offline=True)
    _seed(f, f"{BASE}/monetary-policy/int-rate-decisions/2000/", "index_decisions_2000.html")
    for u in ("mr-00-13", "mr-00-11", "mr-00-08", "mr-00-03"):
        _seed(f, f"{BASE}/media-releases/2000/{u}.html", "statement_2000.html")
    docs = list(RBAAdapter(f).fetch(2000, 2000))
    assert len(docs) == 4
    assert {d.doc_type for d in docs} == {"statement"}


@pytest.mark.network
def test_live_smoke(tmp_path: Path) -> None:
    ad = RBAAdapter(PoliteFetcher(raw_dir=tmp_path))
    docs = []
    for url, hints in ad.list_urls(2008, 2008):
        docs.extend(ad.parse(ad.fetcher.get("rba", url), hints))
        if len(docs) >= 2:
            break
    assert docs and all(len(d.text.split()) > 100 for d in docs)
