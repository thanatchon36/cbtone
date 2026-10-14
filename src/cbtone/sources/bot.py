"""Bank of Thailand (BoT) adapter (opt-in; excluded from headline results).

Document types
    * ``statement``: the Monetary Policy Committee (MPC, "กนง.") decision press release,
      titled "Monetary Policy Committee's Decision n/YYYY" (EN) /
      "ผลการประชุมคณะกรรมการนโยบายการเงิน ครั้งที่ n/YYYY" (TH), read out by the MPC secretary.
    * ``minutes``: the "Edited Minutes of the Monetary Policy Committee Meeting" (PDF), published
      about two weeks after the meeting. Sections carry the PDF's sub-headings.

Languages and pairing
    English (``en``) and Thai (``th``). A decision and its two language versions share
    ``parallel_id = "bot:<decision date>:<doc_type>"``; the pairing is by schedule row, i.e. by
    decision date, because both language schedules list the same meeting in the same row.

URL patterns
    * Index (one page per language, static HTML, one table per year, 2021 onwards):
      ``https://www.bot.or.th/{en,th}/our-roles/monetary-policy/mpc-meeting.html``. Each row:
      meeting number, decision date, "Press Release" link, "Minutes" PDF link.
    * Statement: ``/{en,th}/news-and-media/news/news-YYYYMMDD[-n].html`` (to mid-2025) or
      ``/{en,th}/news-and-media/news/mpc/news-YYYYMMDD-<hash>.html`` (from Aug 2025).
    * Minutes PDF: ``/content/dam/bot/documents/{en,th}/our-roles/monetary-policy/
      mpc-publication/edited-minutes/MPC_Minutes_<YYYY>_<n>.pdf`` (Thai file name uses the
      Buddhist year) or ``.../research-and-publications/reports/monetary-policy/minutes-mpc/
      mpc-minutes-<YYYY>-<n>.pdf``.

Date range: 2021 to present (the earliest year the static schedule page lists; BoT's older
releases have no static index, see ``docs/sources/bot.md``).

Dates and release time (``published_at_utc``; zoneinfo ``Asia/Bangkok``, UTC+7, no DST)
    ``date`` is the MPC decision date (the day of the announcement, ``Wed. 25 Feb. 2026`` in
    the schedule; Thai pages use Buddhist-era years, which the adapter converts). Statements:
    "The MPC's Decision is published at 2:00 PM on the day of the MPC Meeting. The MPC secretary
    holds the press conference at 2:30 PM" (https://www.bot.or.th/en/our-roles/monetary-policy/
    mpc-publication.html), so statements are stamped 14:00 Asia/Bangkok. Minutes carry only a
    publication *date* (a "Publication Date:" line), so their timestamp is ``None``.

Terms of use (https://www.bot.or.th/en/terms-and-condition.html)
    "BOT is pleased to allow Users to visit the Site and download and copy the information,
    documents and materials ... from the Site for User use subject to the terms and conditions
    outlined below, and also subject to more specific restrictions that may apply to specific
    material within this Site." No clause grants republication or redistribution.
    robots.txt disallows only ``/_layouts/``, ``/_vti_bin/`` and ``/_catalogs/`` and sets no
    Crawl-delay.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from datetime import time as dtime
from typing import cast
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

from cbtone.schema import DocType, Document, Language, Section
from cbtone.sources.base import RawResponse, SourceAdapter

BASE = "https://www.bot.or.th"
BANGKOK = ZoneInfo("Asia/Bangkok")
DECISION_TIME = dtime(14, 0)  # "published at 2:00 PM on the day of the MPC Meeting"
FIRST_YEAR = 2021
LANGUAGES = ("en", "th")
SCHEDULE_PATH = "/{lang}/our-roles/monetary-policy/mpc-meeting.html"

_WS = re.compile(r"\s+")
_PUA = re.compile("[\ue000-\uf8ff]")  # private-use bullet glyphs in PDF text
_DATE = re.compile(r"(\d{1,2})\s+([^\s\d]+)\s+(\d{4})")
_MEETING = re.compile(r"(\d{1,2})\s*/\s*(\d{4})")
_PAGE_NO = re.compile(r"^-\s*\d+\s*-$")
_FOOTNOTE = re.compile(r"^\d{1,2}(?:/\s|\s+[A-Z])")  # "2/ text" or "1 Text"
_PUBLISHED = re.compile(r"Publication Date|เผยแพร่ ณ วันที่")
_SIGNOFF = {"Bank of Thailand", "ธนาคารแห่งประเทศไทย"}
_MINUTES_SIGNOFF = {"Monetary Policy Group", "สายนโยบายการเงิน"}
_ATTENDEES = re.compile(r"^(Members|กรรมการที่เข้าร่วมประชุม)")
_BULLETS = ("•", "▪", "-", "\u2013")
_SENTENCE_END = (".", "!", "?", ":", ";", ",", ")")

_EN_MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec"
_TH_ABBR = "มค กพ มีค เมย พค มิย กค สค กย ตค พย ธค"
_TH_FULL = "มกราคม กุมภาพันธ์ มีนาคม เมษายน พฤษภาคม มิถุนายน กรกฎาคม สิงหาคม กันยายน ตุลาคม พฤศจิกายน ธันวาคม"
_MONTHS: dict[str, int] = {
    name: i + 1
    for names in (_EN_MONTHS, _TH_ABBR, _TH_FULL)
    for i, name in enumerate(names.split())
}


def _clean(text: str) -> str:
    text = _PUA.sub("", text.replace("\xa0", " ").replace("\u200b", ""))
    return _WS.sub(" ", text).strip()


def _is_thai(ch: str) -> bool:
    return "฀" <= ch <= "๿"


def parse_date(text: str) -> date | None:
    """First ``D Month YYYY`` in ``text`` (English or Thai month names; Buddhist years -543)."""
    for m in _DATE.finditer(text):
        token = m.group(2).replace(".", "")
        month = _MONTHS.get(token) or _MONTHS.get(token[:3].lower())
        if month is None:
            continue
        year = int(m.group(3))
        year = year - 543 if year > 2400 else year
        try:
            return date(year, month, int(m.group(1)))
        except ValueError:
            continue
    return None


def release_time(d: date) -> datetime:
    """UTC release time of an MPC decision statement (14:00 Asia/Bangkok)."""
    return datetime.combine(d, DECISION_TIME, tzinfo=BANGKOK).astimezone(UTC)


def parse_schedule(html: bytes | str) -> Iterator[dict[str, str]]:
    """Yield one dict per published meeting row of the MPC schedule page.

    Keys: ``meeting_no``, ``date`` (ISO) and optional ``statement_url`` / ``minutes_url``.
    Rows without any link (future meetings) are skipped.
    """
    soup = BeautifulSoup(html, "lxml")
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 4:
            continue
        d = parse_date(tds[1].get_text(" "))
        no = _clean(tds[0].get_text(" "))
        if d is None or not no.isdigit():
            continue
        row = {"meeting_no": no, "date": d.isoformat()}
        for a in tr.find_all("a", href=True):
            href = str(a["href"])
            low = href.lower()
            if "/news-and-media/news/" in low and "statement_url" not in row:
                row["statement_url"] = urljoin(BASE, href)
            elif low.endswith(".pdf") and "minutes" in low and "minutes_url" not in row:
                row["minutes_url"] = urljoin(BASE, href)
        if "statement_url" in row or "minutes_url" in row:
            yield row


def pdf_pages(content: bytes) -> list[str]:
    """Extract the text of each page of a PDF."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    return [page.extract_text() or "" for page in reader.pages]


def _join(prev: str, nxt: str) -> str:
    """Join two wrapped PDF lines (no space inside a Thai word; undo hyphen wrapping)."""
    if prev.endswith(" "):
        return prev + nxt
    if _is_thai(prev[-1]) and _is_thai(nxt[0]):
        return prev + nxt
    if prev.endswith("-") and len(prev) > 1 and prev[-2].isalpha() and nxt[0].islower():
        return prev + nxt
    return prev + " " + nxt


def minutes_sections(pages: list[str]) -> tuple[str, list[Section]]:
    """Title and paragraph sections of an edited-minutes PDF (given as per-page text).

    PDF text has no paragraph marks: a paragraph ends at a line clearly shorter than the usual
    line width, and a short line that starts a block (and is not a sentence) is a heading.
    Footnotes (``1/ ...``), page numbers, and everything after the sign-off line (annex
    charts) are dropped.
    """
    lines: list[str] = []
    started = False  # header (title, date, publication line) seen: footnotes only after it
    for page in pages:
        in_footnote = False
        for raw in page.split("\n"):
            line = raw.rstrip()
            s = line.strip()
            if not s or _PAGE_NO.match(s):
                continue
            started = started or bool(_PUBLISHED.search(s))
            if started and _FOOTNOTE.match(s):
                in_footnote = True
            if in_footnote:
                continue
            if s in _MINUTES_SIGNOFF:
                lines.append(s)
                break
            lines.append(line)
        else:
            continue
        break
    end = len(lines) - 1 if lines and lines[-1].strip() in _MINUTES_SIGNOFF else len(lines)
    body_lines = lines[:end]
    head_end = next((i for i, ln in enumerate(body_lines[:8]) if _PUBLISHED.search(ln)), -1)
    header = [ln.strip() for ln in body_lines[: head_end + 1]]
    body = body_lines[head_end + 1 :]
    title = header[0] if header else ""
    widths = sorted(len(ln.strip()) for ln in body)
    ref = widths[int(len(widths) * 0.9)] if widths else 0

    def ends_paragraph(text: str) -> bool:
        n = len(text)
        if any(_is_thai(c) for c in text):  # Thai has no sentence punctuation
            return n < 0.7 * ref
        return n < 0.5 * ref or (n < 0.8 * ref and text.endswith(_SENTENCE_END))

    sections: list[Section] = []
    heading: str | None = None
    cur = ""
    prev = ""
    skip_to = 0
    for i, ln in enumerate(body):
        s = ln.strip()
        if i < skip_to:
            continue
        if _ATTENDEES.match(s):  # list of attending members: not content
            j = next((k for k in range(i + 1, len(body)) if len(body[k].strip()) < 0.6 * ref), None)
            while j is not None and j + 1 < len(body) and len(body[j + 1].strip()) < 0.6 * ref:
                j += 1  # the heading is the last of the consecutive short lines
            skip_to = j if j is not None else i + 1
            continue
        heading_like = len(s) < 0.8 * ref and not s.startswith(_BULLETS)
        heading_like = heading_like and not s.endswith(_SENTENCE_END)
        if cur and heading_like and len(s) < 0.6 * ref and prev.endswith(_SENTENCE_END):
            sections.append(Section(heading=heading, text=_clean(cur)))  # heading after a
            cur = ""  # full-width last line
        if not cur and heading_like:
            heading = _clean(s)
            continue
        cur = _join(cur, ln.lstrip()) if cur else s
        prev = s
        if ends_paragraph(s):
            sections.append(Section(heading=heading, text=_clean(cur)))
            cur = ""
    if cur:
        sections.append(Section(heading=heading, text=_clean(cur)))
    return _clean(title), sections


class BoTAdapter(SourceAdapter):
    """See the module docstring for document types, URLs, eras, times and terms."""

    bank = "bot"

    # -- discovery -----------------------------------------------------------
    def list_urls(self, start_year: int, end_year: int) -> Iterator[tuple[str, dict[str, str]]]:
        found: list[tuple[str, dict[str, str]]] = []
        for lang in LANGUAGES:
            raw = self.fetcher.get(self.bank, BASE + SCHEDULE_PATH.format(lang=lang))
            for row in parse_schedule(raw.content):
                year = int(row["date"][:4])
                if not start_year <= year <= end_year:
                    continue
                for doc_type, key in (("statement", "statement_url"), ("minutes", "minutes_url")):
                    if key not in row:
                        continue
                    found.append(
                        (
                            row[key],
                            {
                                "doc_type": doc_type,
                                "date": row["date"],
                                "language": lang,
                                "parallel_id": f"bot:{row['date']}:{doc_type}",
                                "title": f"MPC {row['meeting_no']}/{year}",
                                "meeting_no": row["meeting_no"],
                            },
                        )
                    )
        yield from sorted(found, key=lambda x: (x[1]["date"], x[1]["doc_type"], x[1]["language"]))

    # -- parsing -------------------------------------------------------------
    def parse(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        if hints.get("doc_type") == "minutes":
            return self._parse_minutes(pdf_pages(raw.content), raw, hints)
        return self._parse_statement(raw, hints)

    def _document(
        self,
        raw: RawResponse,
        hints: dict[str, str],
        d: date,
        title: str,
        sections: list[Section],
        published: datetime | None,
    ) -> list[Document]:
        if not sections:
            return []
        return [
            Document(
                bank="bot",
                date=d,
                published_at_utc=published,
                doc_type=cast(DocType, hints["doc_type"]),
                language=cast(Language, hints["language"]),
                parallel_id=hints.get("parallel_id"),
                title=title,
                text="\n\n".join(s.text for s in sections),
                sections=sections,
                url=raw.url,
                sha256=raw.sha256,
                fetched_at=raw.fetched_at,
            )
        ]

    def _parse_statement(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        soup = BeautifulSoup(raw.content, "lxml")
        bodies = [e for e in soup.select("div.cmp-text") if isinstance(e, Tag)]
        if not bodies:
            return []
        body = max(bodies, key=lambda e: len(e.get_text()))
        sections: list[Section] = []
        heading: str | None = None
        signoff_date: date | None = None
        expect_date = False
        for el in body.find_all(["p", "h2", "h3", "h4"]):
            text = _clean(el.get_text(" "))
            if not text:
                continue
            if el.name != "p":
                heading = text
            elif text in _SIGNOFF:
                expect_date = True
                heading = "Footnotes" if hints.get("language") == "en" else "เชิงอรรถ"
            elif expect_date:
                expect_date = False
                signoff_date = parse_date(text)
                if signoff_date is None:  # not a date line: ordinary footnote text
                    sections.append(Section(heading=heading, text=text))
            else:
                sections.append(Section(heading=heading, text=text))
        d = date.fromisoformat(hints["date"]) if hints.get("date") else signoff_date
        if d is None:
            return []
        title_el = soup.find("title")
        title = _clean(title_el.get_text(" ")) if title_el else hints.get("title", "")
        return self._document(raw, hints, d, title, sections, release_time(d))

    def _parse_minutes(
        self, pages: list[str], raw: RawResponse, hints: dict[str, str]
    ) -> list[Document]:
        title, sections = minutes_sections(pages)
        d = date.fromisoformat(hints["date"])
        m = _MEETING.search(title)
        if m:  # guard against a file that belongs to another meeting (see docs/sources/bot.md)
            year = int(m.group(2))
            year = year - 543 if year > 2400 else year
            if year != d.year:
                return []
        return self._document(raw, hints, d, title or hints.get("title", ""), sections, None)
