"""Offline tests for the Fed (FOMC) adapter (fixtures are trimmed real pages / one real PDF)."""

import io
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from pypdf import PdfWriter

from cbtone.schema import Document
from cbtone.sources import fed
from cbtone.sources.base import PoliteFetcher, RawResponse
from cbtone.sources.fed import (
    BASE,
    CALENDAR_URL,
    FedAdapter,
    minutes_release,
    parse_calendar_index,
    parse_historical_index,
    statement_release,
)

FIX = Path(__file__).parent / "fixtures" / "fed"
BOILERPLATE = ["Share", "Last update", "Last Update", "Skip to main", "Return to text", "Print"]


def _adapter(tmp_path: Path) -> FedAdapter:
    return FedAdapter(PoliteFetcher(raw_dir=tmp_path, offline=True))


def _raw(content: bytes, name: str = "x") -> RawResponse:
    return RawResponse(
        url=f"{BASE}/{name}",
        content=content,
        content_type="text/html",
        sha256="ab" * 32,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        from_cache=True,
    )


def _parse(tmp_path: Path, name: str, doc_type: str, iso: str, **extra: str) -> Document:
    hints = {"doc_type": doc_type, "date": iso, "language": "en", **extra}
    docs = _adapter(tmp_path).parse(_raw((FIX / name).read_bytes(), name), hints)
    assert len(docs) == 1
    return docs[0]


def _hm(dt: datetime | None) -> str:
    assert dt is not None
    return dt.astimezone(UTC).strftime("%H:%M")


def _check_common(doc: Document) -> None:
    assert doc.bank == "fed" and doc.language == "en"
    assert doc.text == "\n\n".join(s.text for s in doc.sections)
    assert doc.sha256 == "ab" * 32 and doc.fetched_at.year == 2026
    assert doc.url.startswith(BASE)
    for bad in BOILERPLATE:
        assert bad not in doc.text, bad


# ------------------------------------------------------------------ statements
@pytest.mark.parametrize(
    ("name", "iso", "sentence", "min_words", "min_sections", "utc_hhmm"),
    [
        ("statement_1994-02-04.htm", "1994-02-04", "increase slightly the degree", 60, 3, None),
        (
            "statement_1998-11-17.htm",
            "1998-11-17",
            "reduction in the discount rate",
            100,
            4,
            "19:15",
        ),
        (
            "statement_2008-01-30.htm",
            "2008-01-30",
            "lower its target for the federal funds",
            200,
            4,
            "19:15",
        ),
        ("statement_2013-09-18.htm", "2013-09-18", "reaffirmed its view", 600, 4, "18:00"),
        ("statement_2026-01-28.htm", "2026-01-28", "maintain the target range", 250, 4, "19:00"),
    ],
)
def test_statement(
    tmp_path: Path,
    name: str,
    iso: str,
    sentence: str,
    min_words: int,
    min_sections: int,
    utc_hhmm: str | None,
) -> None:
    doc = _parse(tmp_path, name, "statement", iso)
    _check_common(doc)
    assert doc.doc_type == "statement" and doc.date == date.fromisoformat(iso)
    assert doc.title == f"FOMC statement, {iso}"
    assert sentence in doc.text
    assert len(doc.text.split()) >= min_words
    assert len(doc.sections) >= min_sections
    if utc_hhmm is None:
        assert doc.published_at_utc is None
    else:
        assert _hm(doc.published_at_utc) == utc_hhmm
        assert doc.published_at_utc is not None and doc.published_at_utc.tzinfo is not None


def test_statement_no_navigation_or_voting_noise(tmp_path: Path) -> None:
    doc = _parse(tmp_path, "statement_2013-09-18.htm", "statement", "2013-09-18")
    assert not any(s.text.lower().startswith("for immediate release") for s in doc.sections)
    assert doc.sections[-1].text.startswith("Voting for the FOMC monetary policy action were")


def test_legacy_footer_time_used_when_dates_match(tmp_path: Path) -> None:
    # 1998-11-17 footer "Last update: November 17, 1998, 2:15 PM" (EST = UTC-5)
    doc = _parse(tmp_path, "statement_1998-11-17.htm", "statement", "1998-11-17")
    assert doc.published_at_utc == datetime(1998, 11, 17, 19, 15, tzinfo=UTC)
    # unscheduled hint is ignored when the footer carries the time (documented behaviour)
    doc2 = _parse(tmp_path, "statement_1998-11-17.htm", "statement", "1998-11-17", unscheduled="1")
    assert doc2.published_at_utc == doc.published_at_utc


def test_footer_time_rejected_when_date_differs(tmp_path: Path) -> None:
    # same page, but the doc date differs from the footer date and there is no Release Date line
    html = (
        b"<html><body><p>Hello world.</p><p>Last update: March 20, 2003, 2:00 PM</p></body></html>"
    )
    soup = BeautifulSoup(html, "lxml")
    assert fed._footer_time(soup, date(2003, 3, 21)) is None
    assert fed._footer_time(soup, date(2003, 3, 20)) == datetime(2003, 3, 20, 19, 0, tzinfo=UTC)
    assert fed._footer_time(soup, None) is None
    bad_month = BeautifulSoup(b"<p>Last update: Smarch 3, 2003, 2:00 PM</p>", "lxml")
    assert fed._footer_time(bad_month, date(2003, 3, 3)) is None
    assert fed._footer_time(BeautifulSoup(b"<p>nothing</p>", "lxml"), date(2003, 3, 3)) is None
    # 12 AM / 12 PM handling
    noon = BeautifulSoup(b"<p>Last update: May 1, 2003, 12:05 PM</p>", "lxml")
    assert fed._footer_time(noon, date(2003, 5, 1)) == datetime(2003, 5, 1, 16, 5, tzinfo=UTC)


def test_statement_release_rules() -> None:
    # 14:00 ET from 2013; EDT in June (UTC-4), EST in December (UTC-5)
    assert _hm(statement_release(date(2013, 6, 19), False, True)) == "18:00"
    assert _hm(statement_release(date(2024, 12, 18), False, True)) == "19:00"
    # 2013-01-01 boundary
    assert _hm(statement_release(date(2013, 1, 1), False, False)) == "19:00"
    assert _hm(statement_release(date(2012, 12, 12), False, False)) == "19:15"
    # press-conference days Apr 2011 - 2012: no guess
    assert statement_release(date(2012, 4, 25), False, True) is None
    assert statement_release(date(2011, 4, 27), False, True) is None
    # ... but before the first press conference, or without one, the 14:15 rule applies
    assert _hm(statement_release(date(2011, 4, 26), False, True)) == "18:15"
    assert _hm(statement_release(date(2012, 4, 25), False, False)) == "18:15"
    # 1999 boundary and earlier
    assert _hm(statement_release(date(1999, 1, 1), False, False)) == "19:15"
    assert statement_release(date(1998, 12, 22), False, False) is None
    # unscheduled: always None
    assert statement_release(date(2020, 3, 15), True, False) is None


def test_minutes_release_rule() -> None:
    assert minutes_release(None) is None
    assert minutes_release(date(2004, 12, 31)) is None
    assert _hm(minutes_release(date(2013, 4, 10))) == "18:00"
    assert _hm(minutes_release(date(2012, 5, 16))) == "18:00"
    assert _hm(minutes_release(date(2005, 1, 1))) == "19:00"


# ------------------------------------------------------------------ minutes
def test_minutes_2013(tmp_path: Path) -> None:
    doc = _parse(tmp_path, "minutes_2013-09-18.htm", "minutes", "2013-09-18", released="2013-10-09")
    _check_common(doc)
    assert doc.doc_type == "minutes" and doc.date == date(2013, 9, 18)
    assert doc.title == "FOMC minutes, 2013-09-18"
    assert _hm(doc.published_at_utc) == "18:00"
    assert len(doc.text.split()) >= 5000 and len(doc.sections) >= 20
    headings = {s.heading for s in doc.sections}
    assert "Committee Policy Action" in headings
    assert any("Federal Open Market Committee was held" in s.text for s in doc.sections)
    # the date line / title banner does not become a section
    assert not any(
        s.text.startswith("Minutes of the Federal Open Market Committee") for s in doc.sections
    )


def test_minutes_2003_uses_footer_time(tmp_path: Path) -> None:
    # released 2003-03-20 < 2005 -> falls back to the page footer "2:00 PM"
    doc = _parse(tmp_path, "minutes_2003-01-29.htm", "minutes", "2003-01-29", released="2003-03-20")
    _check_common(doc)
    assert doc.date == date(2003, 1, 29)
    assert doc.published_at_utc == datetime(2003, 3, 20, 19, 0, tzinfo=UTC)
    assert len(doc.text.split()) >= 5000 and len(doc.sections) >= 50
    assert "TEMPORARY AUTHORITY TO OPERATE THE SYSTEM ACCOUNT" in {s.heading for s in doc.sections}
    assert any("The meeting adjourned at 12:55 p.m." in s.text for s in doc.sections)


def test_minutes_without_released_hint(tmp_path: Path) -> None:
    doc = _parse(tmp_path, "minutes_2013-09-18.htm", "minutes", "2013-09-18")
    assert doc.published_at_utc is None


# ------------------------------------------------------------------ press conference
def test_press_conference_pdf(tmp_path: Path) -> None:
    doc = _parse(tmp_path, "presconf_2013-03-20.pdf", "press_conference", "2013-03-20")
    assert doc.bank == "fed" and doc.language == "en" and doc.doc_type == "press_conference"
    assert doc.date == date(2013, 3, 20)
    assert doc.title == "FOMC press conference transcript, 2013-03-20"
    assert doc.published_at_utc is None
    assert doc.text == "\n\n".join(s.text for s in doc.sections)
    assert len(doc.text.split()) >= 5000
    intro = [s for s in doc.sections if s.heading == "Introductory statement"]
    qa = [s for s in doc.sections if s.heading == "Q&A"]
    assert len(intro) >= 3 and len(qa) >= 20
    assert doc.sections[: len(intro)] == intro
    assert doc.sections[-len(qa) :] == qa
    assert intro[0].text.startswith("CHAIRMAN BERNANKE. Good afternoon")
    assert any("concluded a two-day meeting" in s.text for s in intro)
    assert not any("concluded a two-day meeting" in s.text for s in qa)
    # page headers / numbers removed
    assert not any(s.text.strip().isdigit() for s in doc.sections)
    assert "Press Conference" not in "".join(s.text for s in intro if len(s.text) < 60)


def test_pdf_paragraph_helpers() -> None:
    text = (
        "Page 1 of 3\n"
        "March 20, 2013 Chairman Bernanke Press Conference\n"
        "CHAIRMAN BERNANKE. Good afternoon.  \n"
        "We met today and decided to hold a long line of text here that wraps around the page\n"
        "onto the next line.\n"
        "STEVE LIESMAN. Thank you, Mr. Chairman.\n"
        "CHAIRMAN BERNANKE. Well, I think that is right.\n"
    )
    paras = fed._pdf_paragraphs(text)
    assert paras[0] == "CHAIRMAN BERNANKE. Good afternoon."
    assert paras[1].endswith("onto the next line.")
    assert paras[2].startswith("STEVE LIESMAN.")
    secs = fed._pdf_sections(paras)
    assert [s.heading for s in secs] == [
        "Introductory statement",
        "Introductory statement",
        "Q&A",
        "Q&A",
    ]
    # text before the Chair speaks has no heading
    pre = fed._pdf_sections(["Preamble text without a speaker.", *paras])
    assert pre[0].heading is None
    assert fed._pdf_paragraphs("") == []


def test_blank_pdf_yields_no_documents(tmp_path: Path) -> None:
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    docs = _adapter(tmp_path).parse(
        _raw(buf.getvalue(), "f.pdf"),
        {"doc_type": "press_conference", "date": "2013-03-20", "language": "en"},
    )
    assert docs == []


# ------------------------------------------------------------------ edge cases
def test_empty_html_returns_no_documents(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    for dt in ("statement", "minutes"):
        assert a.parse(_raw(b""), {"doc_type": dt, "date": "2013-09-18", "language": "en"}) == []
        html = b"<html><body><nav>Menu</nav><script>x=1</script></body></html>"
        assert a.parse(_raw(html), {"doc_type": dt, "date": "2013-09-18", "language": "en"}) == []


def test_unscheduled_and_presser_hints_affect_release(tmp_path: Path) -> None:
    body = b"<html><body><div id='article'><p>The Committee decided to act.</p></div></body></html>"
    a = _adapter(tmp_path)

    def pub(d: str, **h: str) -> datetime | None:
        docs = a.parse(_raw(body), {"doc_type": "statement", "date": d, "language": "en", **h})
        return docs[0].published_at_utc

    assert _hm(pub("2015-03-18")) == "18:00"
    assert pub("2015-03-18", unscheduled="1") is None
    assert pub("2012-04-25", has_presser="1") is None
    assert _hm(pub("2012-04-25")) == "18:15"
    assert pub("1995-02-01") is None


def test_unknown_doc_type_label_and_body_fallback(tmp_path: Path) -> None:
    # no #article container -> falls back to <body>; boilerplate nav/footers are dropped
    html = (
        b"<html><body><nav>Home</nav><p>Para one is here.</p><!-- c --><p><b>Heading</b></p>"
        b"<p>Para two<br/>continues.</p><footer>Contact</footer></body></html>"
    )
    docs = _adapter(tmp_path).parse(
        _raw(html), {"doc_type": "other", "date": "2013-09-18", "language": "en"}
    )
    assert docs[0].title == "FOMC document, 2013-09-18"
    assert [(s.heading, s.text) for s in docs[0].sections] == [
        (None, "Para one is here."),
        ("Heading", "Para two continues."),
    ]


# ------------------------------------------------------------------ index parsing
def test_historical_index_1999() -> None:
    items = parse_historical_index((FIX / "index_hist_1999.htm").read_bytes())
    kinds = [(i.doc_type, i.day.isoformat()) for i in items]
    # panel heading "February 2-3 Meeting" -> meeting date is the last day
    assert ("minutes", "1999-02-03") in kinds
    assert ("statement", "1999-05-18") in kinds
    assert ("minutes", "1999-03-30") in kinds
    st = next(i for i in items if i.doc_type == "statement" and i.day == date(1999, 5, 18))
    assert st.path == "/boarddocs/press/general/1999/19990518/" and not st.unscheduled
    mn = next(i for i in items if i.path == "/fomc/minutes/19990202.htm")
    assert mn.released == date(1999, 4, 1)
    # transcripts / Beige Book / Greenbook links are not collected
    assert all(i.doc_type in {"statement", "minutes", "press_conference"} for i in items)
    assert not any(".pdf" in i.path.lower() for i in items)


def test_historical_index_2008_intermeeting() -> None:
    items = parse_historical_index((FIX / "index_hist_2008.htm").read_bytes())
    by_path = {i.path: i for i in items}
    jan_call = by_path["/newsevents/press/monetary/20080122b.htm"]
    assert jan_call.unscheduled and jan_call.day == date(2008, 1, 21)
    mar_call = by_path["/newsevents/press/monetary/20080311a.htm"]
    assert mar_call.unscheduled and mar_call.day == date(2008, 3, 10)
    sched = by_path["/newsevents/press/monetary/20080130a.htm"]
    assert not sched.unscheduled and sched.day == date(2008, 1, 30)
    assert by_path["/monetarypolicy/fomcminutes20080130.htm"].released == date(2008, 2, 20)


def test_historical_index_2013_press_conference() -> None:
    items = parse_historical_index((FIX / "index_hist_2013.htm").read_bytes())
    by = {(i.doc_type, i.day.isoformat()): i for i in items}
    stmt = by[("statement", "2013-03-20")]
    assert stmt.path == "/newsevents/pressreleases/monetary20130320a.htm" and stmt.has_presser
    assert not by[("statement", "2013-01-30")].has_presser
    pc = by[("press_conference", "2013-03-20")]
    assert pc.path == "/mediacenter/files/FOMCpresconf20130320.pdf"
    assert by[("minutes", "2013-05-01")].released == date(2013, 5, 22)


def test_calendar_index() -> None:
    items = parse_calendar_index((FIX / "index_calendar.htm").read_bytes())
    by = {(i.doc_type, i.day.isoformat()): i for i in items}
    # "27-28" -> 28 January; PDF-only/implementation-note links are not picked as the statement
    s = by[("statement", "2026-01-28")]
    assert s.path == "/newsevents/pressreleases/monetary20260128a.htm" and s.has_presser
    # the Fed's own page spells this link "fomcpressconf" (double s) -> still recognised
    assert by[("press_conference", "2026-01-28")].path.endswith("FOMCpresconf20260128.pdf")
    assert by[("minutes", "2026-01-28")].released == date(2026, 2, 18)
    assert by[("minutes", "2026-03-18")].released == date(2026, 4, 8)  # "April 08, 2026"
    assert by[("press_conference", "2026-03-18")].path.endswith("FOMCpresconf20260318.pdf")
    # years are taken from the h4 headings, not from the order of the page
    assert ("statement", "2023-02-01") in by and ("minutes", "2023-03-22") in by
    assert not any(i.unscheduled for i in items)


def test_calendar_notation_vote_is_unscheduled() -> None:
    html = (
        "<h4>2020 FOMC Meetings</h4>"
        '<div class="fomc-meeting"><div class="fomc-meeting__month">Mar</div>'
        '<div class="fomc-meeting__date">15 (notation vote)</div>'
        '<a href="/newsevents/pressreleases/monetary20200315a.htm">HTML</a></div>'
    )
    (it,) = parse_calendar_index(html)
    assert it.unscheduled and it.day == date(2020, 3, 15)


def test_index_edge_cases() -> None:
    assert parse_historical_index("") == []
    assert parse_calendar_index("") == []
    # panel without h5 is skipped
    assert parse_historical_index("<div class='panel'><a href='/x'>y</a></div>") == []
    # unparsable heading -> date from the first document URL, still scheduled
    html = (
        "<div class='panel'><h5>Weird heading</h5>"
        "<a href='https://www.federalreserve.gov/fomc/minutes/19960130.htm#top'>Minutes</a></div>"
    )
    (it,) = parse_historical_index(html)
    assert it.day == date(1996, 1, 30) and it.path == "/fomc/minutes/19960130.htm"
    assert it.doc_type == "minutes" and it.released is None
    # heading with an unknown month and no usable link -> nothing
    assert parse_historical_index("<div class='panel'><h5>Foo 3 Meeting - 1999</h5></div>") == []
    # "Released" with an unknown month name is ignored
    html = (
        "<div class='panel'><h5>May 5 Meeting - 2000</h5>"
        "<a href='/fomc/minutes/20000505.htm'>Minutes</a> (Released Zork 3, 2000)</div>"
    )
    (it,) = parse_historical_index(html)
    assert it.released is None
    # calendar rows before any year heading, or missing month/date cells, or bad values: skipped
    row = (
        '<div class="fomc-meeting"><div class="fomc-meeting__month">{m}</div>'
        '<div class="fomc-meeting__date">{d}</div>'
        '<a href="/newsevents/pressreleases/monetary20200129a.htm">HTML</a></div>'
    )
    assert parse_calendar_index(row.format(m="January", d="29")) == []
    head = "<h4>2020 FOMC Meetings</h4>"
    assert parse_calendar_index(head + row.format(m="Zork", d="29")) == []
    assert parse_calendar_index(head + row.format(m="January", d="tbd")) == []
    assert parse_calendar_index(head + '<div class="fomc-meeting"></div>') == []
    # joint months "Jan/Feb" use the last month
    (it,) = parse_calendar_index(head + row.format(m="Jan/Feb", d="29"))
    assert it.day == date(2020, 2, 29)


# ------------------------------------------------------------------ list_urls
def _seed(f: PoliteFetcher, url: str, content: bytes) -> None:
    body, meta = f._paths("fed", url)
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


def _seeded(tmp_path: Path) -> FedAdapter:
    f = PoliteFetcher(raw_dir=tmp_path, offline=True)
    for year in (1999, 2008, 2013):
        _seed(
            f,
            f"{BASE}/monetarypolicy/fomchistorical{year}.htm",
            (FIX / f"index_hist_{year}.htm").read_bytes(),
        )
    _seed(f, CALENDAR_URL, (FIX / "index_calendar.htm").read_bytes())
    return FedAdapter(f)


def test_list_urls_across_eras(tmp_path: Path) -> None:
    a = _seeded(tmp_path)
    got = {y: list(a.list_urls(y, y)) for y in (1999, 2008, 2013)}
    for items in got.values():
        for url, hints in items:
            assert url.startswith(BASE) and hints["language"] == "en"
            assert hints["doc_type"] in {"statement", "minutes", "press_conference"}
            assert date.fromisoformat(hints["date"])
        assert [h["date"] for _, h in items] == sorted(h["date"] for _, h in items)

    u99 = {(h["doc_type"], h["date"]): u for u, h in got[1999]}
    assert u99[("statement", "1999-05-18")] == f"{BASE}/boarddocs/press/general/1999/19990518/"
    h99 = {(h["doc_type"], h["date"]): h for _, h in got[1999]}
    assert h99[("minutes", "1999-02-03")]["released"] == "1999-04-01"
    assert all(h["date"].startswith("1999") for _, h in got[1999])

    h08 = {h["date"]: h for _, h in got[2008] if h["doc_type"] == "statement"}
    assert h08["2008-01-21"]["unscheduled"] == "1"
    assert "unscheduled" not in h08["2008-01-30"]

    h13 = {(h["doc_type"], h["date"]): h for _, h in got[2013]}
    assert h13[("statement", "2013-03-20")]["has_presser"] == "1"
    assert ("press_conference", "2013-03-20") in h13
    pc_url = next(u for u, h in got[2013] if h["doc_type"] == "press_conference")
    assert pc_url == f"{BASE}/mediacenter/files/FOMCpresconf20130320.pdf"


def test_list_urls_calendar_era_fetches_calendar_once(tmp_path: Path) -> None:
    a = _seeded(tmp_path)
    items = list(a.list_urls(2021, 2030))
    dates = [h["date"] for _, h in items]
    assert dates == sorted(dates)
    assert min(dates) >= "2021" and max(dates) < "2027"
    assert {d[:4] for d in dates} == {"2023", "2026"}
    assert len(items) == len(set(items[i][0] for i in range(len(items))))
    # a single-year window on the calendar page filters to that year
    only = list(a.list_urls(2026, 2026))
    assert only and all(h["date"].startswith("2026") for _, h in only)


def test_list_urls_start_year_clamped_and_missing_page_raises(tmp_path: Path) -> None:
    f = PoliteFetcher(raw_dir=tmp_path, offline=True)
    _seed(f, f"{BASE}/monetarypolicy/fomchistorical1993.htm", b"<html></html>")
    a = FedAdapter(f)
    assert list(a.list_urls(1900, 1993)) == []  # clamps to 1993; empty page -> nothing
    with pytest.raises(FileNotFoundError):
        list(a.list_urls(1994, 1994))  # offline and not cached


def test_list_urls_dedups_shared_minutes_preferring_scheduled(tmp_path: Path) -> None:
    link = "<a href='/fomc/minutes/20000202.htm'>Minutes</a> (Released March 23, 2000)"
    html = (
        "<div class='panel'><h5>January 5 Conference Call - 2000</h5>" + link + "</div>"
        "<div class='panel'><h5>February 1-2 Meeting - 2000</h5>" + link + "</div>"
    ).encode()
    f = PoliteFetcher(raw_dir=tmp_path, offline=True)
    _seed(f, f"{BASE}/monetarypolicy/fomchistorical2000.htm", html)
    ((url, hints),) = FedAdapter(f).list_urls(2000, 2000)
    assert url.endswith("/fomc/minutes/20000202.htm")
    assert hints["date"] == "2000-02-02" and "unscheduled" not in hints


@pytest.mark.network
def test_live_smoke(tmp_path: Path) -> None:
    f = PoliteFetcher(raw_dir=tmp_path)
    a = FedAdapter(f)
    url = f"{BASE}/newsevents/pressreleases/monetary20130918a.htm"
    raw = f.get("fed", url)
    docs = a.parse(raw, {"doc_type": "statement", "date": "2013-09-18", "language": "en"})
    assert docs and "Federal Open Market Committee" in docs[0].text
