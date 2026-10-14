"""Bank of England (BoE) adapter: Monetary Policy Committee decisions and minutes.

Document types
    * ``statement``: the MPC decision. 2000-Jul 2015: the "Bank of England maintains Bank
      Rate at ..." press release; Aug 2015 onwards: the "Monetary Policy Summary" (the
      summary and the minutes were merged into one publication from the August 2015
      meeting, published together).
    * ``minutes``: MPC minutes. 1997-Jul 2015: stand-alone minutes published about two
      weeks after the decision; Aug 2015 onwards: the "Minutes of the Monetary Policy
      Committee meeting ending on ..." section of the combined publication. From about
      2022 the HTML page carries both parts (split here into one ``statement`` and one
      ``minutes`` Document from the same URL); in earlier eras the HTML page holds only
      the summary (or a stub with the vote) and the full minutes are in a PDF linked from
      the page, which is what ``list_urls`` yields for them.

URL patterns (English only; ``language="en"``)
    * Index: the site map ``https://www.bankofengland.co.uk/_api/sitemap/getsitemap``
      (named in robots.txt; the site has no static year list). Entries are filtered by path.
    * Statement press release 2000-Jul 2015: ``/news/YYYY/<month>/mpc-<month>-YYYY``.
    * Minutes 1997-Jul 2015: ``/minutes/YYYY/monetary-policy-committee-<month>-YYYY`` or
      ``/minutes/YYYY/minutes-<month>-YYYY`` (PDF under ``/-/media/boe/files/minutes/``).
    * Summary and minutes Aug 2015 onwards:
      ``/monetary-policy-summary-and-minutes/YYYY/<mpc-><month>-YYYY`` (PDF under
      ``/-/media/boe/files/monetary-policy-summary-and-minutes/YYYY/``).
    Future meetings already have placeholder pages ("to be published ..."); they are skipped.

Date range: minutes June 1997 to present; decision press releases Jan 2000 to present
(1997-1999 decisions have no stand-alone release page).

Dates: ``statement`` date is the announcement date ("Published on"). ``minutes`` date is the
last day of the meeting they cover (title "held on 7 and 8 April 1999", "meeting ending
3 June 2015"), which since 2015 is the day before the announcement. ``list_urls`` fetches the
page of every candidate (cached, so ``fetch`` does not re-request it) to read these dates.

Release-time rule (``published_at_utc``; zoneinfo ``Europe/London``)
    * ``statement``: 12:00 on the announcement date. Source: press release of 1 August 2013
      ("the decision will still be announced at the originally scheduled time of 12.00")
      and the BoE placeholder titles "(to be published at 12pm)"; assumed unchanged for
      2000-2012.
    * ``minutes`` published before 6 Aug 2015: 09:30 on the publication date. Source: the
      press releases of 1 Aug 2013 and 9 Jul 2015 ("The minutes of the meeting will be
      published at 9.30am on Wednesday ...").
    * ``minutes`` of the combined publication (from 6 Aug 2015): 12:00, with the summary.
    * Pages titled or named "special" (emergency meetings in March 2020): ``None``.

PDF caveat: some recent PDFs use AES-256 encryption, which ``pypdf`` can read only with the
optional ``cryptography`` package. Without it ``parse`` logs a warning and returns ``[]`` for
those minutes (the HTML summary is unaffected).

Terms of use (https://www.bankofengland.co.uk/legal): "Unless otherwise stated, the copyright
and any other rights in the contents of the Resources, including but not limited to images,
text and data, are owned by the Governor and Company of the Bank of England." Users may
"download, display or print the Resources for personal use or internal use within an
individual organisation for non-commercial purposes"; "The Bank typically grants permission
for non-commercial re-use of the Resources, particularly in an academic or education
context." Redistribution is therefore not granted by default. robots.txt has no
Crawl-delay; the default 2 s interval applies.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from io import BytesIO
from typing import cast
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag
from pypdf import PdfReader
from pypdf.errors import DependencyError, PyPdfError

from cbtone.schema import DocType, Document, Section
from cbtone.sources.base import RawResponse, SourceAdapter

log = logging.getLogger(__name__)

BASE = "https://www.bankofengland.co.uk"
SITEMAP_URL = f"{BASE}/_api/sitemap/getsitemap"
LONDON = ZoneInfo("Europe/London")
FIRST_YEAR = 1997
COMBINED_START = date(2015, 8, 6)  # first summary-and-minutes publication

_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
_LOC = re.compile(r"<loc>([^<]+)</loc>")
_NEWS = re.compile(rf"^/news/(\d{{4}})/(?:{_MONTHS})/mpc-(?:{_MONTHS})-\d{{4}}$")
_MINUTES = re.compile(
    rf"^/minutes/(\d{{4}})/(?:monetary-policy-committee|minutes)-(?:\d{{1,2}}-)?(?:{_MONTHS})-\d{{4}}$"
)
_COMBINED = re.compile(r"^/monetary-policy-summary-and-minutes/(\d{4})/[a-z0-9-]+$")
_DATE = re.compile(rf"\b(\d{{1,2}})\s+({_MONTHS})\s+(\d{{4}})\b", re.I)
_ENDING = re.compile(rf"meeting ending (?:on )?(\d{{1,2}}\s+(?:{_MONTHS})\s+\d{{4}})", re.I)
_PDF_LINK = re.compile(r"/files/(?:minutes|monetary-policy-summary-and-minutes)/.*\.pdf$", re.I)
_MINUTES_HEAD = re.compile(r"^minutes of the", re.I)
_WS = re.compile(r"[ \t\r\f\v\xa0]+")
_PAR_SPLIT = re.compile(r"\n\s*\n")
_PDF_START = re.compile(r"^minutes of the monetary policy committee meeting", re.I)
_PDF_NUMBERED = re.compile(r"^(\d{1,3})\s+(\S.*)$")
_NOTICE = re.compile(
    r"^(the minutes of the meeting will be published\b|the committee.s latest inflation and "
    r"output projections will appear\b).{0,200}$",
    re.I,
)
_PDF_FOOTER = re.compile(r"^(bank of england\s+minutes of|\d{1,3}$)", re.I)


def _clean(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _parse_date(text: str) -> date | None:
    """Last ``D Month YYYY`` date in ``text``."""
    found = _DATE.findall(text)
    if not found:
        return None
    d, m, y = found[-1]
    return datetime.strptime(f"{d} {m.title()} {y}", "%d %B %Y").date()


def release_time(doc_type: str, published: date, *, special: bool = False) -> datetime | None:
    """UTC release time of a BoE decision (``statement``) or ``minutes`` (see module doc)."""
    if special:
        return None
    t = dtime(9, 30) if doc_type == "minutes" and published < COMBINED_START else dtime(12, 0)
    return datetime.combine(published, t, tzinfo=LONDON).astimezone(UTC)


class _Page:
    """What ``list_urls`` and ``parse`` need from one BoE HTML page."""

    def __init__(self, html: bytes) -> None:
        self.soup = BeautifulSoup(html, "lxml")
        h1 = self.soup.find("h1")
        self.title = _clean(h1.get_text(" ")) if h1 else ""
        pub = self.soup.select_one("div.published-date")
        self.published = _parse_date(pub.get_text(" ")) if pub else None
        main = self.soup.find("main")
        self.pdf_hrefs = [  # collected first: _blocks() removes download links from the tree
            str(a["href"])
            for a in (main.find_all("a", href=True) if isinstance(main, Tag) else [])
            if _PDF_LINK.search(urlsplit(str(a["href"])).path)
        ]
        self.blocks = self._blocks()
        hero = self.soup.select_one("div.page-description")
        self.lead = _clean(hero.get_text(" ")) if hero else ""

    @property
    def placeholder(self) -> bool:
        return "to be published" in self.title.lower() or not self.blocks

    @property
    def is_minutes_page(self) -> bool:
        return bool(_MINUTES_HEAD.match(self.title))

    @property
    def has_minutes_section(self) -> bool:
        return any(tag == "h2" and _MINUTES_HEAD.match(t) for tag, t in self.blocks)

    def pdf_url(self, page_url: str) -> str | None:
        return urljoin(page_url, self.pdf_hrefs[0]) if self.pdf_hrefs else None

    def body_text(self) -> str:
        return " ".join(t for _, t in self.blocks)

    def _blocks(self) -> list[tuple[str, str]]:
        """``(tag, text)`` for the headings and paragraphs of the article, in order."""
        pub = self.soup.select_one("div.published-date")
        section = pub.find_parent("section") if pub else None
        if not isinstance(section, Tag):
            return []
        for junk in section.select(
            "form, img, script, style, div.hero-paragraph, div.container-latest, "
            "div.container-download, div.related-links-wrap, div.icon-title-list"
        ):
            junk.decompose()
        for a in section.select('a[href*="/-/media/"]'):  # download links, not prose
            parent = a.find_parent(["p", "li"])
            if parent is not None and _clean(parent.get_text(" ")) == _clean(a.get_text(" ")):
                parent.decompose()
            else:
                a.decompose()
        out: list[tuple[str, str]] = []
        for pc in section.select("div.content-block > div.page-content"):
            for el in pc.find_all(["h2", "h3", "h4", "p", "li"]):
                if not isinstance(el, Tag):
                    continue
                if el.name == "p" and el.find_parent("li"):
                    continue
                if el.name == "li" and el.find(["li", "p"]):
                    continue
                for br in el.find_all("br"):
                    br.replace_with("\n")
                raw = el.get_text("")
                parts = _PAR_SPLIT.split(raw) if el.name == "p" else [raw]
                for part in parts:
                    text = _clean(re.sub(r"\s*\n\s*", " ", part))
                    if text:
                        out.append((el.name, text))
        return out


class BoEAdapter(SourceAdapter):
    """See the module docstring for document types, URLs, eras, times and terms."""

    bank = "boe"

    # -- discovery -----------------------------------------------------------
    @staticmethod
    def parse_sitemap(xml: str) -> Iterator[tuple[str, str]]:
        """Yield ``(kind, url)`` for MPC pages; kind is ``news``, ``minutes`` or ``combined``."""
        for loc in _LOC.findall(xml):
            path = loc[len(BASE) :] if loc.startswith(BASE) else ""
            for kind, pat in (("news", _NEWS), ("minutes", _MINUTES), ("combined", _COMBINED)):
                if pat.match(path):
                    yield kind, loc
                    break

    def list_urls(self, start_year: int, end_year: int) -> Iterator[tuple[str, dict[str, str]]]:
        sitemap = self.fetcher.get(self.bank, SITEMAP_URL).content.decode("utf-8", "replace")
        by_year: dict[int, list[tuple[str, str]]] = {}
        for kind, url in self.parse_sitemap(sitemap):
            year = int(urlsplit(url).path.split("/")[2])
            if max(start_year, FIRST_YEAR) <= year <= end_year:
                by_year.setdefault(year, []).append((kind, url))
        for year in sorted(by_year):
            found: list[tuple[str, dict[str, str]]] = []
            for kind, url in sorted(by_year[year], key=lambda x: x[1]):
                found.extend(self._entries(kind, url))
            yield from sorted(found, key=lambda x: (x[1]["date"], x[1]["doc_type"]))

    def _entries(self, kind: str, url: str) -> list[tuple[str, dict[str, str]]]:
        raw = self.fetcher.get(self.bank, url)
        page = _Page(raw.content)
        if page.placeholder or page.published is None:
            return []
        pub = page.published.isoformat()
        base = {"language": "en", "title": page.title, "published": pub, "page": url}
        special = "special" in url.lower() or "special" in page.title.lower()
        if special:
            base["special"] = "1"
        meeting = self._meeting_date(page).isoformat()
        if kind == "news":
            return [(url, {**base, "doc_type": "statement", "date": pub})]
        if page.has_minutes_section:
            return [(url, {**base, "doc_type": "combined", "date": pub, "meeting": meeting})]
        pdf = page.pdf_url(url)
        if kind == "minutes" or page.is_minutes_page:
            if pdf:
                return [(pdf, {**base, "doc_type": "minutes", "date": meeting})]
            return [(url, {**base, "doc_type": "minutes", "date": meeting})]
        out = [(url, {**base, "doc_type": "statement", "date": pub})]
        if pdf:
            out.append((pdf, {**base, "doc_type": "minutes", "date": meeting}))
        return out

    @staticmethod
    def _meeting_date(page: _Page) -> date:
        """Last day of the meeting a page covers (title, then body, then publication date)."""
        for text in (page.title, *(t for tag, t in page.blocks if tag == "h2")):
            if re.search(r"held on|ending", text, re.I):
                d = _parse_date(text)
                if d:
                    return d
        m = _ENDING.search(page.body_text())
        if m and (d := _parse_date(m.group(1))):
            return d
        assert page.published is not None
        return (
            page.published - timedelta(days=1)
            if page.published >= COMBINED_START
            else page.published
        )

    # -- parsing -------------------------------------------------------------
    def parse(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        if raw.content[:5] == b"%PDF-" or "pdf" in raw.content_type.lower():
            return self._parse_pdf(raw, hints)
        return self._parse_html(raw, hints)

    def _doc(
        self,
        raw: RawResponse,
        hints: dict[str, str],
        doc_type: str,
        d: date,
        title: str,
        sections: list[Section],
    ) -> Document:
        published = date.fromisoformat(hints["published"]) if hints.get("published") else None
        return Document(
            bank="boe",
            date=d,
            published_at_utc=(
                release_time(doc_type, published, special=bool(hints.get("special")))
                if published
                else None
            ),
            doc_type=cast(DocType, doc_type),
            language="en",
            title=title,
            text="\n\n".join(s.text for s in sections),
            sections=sections,
            url=raw.url,
            sha256=raw.sha256,
            fetched_at=raw.fetched_at,
        )

    def _parse_html(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        page = _Page(raw.content)
        if page.placeholder:
            return []
        want = hints["doc_type"]
        kind = "minutes" if want == "minutes" else "statement"
        titles = {"statement": page.title, "minutes": page.title}
        buckets: dict[str, list[Section]] = {"statement": [], "minutes": []}
        heading: str | None = None
        for tag, text in page.blocks:
            if tag == "h2" and _MINUTES_HEAD.match(text) and want == "combined":
                kind, heading = "minutes", None
                titles["minutes"] = text
                continue
            if tag in ("h2", "h3", "h4"):
                if text.lower().startswith("monetary policy summary and minutes"):
                    continue  # page-title echo, not a section
                heading = text
                continue
            buckets[kind].append(Section(heading=heading, text=text))
        if want == "statement" and "/news/" in raw.url:
            # 2000-2012 press releases keep the decision sentence in the page lead.
            if page.lead and page.lead not in page.body_text():
                buckets["statement"].insert(0, Section(heading=None, text=page.lead))
            kept = [x for x in buckets["statement"] if not _NOTICE.match(x.text)]
            buckets["statement"] = kept or buckets["statement"]
        d0 = date.fromisoformat(hints["date"])
        wanted = ("statement", "minutes") if want == "combined" else (want,)
        docs: list[Document] = []
        for dt in wanted:
            if not buckets[dt]:
                continue
            d = self._meeting_date(page) if want == "combined" and dt == "minutes" else d0
            docs.append(self._doc(raw, hints, dt, d, titles[dt], buckets[dt]))
        return docs

    def _parse_pdf(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        try:
            reader = PdfReader(BytesIO(raw.content))
            text = "\n".join(p.extract_text() or "" for p in reader.pages)
        except DependencyError:
            log.warning("cannot decrypt %s (install `cryptography`); skipped", raw.url)
            return []
        except PyPdfError:
            log.warning("unreadable PDF %s; skipped", raw.url)
            return []
        sections = self.pdf_sections(text)
        if not sections:
            return []
        d = date.fromisoformat(hints["date"])
        return [self._doc(raw, hints, "minutes", d, hints.get("title", ""), sections)]

    @staticmethod
    def pdf_sections(text: str) -> list[Section]:
        """Paragraphs of the minutes in extracted PDF text (numbered ``1 ...``, ``2 ...``)."""
        lines = [_clean(line) for line in text.splitlines()]
        start = next((i for i, ln in enumerate(lines) if _PDF_START.match(ln)), None)
        if start is not None:
            lines = lines[start + 1 :]
        sections: list[Section] = []
        heading: str | None = None
        cur: list[str] = []
        expected = 1

        def flush() -> None:
            if cur:
                sections.append(Section(heading=heading, text=_clean(" ".join(cur))))
                cur.clear()

        for ln in lines:
            if not ln or _PDF_FOOTER.match(ln):
                continue
            m = _PDF_NUMBERED.match(ln)
            if m and int(m.group(1)) == expected:
                flush()
                expected += 1
                cur.append(m.group(2))
            elif (
                len(ln) <= 70
                and ln[0].isupper()
                and not ln.endswith((".", ",", ";", ":"))
                and (not cur or cur[-1].endswith("."))
                and expected > 1
            ):
                flush()
                heading = ln
            elif cur:
                cur.append(ln)
        flush()
        return sections
