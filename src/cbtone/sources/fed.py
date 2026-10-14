"""Federal Reserve (FOMC) source adapter.

Document types
    * ``statement``: FOMC policy statement / press release (1994 onwards; the 1994-1998
      pages are the short "Chairman announced today ..." notices, the full-length
      statement format begins in 1999).
    * ``minutes``: Minutes of the FOMC meeting (1993 onwards; released ~3 weeks after the
      meeting since 2005, ~6 weeks before that).
    * ``press_conference``: Chair's press-conference transcript, PDF (April 2011 onwards).
      The introductory statement is labelled ``heading="Introductory statement"`` and
      everything after the first non-Chair speaker ``heading="Q&A"``.

Index pages (all fetched via ``self.fetcher``)
    * ``https://www.federalreserve.gov/monetarypolicy/fomchistoricalYYYY.htm`` for
      meeting years <= 2020 (one page per year, one ``div.panel`` per meeting or
      conference call; the ``<h5>`` heading, e.g. ``June 30-July 1 Meeting - 1998``,
      is the authoritative meeting date: the *last* day of the meeting).
    * ``https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm`` for 2021 onwards
      (one ``div.fomc-meeting`` row per meeting).

Document URL patterns (layout eras)
    * 1994-1997 statements: ``/fomc/YYYYMMDDdefault.htm`` (``...DEFAULT.htm`` in 1996/97);
      table-less legacy HTML.
    * 1998-2005 statements: ``/boarddocs/press/{general|monetary}/YYYY/YYYYMMDD/[default.htm]``.
    * 2006-2012 statements: ``/newsevents/press/monetary/YYYYMMDD[a-z].htm`` (modern site
      template, uppercase ``<P>`` tags).
    * 2013 onwards statements: ``/newsevents/pressreleases/monetaryYYYYMMDD[a-z].htm``.
    * Minutes: ``/fomc/MINUTES/YYYY/YYYYMMDDmin.htm`` (1993-1994),
      ``/fomc/minutes/YYYYMMDD.htm`` (1995-2007; the date is the *first* meeting day),
      ``/monetarypolicy/fomcminutesYYYYMMDD.htm`` (2008 onwards).
    * Press conferences: ``/mediacenter/files/FOMCpresconfYYYYMMDD.pdf`` (the HTML wrapper
      ``/monetarypolicy/fomcpresconfYYYYMMDD.htm`` links to it).

Language: English only.  Unscheduled meetings / conference calls are yielded with
``hints["unscheduled"] == "1"``; ``hints["released"]`` (ISO date) is set for minutes when
the index prints ``(Released ...)``.

Release times (``published_at_utc``, America/New_York via ``zoneinfo``)
    * Statements: 14:00 ET from 2013-01-01 (the Fed's own press-conference pages state
      e.g. "FOMC Meeting Statement (Released March 20, 2013 at 2:00 p.m.)",
      https://www.federalreserve.gov/monetarypolicy/fomcpresconf20130320.htm);
      14:15 ET for scheduled, non-press-conference meetings 1999-01-01..2012-12-31
      (the legacy pages' footers read e.g. "Last update: November 17, 1998, 2:15 PM";
      when a legacy page footer carries a time and its date equals the page's
      "Release Date", that footer time is used directly).  On press-conference days
      April 2011..2012 the statement came out around 12:30 ET (the page for 2012-04-25
      says "Released April 25, 2012 at 12:35 p.m."), so ``None`` is stored there rather
      than a guess.  Unscheduled statements and 1994-1998 statements without a footer
      time are ``None``.
    * Minutes: 14:00 ET on the printed release date (e.g. "Released April 10, 2013 at
      2:00 p.m.", "Released May 16, 2012 at 2:00 p.m.", 2003 footer "Last update:
      March 20, 2003, 2:00 PM") for releases from 2005-01-01; earlier releases use the
      footer time when present, else ``None``.
    * Press-conference transcripts: ``None`` (the PDF is posted after the event and no
      posting time is published).

Terms of use
    "Unless otherwise indicated, information on Board's website is in the public domain and
    may be copied and distributed without permission. Please cite to the Board as the source of
    the information." (https://www.federalreserve.gov/disclaimer.htm; linked from the footer
    "Website Policies" page, https://www.federalreserve.gov/website-linking-policies.htm).
    Details in ``docs/sources/fed.md``.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Comment, Tag
from bs4.element import NavigableString
from pypdf import PdfReader

from cbtone.schema import DocType, Document, Section
from cbtone.sources.base import RawResponse, SourceAdapter

BASE = "https://www.federalreserve.gov"
CALENDAR_URL = f"{BASE}/monetarypolicy/fomccalendars.htm"
CALENDAR_FIRST_YEAR = 2021
FIRST_YEAR = 1993
NY = ZoneInfo("America/New_York")

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
    )
}

_STATEMENT_RE = re.compile(
    r"^(?:/fomc/\d{8}default\.htm"
    r"|/boarddocs/press/(?:general|monetary)/\d{4}/\d{8}/(?:default\.htm)?"
    r"|/newsevents/press/monetary/\d{8}[a-z]\.htm"
    r"|/newsevents/pressreleases/monetary\d{8}[a-z]\.htm)$",
    re.I,
)
_MINUTES_RE = re.compile(
    r"^(?:/fomc/minutes/\d{8}\.htm|/fomc/minutes/\d{4}/\d{8}min\.htm"
    r"|/monetarypolicy/fomcminutes\d{8}\.htm)$",
    re.I,
)
_PRESCONF_RE = re.compile(r"^/monetarypolicy/fomcpress?conf(\d{8})\.htm$", re.I)
_HEADING_RE = re.compile(
    r"^(?P<m1>[A-Za-z]+)\s+(?P<d1>\d{1,2})(?:\s*-\s*(?:(?P<m2>[A-Za-z]+)\s+)?(?P<d2>\d{1,2}))?"
    r"\s+(?P<kind>.*?)\s*-\s*(?P<y>\d{4})$"
)
_RELEASED_RE = re.compile(r"Released\s+([A-Za-z]+)\.?\s+(\d{1,2}),\s+(\d{4})")


def _month(name: str) -> int | None:
    return _MONTHS.get(name.strip().lower()[:3])


def _norm_path(href: str) -> str:
    """Strip scheme/host and fragment so hrefs can be matched against path patterns."""
    href = href.split("#", 1)[0].strip()
    href = re.sub(r"^(?:https?:)?//www\.federalreserve\.gov", "", href)
    return href


def _url(path: str) -> str:
    return path if path.startswith("http") else BASE + path


@dataclass
class _Item:
    doc_type: DocType
    path: str
    day: date
    unscheduled: bool
    released: date | None = None
    has_presser: bool = False


# --------------------------------------------------------------------------- index parsing
def _panel_items(
    anchors: list[tuple[str, str]], panel_html: str, meeting: date | None, unscheduled: bool
) -> list[_Item]:
    """Classify the links of one meeting panel / calendar row."""
    stmt: str | None = None
    minutes: str | None = None
    presser: str | None = None
    for href, text in anchors:
        p = _norm_path(href)
        if stmt is None and text in ("Statement", "HTML") and _STATEMENT_RE.match(p):
            stmt = p
        elif minutes is None and _MINUTES_RE.match(p):
            minutes = p
        elif presser is None and _PRESCONF_RE.match(p):
            presser = p
    if meeting is None:
        # fall back to the date embedded in the first document URL
        for cand in (stmt, minutes, presser):
            if cand and (m := re.search(r"(\d{4})(\d{2})(\d{2})", cand.split("/")[-1] or cand)):
                meeting = date(int(m[1]), int(m[2]), int(m[3]))
                break
        if meeting is None:
            return []
    out: list[_Item] = []
    if stmt:
        out.append(_Item("statement", stmt, meeting, unscheduled, has_presser=presser is not None))
    if minutes:
        rel: date | None = None
        if m := _RELEASED_RE.search(re.sub(r"<[^>]+>", " ", panel_html)):
            mon = _month(m[1])
            if mon:
                rel = date(int(m[3]), mon, int(m[2]))
        out.append(_Item("minutes", minutes, meeting, unscheduled, released=rel))
    if presser:
        pdate = _PRESCONF_RE.match(presser)
        assert pdate is not None
        d = pdate[1]
        out.append(
            _Item(
                "press_conference",
                f"/mediacenter/files/FOMCpresconf{d}.pdf",
                date(int(d[:4]), int(d[4:6]), int(d[6:])),
                unscheduled,
            )
        )
    return out


def parse_historical_index(html: bytes | str) -> list[_Item]:
    """Parse ``fomchistoricalYYYY.htm`` (one ``div.panel`` per meeting / call)."""
    soup = BeautifulSoup(html, "lxml")
    items: list[_Item] = []
    for panel in soup.select("div.panel"):
        h5 = panel.find("h5")
        if not isinstance(h5, Tag):
            continue
        heading = re.sub(r"\s+", " ", h5.get_text(" ", strip=True))
        meeting: date | None = None
        unscheduled = False
        if m := _HEADING_RE.match(heading):
            end_month = _month(m["m2"] or m["m1"])
            day = int(m["d2"] or m["d1"])
            if end_month:
                meeting = date(int(m["y"]), end_month, day)
            unscheduled = m["kind"].strip().lower() != "meeting"
        anchors = [
            (str(a["href"]), a.get_text(" ", strip=True))
            for a in panel.find_all("a", href=True)
            if isinstance(a, Tag)
        ]
        items.extend(_panel_items(anchors, str(panel), meeting, unscheduled))
    return items


def parse_calendar_index(html: bytes | str) -> list[_Item]:
    """Parse ``fomccalendars.htm`` (2021 onwards; ``div.fomc-meeting`` rows under year h4s)."""
    soup = BeautifulSoup(html, "lxml")
    items: list[_Item] = []
    year: int | None = None
    for el in soup.find_all(["h4", "div"]):
        if not isinstance(el, Tag):
            continue
        if el.name == "h4":
            if m := re.match(r"(\d{4}) FOMC Meetings", el.get_text(" ", strip=True)):
                year = int(m[1])
            continue
        classes: list[str] = list(el.get("class") or [])
        if "fomc-meeting" not in classes or year is None:
            continue
        mon_el = el.select_one(".fomc-meeting__month")
        day_el = el.select_one(".fomc-meeting__date")
        if mon_el is None or day_el is None:
            continue
        month_txt = mon_el.get_text(strip=True).split("/")[-1]
        day_txt = day_el.get_text(" ", strip=True)
        dm = re.match(r"(?:\d{1,2}\s*-\s*)?(\d{1,2})", day_txt)
        mon = _month(month_txt)
        if dm is None or mon is None:
            continue
        meeting = date(year, mon, int(dm[1]))
        anchors = [
            (str(a["href"]), a.get_text(" ", strip=True))
            for a in el.find_all("a", href=True)
            if isinstance(a, Tag)
        ]
        items.extend(_panel_items(anchors, str(el), meeting, "notation" in day_txt.lower()))
    return items


# --------------------------------------------------------------------------- release times
def _ny_to_utc(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=NY).astimezone(UTC)


def _footer_time(soup: BeautifulSoup, doc_date: date | None) -> datetime | None:
    """Legacy pages end with ``Last update: March 20, 2003, 2:00 PM``.  Only trusted when the
    footer date equals the page's own release date (``Release Date:`` line) or ``doc_date``."""
    text = soup.get_text(" ", strip=True)
    m = re.search(
        r"Last update:\s*([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4}),\s*(\d{1,2}):(\d{2})\s*([AP]M)",
        text,
        re.I,
    )
    if not m:
        return None
    mon = _month(m[1])
    if mon is None:
        return None
    d = date(int(m[3]), mon, int(m[2]))
    r = re.search(r"Release Date:\s*([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", text)
    ref = doc_date
    if r and (rm := _month(r[1])):
        ref = date(int(r[3]), rm, int(r[2]))
    if ref is None or d != ref:
        return None
    hour = int(m[4]) % 12 + (12 if m[6].upper() == "PM" else 0)
    return _ny_to_utc(d, time(hour, int(m[5])))


def statement_release(d: date, unscheduled: bool, has_presser: bool) -> datetime | None:
    """Rule-based statement release time (see module docstring)."""
    if unscheduled:
        return None
    if d >= date(2013, 1, 1):
        return _ny_to_utc(d, time(14, 0))
    if date(2011, 4, 27) <= d and has_presser:
        return None  # ~12:30 ET on press-conference days; not stored as a guess
    if d >= date(1999, 1, 1):
        return _ny_to_utc(d, time(14, 15))
    return None


def minutes_release(released: date | None) -> datetime | None:
    if released is not None and released >= date(2005, 1, 1):
        return _ny_to_utc(released, time(14, 0))
    return None


# --------------------------------------------------------------------------- HTML text
_BLOCK = {
    "p", "div", "li", "ul", "ol", "tr", "table", "tbody", "thead", "td", "th", "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6", "dd", "dt", "dl", "hr", "section", "center", "pre",
}  # fmt: skip
_SKIP = {"script", "style", "noscript", "nav", "footer", "form", "button", "svg", "head"}
_BOLD = {"b", "strong", "h1", "h2", "h3", "h4", "h5", "h6"}
_PRUNE_CLASSES = {"heading", "lastUpdate", "footnotes", "share", "article__time", "shareDL"}
_DROP_RE = re.compile(
    r"^(?:share|last update.*|return to (?:top|text)|for immediate release|release date.*"
    r"|home\s*\|.*|accessibility.*|contact us.*|for media inquiries.*"
    r"|implementation note issued.*|footnotes?|fomc|print|back to top"
    r"|\d{4} monetary policy|secretary|meeting of [A-Za-z0-9 ,\-]+"
    r"|minutes of the federal open market committee(?: meeting of .*)?"
    r"|[A-Z][a-z]+ \d{1,2}(?:\s*[-\u2013]\s*(?:[A-Z][a-z]+ )?\d{1,2})?, \d{4}"
    r"|_{5,}|FRB: .*|.*return to text.*)$",
    re.I | re.S,
)


def _pruned(tag: Tag) -> bool:
    if tag.name in _SKIP:
        return True
    classes: set[str] = set(tag.get("class") or [])
    if classes & _PRUNE_CLASSES:
        return True
    return tag.get("id") in {"lastUpdate", "top-banner"}


def _blocks(root: Tag) -> list[tuple[bool, str]]:
    """Walk ``root`` and return ``(is_heading, text)`` blocks in reading order."""
    out: list[tuple[bool, str]] = []
    buf: list[str] = []
    bold = 0
    total = 0

    def flush() -> None:
        nonlocal bold, total
        text = re.sub(r"\s+", " ", "".join(buf).replace("\xa0", " ")).strip()
        is_head = bool(text) and bold >= total > 0 and len(text) <= 150 and not text.endswith(":")
        if text:
            out.append((is_head, text))
        buf.clear()
        bold = 0
        total = 0

    def walk(node: Tag, in_bold: bool) -> None:
        nonlocal bold, total
        for child in node.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                s = str(child)
                if s.strip():
                    buf.append(s)
                    n = len(s.strip())
                    total += n
                    if in_bold:
                        bold += n
                else:
                    buf.append(" ")
                continue
            if not isinstance(child, Tag) or _pruned(child):
                continue
            if child.name == "br":
                if total > 0 and bold >= total:
                    flush()  # "<strong>Heading</strong><br>text" -> heading block
                else:
                    buf.append(" ")
                continue
            is_block = child.name in _BLOCK
            if is_block:
                flush()
            walk(child, in_bold or child.name in _BOLD)
            if is_block:
                flush()

    walk(root, False)
    flush()
    return out


def _sections(blocks: list[tuple[bool, str]]) -> list[Section]:
    sections: list[Section] = []
    heading: str | None = None
    for is_head, text in blocks:
        if _DROP_RE.match(text):
            continue
        if is_head:
            heading = text
            continue
        sections.append(Section(heading=heading, text=text))
    return sections


def _content_root(soup: BeautifulSoup) -> Tag:
    article = soup.find(id="article")
    if isinstance(article, Tag):
        return article
    return soup.body if isinstance(soup.body, Tag) else soup


# --------------------------------------------------------------------------- PDF text
_PDF_HEADER_RE = re.compile(
    r"^(?:(?:Page )?\d+ of \d+|[A-Z][a-z]+ \d{1,2}, \d{4}\s+.*Press Conference.*"
    r"|Transcript of .*Press Conference|[A-Z][a-z]+ \d{1,2}, \d{4})\s*$"
)
_SPEAKER_RE = re.compile(r"^([A-Z][A-Z'\u2019\-]*(?: [A-Z][A-Z'\u2019\-]*){0,4})\.\s")


def _pdf_paragraphs(text: str) -> list[str]:
    lines = [ln for ln in text.split("\n") if ln.strip() and not _PDF_HEADER_RE.match(ln.strip())]
    lengths = sorted(len(ln.rstrip()) for ln in lines)
    width = lengths[int(len(lengths) * 0.9)] if lengths else 0
    paras: list[str] = []
    cur: list[str] = []

    def flush() -> None:
        if cur:
            paras.append(re.sub(r"\s+", " ", " ".join(cur)).strip())
            cur.clear()

    for raw in lines:
        s = raw.strip()
        m = _SPEAKER_RE.match(s + " ")
        if m and len(m[1]) >= 5:
            flush()
        cur.append(s)
        short_end = len(s) < 0.8 * width and s[-1] in '.?!”"'
        if raw.endswith("   ") or short_end:
            flush()
    flush()
    return [p for p in paras if p]


def _pdf_sections(paras: list[str]) -> list[Section]:
    sections: list[Section] = []
    speaker: str | None = None
    phase = 0  # 0 before the Chair speaks, 1 introductory statement, 2 Q&A
    for p in paras:
        m = _SPEAKER_RE.match(p + " ")
        if m and len(m[1]) >= 5:
            speaker = m[1]
        is_chair = speaker is not None and speaker.startswith("CHAIR")
        if phase == 0 and is_chair:
            phase = 1
        elif phase == 1 and not is_chair:
            phase = 2
        heading = {0: None, 1: "Introductory statement", 2: "Q&A"}[phase]
        sections.append(Section(heading=heading, text=p))
    return sections


# --------------------------------------------------------------------------- adapter
class FedAdapter(SourceAdapter):
    """Federal Reserve FOMC statements, minutes and press-conference transcripts.

    See the module docstring for document types, index and document URL patterns per
    layout era, date coverage (statements 1994->, minutes 1993->, press conferences
    2011->), language (en), release-time rules and the terms-of-use note.
    """

    bank = "fed"

    def _items(self, start_year: int, end_year: int) -> Iterator[_Item]:
        start_year = max(start_year, FIRST_YEAR)
        calendar_done = False
        for year in range(start_year, end_year + 1):
            if year < CALENDAR_FIRST_YEAR:
                url = f"{BASE}/monetarypolicy/fomchistorical{year}.htm"
                items = parse_historical_index(self.fetcher.get(self.bank, url).content)
            elif not calendar_done:
                calendar_done = True
                items = parse_calendar_index(self.fetcher.get(self.bank, CALENDAR_URL).content)
            else:
                continue
            # the same document can be linked from several panels (e.g. the minutes of an
            # intermeeting call are appended to the next meeting's minutes): keep one,
            # preferring the scheduled meeting's panel.
            best: dict[tuple[str, str], _Item] = {}
            for it in items:
                key = (it.doc_type, it.path.lower())
                if key not in best or (best[key].unscheduled and not it.unscheduled):
                    best[key] = it
            for it in best.values():
                if start_year <= it.day.year <= end_year:
                    yield it

    def list_urls(self, start_year: int, end_year: int) -> Iterator[tuple[str, dict[str, str]]]:
        for it in sorted(self._items(start_year, end_year), key=lambda i: (i.day, i.doc_type)):
            hints = {"doc_type": it.doc_type, "date": it.day.isoformat(), "language": "en"}
            if it.unscheduled:
                hints["unscheduled"] = "1"
            if it.released:
                hints["released"] = it.released.isoformat()
            if it.has_presser:
                hints["has_presser"] = "1"
            yield _url(it.path), hints

    # -- parse ---------------------------------------------------------------
    def parse(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        doc_type: DocType = hints["doc_type"]  # type: ignore[assignment]
        d = date.fromisoformat(hints["date"])
        published: datetime | None
        if doc_type == "press_conference":
            reader = PdfReader(io.BytesIO(raw.content))
            body = "\n".join(page.extract_text() for page in reader.pages)
            sections = _pdf_sections(_pdf_paragraphs(body))
            published = None
        else:
            soup = BeautifulSoup(raw.content, "lxml")
            sections = _sections(_blocks(_content_root(soup)))
            if doc_type == "statement":
                published = _footer_time(soup, d) or statement_release(
                    d, hints.get("unscheduled") == "1", hints.get("has_presser") == "1"
                )
            else:
                released = date.fromisoformat(hints["released"]) if "released" in hints else None
                published = minutes_release(released)
                if published is None and released is not None:
                    published = _footer_time(soup, released)
        if not sections:
            return []
        text = "\n\n".join(s.text for s in sections)
        label = {
            "statement": "FOMC statement",
            "minutes": "FOMC minutes",
            "press_conference": "FOMC press conference transcript",
        }.get(doc_type, "FOMC document")
        return [
            Document(
                bank="fed",
                date=d,
                published_at_utc=published,
                doc_type=doc_type,
                language="en",
                title=f"{label}, {d.isoformat()}",
                text=text,
                sections=sections,
                url=raw.url,
                sha256=raw.sha256,
                fetched_at=raw.fetched_at,
            )
        ]


__all__ = ["FedAdapter", "parse_calendar_index", "parse_historical_index"]
