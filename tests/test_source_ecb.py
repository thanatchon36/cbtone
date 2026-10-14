"""Offline tests for the ECB adapter (fixtures are trimmed real pages)."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from cbtone.schema import Document
from cbtone.sources.base import PoliteFetcher, RawResponse
from cbtone.sources.ecb import BASE, EcbAdapter, release_time

FIX = Path(__file__).parent / "fixtures" / "ecb"
BOILERPLATE = ["Share", "Last Update", "Skip to main", "Jump to the transcript", "PRESS RELEASE"]


def _adapter(tmp_path: Path) -> EcbAdapter:
    return EcbAdapter(PoliteFetcher(raw_dir=tmp_path, offline=True))


def _parse(tmp_path: Path, name: str, doc_type: str, iso: str) -> Document:
    raw = RawResponse(
        url=f"{BASE}/x/{name}.en.html",
        content=(FIX / f"{name}.html").read_bytes(),
        content_type="text/html",
        sha256="ab" * 32,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        from_cache=True,
    )
    docs = _adapter(tmp_path).parse(raw, {"doc_type": doc_type, "date": iso, "language": "en"})
    assert len(docs) == 1
    return docs[0]


def _check_common(doc: Document, min_words: int) -> None:
    assert doc.bank == "ecb" and doc.language == "en"
    assert len(doc.text.split()) >= min_words
    assert len(doc.sections) >= 3
    assert doc.text == "\n\n".join(s.text for s in doc.sections)
    for bad in BOILERPLATE:
        assert bad not in doc.text
    assert doc.sha256 == "ab" * 32 and doc.fetched_at.year == 2026


@pytest.mark.parametrize(
    ("name", "iso", "sentence", "utc_hhmm"),
    [
        ("statement_1999", "1999-12-02", "will remain unchanged at 3.0%, 4.0% and 2.0%", "12:45"),
        (
            "statement_2023",
            "2023-12-14",
            "keep the three key ECB interest rates unchanged",
            "13:15",
        ),
    ],
)
def test_statement(tmp_path: Path, name: str, iso: str, sentence: str, utc_hhmm: str) -> None:
    doc = _parse(tmp_path, name, "statement", iso)
    assert doc.doc_type == "statement" and doc.date == date.fromisoformat(iso)
    assert doc.title == "Monetary policy decisions"
    assert doc.published_at_utc is not None
    assert doc.published_at_utc.strftime("%H:%M") == utc_hhmm
    assert sentence in doc.text
    assert all(s.heading != "Q&A" for s in doc.sections)
    if name == "statement_1999":
        assert len(doc.sections) >= 3
        assert len(doc.text.split()) >= 50
    else:
        _check_common(doc, 300)
        assert doc.sections[-1].text.startswith("The President of the ECB will comment")
        assert "Key ECB interest rates" in {s.heading for s in doc.sections}


@pytest.mark.parametrize(
    ("name", "iso", "intro_sentence", "min_qa", "utc_hhmm"),
    [
        ("pc_1999", "1999-12-02", "report on the outcome of", 10, "13:30"),
        ("pc_2004", "2004-12-02", "outcome of today", 10, "13:30"),
        ("pc_2020", "2020-12-10", "welcome you to our press conference", 10, "13:30"),
        ("pc_2023", "2023-12-14", "Good afternoon, the Vice-President and I welcome", 10, "13:45"),
    ],
)
def test_press_conference(
    tmp_path: Path, name: str, iso: str, intro_sentence: str, min_qa: int, utc_hhmm: str
) -> None:
    doc = _parse(tmp_path, name, "press_conference", iso)
    _check_common(doc, 1500)
    assert doc.doc_type == "press_conference" and doc.date == date.fromisoformat(iso)
    assert doc.published_at_utc is not None
    assert doc.published_at_utc.strftime("%H:%M") == utc_hhmm
    qa = [s for s in doc.sections if s.heading == "Q&A"]
    intro = [s for s in doc.sections if s.heading != "Q&A"]
    assert len(qa) >= min_qa and len(intro) >= 5
    # intro first, Q&A strictly afterwards, and the intro does not leak into Q&A
    assert doc.sections[: len(intro)] == intro
    assert any(intro_sentence in s.text for s in intro)
    assert not any(intro_sentence in s.text for s in qa)


def test_press_conference_2023_headings(tmp_path: Path) -> None:
    doc = _parse(tmp_path, "pc_2023", "press_conference", "2023-12-14")
    headings = {s.heading for s in doc.sections}
    assert {"Economic activity", "Inflation", "Risk assessment", "Q&A"} <= headings
    assert doc.sections[0].heading is None


def test_pc_2004_transcript_in_appendix(tmp_path: Path) -> None:
    doc = _parse(tmp_path, "pc_2004", "press_conference", "2004-12-02")
    assert any(s.text.startswith("Question:") for s in doc.sections if s.heading == "Q&A")
    assert not any(s.text.startswith("Question:") for s in doc.sections if s.heading != "Q&A")


def test_release_time_rule() -> None:
    def hm(dt: datetime) -> str:
        return dt.astimezone(UTC).strftime("%H:%M")

    # winter, pre-2022: 13:45 / 14:30 CET = 12:45 / 13:30 UTC
    assert hm(release_time("statement", date(2016, 3, 10))) == "12:45"
    assert hm(release_time("press_conference", date(2016, 3, 10))) == "13:30"
    # summer, pre-2022 (CEST): 13:45 / 14:30 local = 11:45 / 12:30 UTC
    assert hm(release_time("statement", date(2019, 7, 25))) == "11:45"
    # last old-time day vs first new-time day (21 July 2022, CEST)
    assert hm(release_time("statement", date(2022, 7, 21))) == "12:15"
    assert hm(release_time("press_conference", date(2022, 7, 21))) == "12:45"
    assert hm(release_time("statement", date(2022, 6, 9))) == "11:45"


def _seed(f: PoliteFetcher, url: str, fixture: str) -> None:
    body, meta = f._paths("ecb", url)
    body.parent.mkdir(parents=True, exist_ok=True)
    content = (FIX / fixture).read_bytes()
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


def test_list_urls_offline(tmp_path: Path) -> None:
    f = PoliteFetcher(raw_dir=tmp_path, offline=True)
    for year in (1999, 2023):
        _seed(
            f,
            f"{BASE}/press/pressconf/{year}/html/index_include.en.html",
            f"pressconf_index_{year}.html",
        )
        _seed(f, f"{BASE}/press/pr/date/{year}/html/index_include.en.html", f"pr_index_{year}.html")
    a = EcbAdapter(f)
    items = list(a.list_urls(1990, 1999)) + list(a.list_urls(2023, 2023))  # 1990 clamps to 1999
    by_year: dict[str, list[tuple[str, dict[str, str]]]] = {"1999": [], "2023": []}
    for url, hints in items:
        by_year[hints["date"][:4]].append((url, hints))
        assert url.startswith(BASE) and url.endswith(".en.html") and "?" not in url
        assert hints["language"] == "en" and hints["doc_type"] in {"statement", "press_conference"}
    stmts99 = [h["date"] for _, h in by_year["1999"] if h["doc_type"] == "statement"]
    pcs99 = [h for _, h in by_year["1999"] if h["doc_type"] == "press_conference"]
    assert stmts99 == [
        "1999-02-18",
        "1999-11-18",
        "1999-12-02",
    ]  # incl. "Decisions on ECB interest rates"
    assert len(pcs99) == 11
    urls23 = {h["doc_type"] + h["date"]: u for u, h in by_year["2023"]}
    assert set(urls23) == {
        "statement2023-10-26",
        "statement2023-12-14",
        "press_conference2023-10-26",
        "press_conference2023-12-14",
    }
    assert (
        "/press_conference/monetary-policy-statement/2023/" in urls23["press_conference2023-12-14"]
    )
    assert "/ecb.mp231214~" in urls23["statement2023-12-14"]
    # the dated list is sorted and nothing but the two doc types leaks through (no PDFs/podcasts)
    assert [h["date"] for _, h in by_year["2023"]] == sorted(h["date"] for _, h in by_year["2023"])


def test_crawl_delay_applied(tmp_path: Path) -> None:
    f = PoliteFetcher(raw_dir=tmp_path, offline=True, min_interval_s=2.0)
    EcbAdapter(f)
    assert f.min_interval_s >= 5.0


@pytest.mark.network
def test_live_smoke(tmp_path: Path) -> None:
    f = PoliteFetcher(raw_dir=tmp_path)
    a = EcbAdapter(f)
    url = f"{BASE}/press/pr/date/1999/html/pr991202.en.html"
    raw = f.get("ecb", url)
    docs = a.parse(raw, {"doc_type": "statement", "date": "1999-12-02", "language": "en"})
    assert docs and "3.0%" in docs[0].text
