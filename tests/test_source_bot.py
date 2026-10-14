"""Offline tests for the Bank of Thailand adapter (fixtures are trimmed real pages / PDF text)."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from cbtone.schema import Document
from cbtone.sources.base import PoliteFetcher, RawResponse
from cbtone.sources.bot import (
    BASE,
    BoTAdapter,
    minutes_sections,
    parse_date,
    parse_schedule,
    pdf_pages,
    release_time,
)

FIX = Path(__file__).parent / "fixtures" / "bot"
BOILERPLATE = [
    "Contact for more information",
    "สอบถามเพิ่มเติม",
    "MPSO@bot.or.th",
    "Related Tag",
    "Skip to main",
    "Our use of cookies",
    "Publication Date",
]


def _adapter(tmp_path: Path) -> BoTAdapter:
    return BoTAdapter(PoliteFetcher(raw_dir=tmp_path, offline=True))


def _raw(content: bytes, url: str = f"{BASE}/x", ctype: str = "text/html") -> RawResponse:
    return RawResponse(
        url=url,
        content=content,
        content_type=ctype,
        sha256="ab" * 32,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        from_cache=True,
    )


def _hints(doc_type: str, iso: str, lang: str) -> dict[str, str]:
    return {
        "doc_type": doc_type,
        "date": iso,
        "language": lang,
        "parallel_id": f"bot:{iso}:{doc_type}",
    }


def _statement(tmp_path: Path, name: str, iso: str, lang: str) -> Document:
    raw = _raw((FIX / f"{name}.html").read_bytes(), f"{BASE}/{lang}/news/{name}.html")
    docs = _adapter(tmp_path).parse(raw, _hints("statement", iso, lang))
    assert len(docs) == 1
    return docs[0]


def _check_common(doc: Document, lang: str, iso: str) -> None:
    assert doc.bank == "bot" and doc.language == lang and doc.date == date.fromisoformat(iso)
    assert doc.parallel_id == f"bot:{iso}:{doc.doc_type}"
    assert len(doc.sections) >= 3
    assert doc.text == "\n\n".join(s.text for s in doc.sections)
    for bad in BOILERPLATE:
        assert bad not in doc.text
    assert doc.sha256 == "ab" * 32 and doc.fetched_at.year == 2026


@pytest.mark.parametrize(
    ("name", "iso", "lang", "title", "sentence", "min_words"),
    [
        (
            "statement_2021_1_en",
            "2021-02-03",
            "en",
            "Monetary Policy Committee\u2019s Decision 1/2021",
            "The Committee voted unanimously to maintain the policy rate at 0.50 percent",
            200,
        ),
        (
            "statement_2021_1_th",
            "2021-02-03",
            "th",
            "ผลการประชุมคณะกรรมการนโยบายการเงิน ครั้งที่ 1/2564",
            "คณะกรรมการฯ มีมติเป็นเอกฉันท์ ให้คงอัตราดอกเบี้ยนโยบายไว้ที่ร้อยละ 0.50 ต่อปี",
            50,
        ),
        (
            "statement_2025_3_en",
            "2025-06-25",
            "en",
            "Monetary Policy Committee\u2019s Decision 3/2025",
            "The Committee voted 6 to 1 to maintain the policy rate at 1.75 percent",
            200,
        ),
        (
            "statement_2025_3_th",
            "2025-06-25",
            "th",
            "ผลการประชุมคณะกรรมการนโยบายการเงิน ครั้งที่ 3/2568",
            "คณะกรรมการฯ มีมติ 6 ต่อ 1 เสียง ให้คงอัตราดอกเบี้ยนโยบายไว้ที่ร้อยละ 1.75 ต่อปี",
            50,
        ),
        (
            "statement_2026_4_en",
            "2026-08-26",
            "en",
            "Monetary Policy Committee\u2019s Decision 4/2026",
            "The Committee voted unanimously to maintain the policy rate at 1.00 percent",
            200,
        ),
        (
            "statement_2026_4_th",
            "2026-08-26",
            "th",
            "ผลการประชุมคณะกรรมการนโยบายการเงิน ครั้งที่ 4/2569",
            "คณะกรรมการฯ มีมติเป็นเอกฉันท์ให้คงอัตราดอกเบี้ยนโยบายไว้ที่ร้อยละ 1.00 ต่อปี",
            50,
        ),
    ],
)
def test_statement(
    tmp_path: Path, name: str, iso: str, lang: str, title: str, sentence: str, min_words: int
) -> None:
    doc = _statement(tmp_path, name, iso, lang)
    _check_common(doc, lang, iso)
    assert doc.doc_type == "statement" and doc.title == title
    assert len(doc.text.split()) >= min_words
    assert any(sentence in s.text for s in doc.sections)
    # 14:00 Asia/Bangkok (UTC+7) = 07:00 UTC on the decision date
    assert doc.published_at_utc == datetime(*date.fromisoformat(iso).timetuple()[:3], 7, tzinfo=UTC)
    # the sign-off ("Bank of Thailand" + date) is dropped
    assert not any(s.text in {"Bank of Thailand", "ธนาคารแห่งประเทศไทย"} for s in doc.sections)


def test_statement_footnote_section(tmp_path: Path) -> None:
    doc = _statement(tmp_path, "statement_2025_3_en", "2025-06-25", "en")
    notes = [s for s in doc.sections if s.heading == "Footnotes"]
    assert len(notes) == 1 and notes[0].text.startswith("1 Under the assumption")
    assert all(s.heading is None for s in doc.sections if s.heading != "Footnotes")
    th = _statement(tmp_path, "statement_2025_3_th", "2025-06-25", "th")
    assert [s.heading for s in th.sections if s.heading] == ["เชิงอรรถ"]
    old = _statement(tmp_path, "statement_2021_1_en", "2021-02-03", "en")
    assert all(s.heading is None for s in old.sections)  # no footnotes in the 2021 layout


def test_statement_date_falls_back_to_signoff(tmp_path: Path) -> None:
    raw = _raw((FIX / "statement_2026_4_th.html").read_bytes())
    docs = _adapter(tmp_path).parse(raw, {"doc_type": "statement", "language": "th"})
    assert docs[0].date == date(2026, 8, 26)  # "26 สิงหาคม 2569" (Buddhist year 2569)
    raw_en = _raw((FIX / "statement_2021_1_en.html").read_bytes())
    docs = _adapter(tmp_path).parse(raw_en, {"doc_type": "statement", "language": "en"})
    assert docs[0].date == date(2021, 2, 3)


def test_statement_unparseable(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    hints = {"doc_type": "statement", "language": "en"}
    assert a.parse(_raw(b"<html><body><p>nothing</p></body></html>"), hints) == []
    page = b'<html><body><div class="cmp-text"><p>Hello there.</p></div></body></html>'
    assert a.parse(_raw(page), hints) == []  # no hint date and no sign-off date
    empty = b'<html><body><div class="cmp-text"><p>&nbsp;</p></div></body></html>'
    assert a.parse(_raw(empty), {**hints, "date": "2026-01-01"}) == []
    doc = a.parse(_raw(page), {**hints, "date": "2026-01-01", "title": "MPC 1/2026"})[0]
    assert doc.title == "MPC 1/2026"  # no <title>: fall back to the hint title


def _pages(name: str) -> list[str]:
    return (FIX / f"{name}.txt").read_text(encoding="utf-8").split("\f")


@pytest.mark.parametrize(
    ("name", "iso", "lang", "title_start", "sentence", "headings", "min_words"),
    [
        (
            "minutes_2021_1_en",
            "2021-02-03",
            "en",
            "Edited Minutes of the Monetary Policy Committee Meeting (No.1/2021)",
            "The Committee voted unanimously to maintain the policy rate at 0 . 50",
            {"The Global Economy and Financial Markets", "Monetary Policy Decision"},
            1500,
        ),
        (
            "minutes_2026_4_en",
            "2026-08-26",
            "en",
            "Edited Minutes of Monetary Policy Committee Meeting (No. 4/2026)",
            "The Committee voted unanimously to maintain the policy rate",
            {"Economic and Inflation Assessment", "Monetary Policy Decision"},
            1500,
        ),
        (
            "minutes_2569_4_th",
            "2026-08-26",
            "th",
            "รายงานการประชุมคณะกรรมการนโยบายการเงิน (ฉบับย่อ) ครั้งที่ 4/2569",
            "คณะกรรมการฯ เห็นควรให้คงอัตราดอกเบี้ยนโยบายในการประชุมครั้งนี้",
            {"การประเมินภาพเศรษฐกิจและเงินเฟ้อ"},
            300,
        ),
    ],
)
def test_minutes(
    tmp_path: Path,
    name: str,
    iso: str,
    lang: str,
    title_start: str,
    sentence: str,
    headings: set[str],
    min_words: int,
) -> None:
    raw = _raw(b"%PDF", f"{BASE}/content/dam/{name}.pdf", "application/pdf")
    docs = _adapter(tmp_path)._parse_minutes(_pages(name), raw, _hints("minutes", iso, lang))
    assert len(docs) == 1
    doc = docs[0]
    _check_common(doc, lang, iso)
    assert doc.doc_type == "minutes" and doc.title.startswith(title_start)
    assert doc.published_at_utc is None  # minutes only carry a publication date
    assert len(doc.text.split()) >= min_words
    assert len(doc.sections) >= 10
    assert any(sentence in s.text for s in doc.sections)
    assert headings <= {s.heading for s in doc.sections}
    # page numbers, sign-off, annex charts and the members list are not content
    for bad in ("-1-", "-2-", "Monetary Policy Group", "สายนโยบายการเงิน", "Members", "Key Issues"):
        assert bad not in doc.text
    assert "Chairman" not in doc.text and "(ประธาน)" not in doc.text


def test_minutes_footnotes_and_page_breaks() -> None:
    _, sections = minutes_sections(_pages("minutes_2021_1_en"))
    text = "\n".join(s.text for s in sections)
    assert "This was due to (1)" not in text  # "2/ ..." footnote dropped
    assert any("Additional fiscal measures should be expedited" in s.text for s in sections)
    _, sections26 = minutes_sections(_pages("minutes_2026_4_en"))
    assert not any("Business Sentiment Index Special Survey" in s.text for s in sections26)
    # a paragraph interrupted by a page-bottom footnote continues after it as one section
    assert any(
        s.text.startswith("The Thai baht against the U.S. dollar") and "factors in recent" in s.text
        for s in sections26
    )


def test_minutes_sections_empty() -> None:
    assert minutes_sections([]) == ("", [])
    assert minutes_sections(["\n \n-1-\n"]) == ("", [])


def _tiny_pdf(lines: list[str]) -> bytes:
    """A one-page PDF with a standard (non-embedded) font, one text line per entry."""
    stream = "BT /F1 10 Tf 12 TL 40 760 Td " + " T* ".join(f"({ln}) Tj" for ln in lines) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def test_parse_pdf_branch(tmp_path: Path) -> None:
    long = "The Committee assessed that the economy would expand at a steady pace in the year"
    lines = [
        "Edited Minutes of the Monetary Policy Committee Meeting (No.2/2022)",
        "30 March 2022, Bank of Thailand",
        "Publication Date: 13 April 2022",
        "Members Present",
        "A B (Chairman), C D (Vice Chairman), E F, G H, I J, K L, M N, O P and Q R, S T U V W X Y",
        "S T",
        "Economic Assessment",
        long,
        "ahead, supported by exports.",
        "Monetary Policy Group",
        "13 April 2022",
    ]
    content = _tiny_pdf(lines)
    assert pdf_pages(content)[0].startswith("Edited Minutes")
    raw = _raw(content, f"{BASE}/m.pdf", "application/pdf")
    docs = _adapter(tmp_path).parse(raw, _hints("minutes", "2022-03-30", "en"))
    assert len(docs) == 1
    assert docs[0].sections[0].heading == "Economic Assessment"
    assert docs[0].text == long + " ahead, supported by exports."


def test_minutes_file_of_another_meeting_is_rejected(tmp_path: Path) -> None:
    # BoT's Thai "2564_1" minutes URL served the 1/2567 (2024) minutes when probed (see docs).
    pdf = (FIX / "minutes_2564_1_th.pdf").read_bytes()
    pages = pdf_pages(pdf)
    assert "ครั้งที่ 1/2567" in pages[0]
    raw = _raw(pdf, f"{BASE}/MPC_Minutes_2564_1.pdf", "application/pdf")
    a = _adapter(tmp_path)
    assert a.parse(raw, _hints("minutes", "2021-02-03", "th")) == []
    docs = a.parse(raw, _hints("minutes", "2024-02-07", "th"))  # same file, right meeting
    assert len(docs) == 1 and docs[0].date == date(2024, 2, 7) and docs[0].language == "th"


def test_parse_date() -> None:
    assert parse_date("Wed. 25 Feb. 2026") == date(2026, 2, 25)
    assert parse_date("Wed. 24 Jun. 2026") == date(2026, 6, 24)
    assert parse_date("Wed. 27 Sep. 2023") == date(2023, 9, 27)
    assert parse_date("พุธที่ 25 ก.พ. 2569") == date(2026, 2, 25)
    assert parse_date("พุธที่ 29 มี.ค. 2566") == date(2023, 3, 29)
    assert parse_date("26 สิงหาคม 2569") == date(2026, 8, 26)
    assert parse_date("31 February 2026") is None
    assert parse_date("Foo 12 Xyz 2026, then 3 May 2025") == date(2025, 5, 3)
    assert parse_date("no date here") is None


def test_release_time_rule() -> None:
    # Asia/Bangkok is UTC+7 all year (no DST): 14:00 local = 07:00 UTC
    for d in (date(2021, 2, 3), date(2023, 6, 28), date(2026, 8, 26)):
        t = release_time(d)
        assert (t.hour, t.minute, t.date()) == (7, 0, d)


def _schedule(lang: str) -> list[dict[str, str]]:
    return list(parse_schedule((FIX / f"schedule_{lang}.html").read_bytes()))


def test_parse_schedule() -> None:
    en, th = _schedule("en"), _schedule("th")
    assert [r["date"] for r in en] == [r["date"] for r in th]  # same meetings, same order
    by_date = {r["date"]: r for r in en}
    # 2026: only the four meetings that already happened (future rows have no links)
    assert [d for d in by_date if d.startswith("2026")] == [
        "2026-02-25",
        "2026-04-29",
        "2026-06-24",
        "2026-08-26",
    ]
    assert len([d for d in by_date if d.startswith("2025")]) == 6
    assert len([d for d in by_date if d.startswith("2021")]) == 8  # incl. two extra meetings
    r = by_date["2026-08-26"]
    assert r["meeting_no"] == "4"
    assert r["statement_url"] == f"{BASE}/en/news-and-media/news/mpc/news-20260826-KsecaE98.html"
    assert r["minutes_url"].endswith("/minutes-mpc/mpc-minutes-2026-4.pdf")
    assert "mpr" not in r["minutes_url"].lower()
    t = {r["date"]: r for r in th}["2026-08-26"]
    assert t["statement_url"].startswith(f"{BASE}/th/") and t["minutes_url"].endswith("2569-4.pdf")
    old = by_date["2021-02-03"]
    assert old["statement_url"].endswith("/en/news-and-media/news/news-20210203.html")
    assert old["minutes_url"].endswith("/edited-minutes/MPC_Minutes_2021_1.pdf")


def _seed(f: PoliteFetcher, url: str, fixture: str) -> None:
    body, meta = f._paths("bot", url)
    body.parent.mkdir(parents=True, exist_ok=True)
    body.write_bytes((FIX / fixture).read_bytes())
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


def _seeded_fetcher(tmp_path: Path) -> PoliteFetcher:
    f = PoliteFetcher(raw_dir=tmp_path, offline=True)
    for lang in ("en", "th"):
        _seed(
            f, f"{BASE}/{lang}/our-roles/monetary-policy/mpc-meeting.html", f"schedule_{lang}.html"
        )
    return f


def test_list_urls_offline(tmp_path: Path) -> None:
    a = BoTAdapter(_seeded_fetcher(tmp_path))
    items = list(a.list_urls(2025, 2026))
    assert len(items) == (6 + 4) * 2 * 2  # meetings x {statement, minutes} x {en, th}
    assert [h["date"] for _, h in items] == sorted(h["date"] for _, h in items)
    assert {h["date"][:4] for _, h in items} == {"2025", "2026"}
    by_pid: dict[str, set[str]] = {}
    for url, h in items:
        assert url.startswith(f"{BASE}/{h['language']}/") or url.startswith(f"{BASE}/content/dam/")
        assert h["language"] in {"en", "th"} and h["doc_type"] in {"statement", "minutes"}
        assert h["parallel_id"] == f"bot:{h['date']}:{h['doc_type']}"
        by_pid.setdefault(h["parallel_id"], set()).add(h["language"])
    assert all(langs == {"en", "th"} for langs in by_pid.values())  # every doc has both languages
    first = items[0][1]
    assert first["title"] == "MPC 1/2025" and first["meeting_no"] == "1"
    assert next(iter(a.list_urls(2021, 2021)))[1]["date"] == "2021-02-03"
    assert list(a.list_urls(2010, 2020)) == []  # nothing listed before 2021


def test_fetch_uses_cache_and_pairs_languages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = _seeded_fetcher(tmp_path)
    for lang in ("en", "th"):
        url = f"{BASE}/{lang}/news-and-media/news/mpc/news-20260826-KsecaE98.html"
        _seed(f, url, f"statement_2026_4_{lang}.html")
    a = BoTAdapter(f)
    only_aug = [
        (u, h)
        for u, h in a.list_urls(2026, 2026)
        if h["date"] == "2026-08-26" and h["doc_type"] == "statement"
    ]
    assert len(only_aug) == 2
    monkeypatch.setattr(a, "list_urls", lambda s, e: iter(only_aug))
    docs = list(a.fetch(2026, 2026))
    assert {(d.language, d.doc_type) for d in docs} == {("en", "statement"), ("th", "statement")}
    assert {d.parallel_id for d in docs} == {"bot:2026-08-26:statement"}
    assert all(d.url.startswith(BASE) for d in docs)


@pytest.mark.network
def test_live_smoke(tmp_path: Path) -> None:
    f = PoliteFetcher(raw_dir=tmp_path)
    a = BoTAdapter(f)
    url = f"{BASE}/en/news-and-media/news/news-20210203.html"
    docs = a.parse(f.get("bot", url), _hints("statement", "2021-02-03", "en"))
    assert docs and "0.50 percent" in docs[0].text
