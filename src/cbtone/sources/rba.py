"""Reserve Bank of Australia (RBA) adapter.

Document types
    * ``statement``: the media release announcing each monetary-policy decision
      ("Statement by the Governor: Monetary Policy" up to 2024, "Statement by the Reserve
      Bank Board: Monetary Policy Decision" in 2024, "Statement by the Monetary Policy
      Board: Monetary Policy Decision" since the Monetary Policy Board replaced the
      Reserve Bank Board on 1 March 2025). Before December 2007 a release was issued
      only when the cash rate target changed; since then after every Board meeting.
    * ``minutes``: minutes of the monetary-policy meeting of the Reserve Bank Board
      (Oct 2006 onwards, first published Dec 2007) and, since 2025, of the Monetary
      Policy Board. Attendance lists and the "minutes approved" line are dropped.
    * ``press_conference``: transcript of the Governor's media conference after the
      decision (from Feb 2024). The Governor's opening statement has ``heading=None``;
      every question and answer paragraph has ``heading="Q&A"`` and is prefixed with
      the speaker's name ("Name: ...").

URL patterns (English only; ``language="en"``)
    * Index (static HTML, one per year):
      ``https://www.rba.gov.au/monetary-policy/int-rate-decisions/YYYY/`` (statements,
      1990-) and ``https://www.rba.gov.au/monetary-policy/rba-board-minutes/YYYY/``
      (minutes, 2006-). Both are ``ul.list-articles`` lists of links.
    * Statement: ``/media-releases/YYYY/mr-YY-NN.html``.
    * Minutes: ``/monetary-policy/rba-board-minutes/YYYY/DDMMYYYY.html`` (2006-~2009) or
      ``.../YYYY/YYYY-MM-DD.html``.
    * Media conference: ``/speeches/YYYY/mc-gov-YYYY-MM-DD.html``, discovered from the
      "More on the ... monetary policy decision" links of the statement page.

Date range: statements 1990-present, minutes Oct 2006-present, press conferences
Feb 2024-present.

``date`` is the meeting date. Statements issued the day after the meeting
("... at its meeting yesterday", common before 2008) are dated one day earlier than the
release; the minutes URL carries the meeting date.

Release-time rule (``published_at_utc``; zoneinfo ``Australia/Sydney``)
    * Statements from 2008 onward: 14:30 Sydney time. Source: the RBA page "Monetary
      Policy Decisions" (https://www.rba.gov.au/monetary-policy/int-rate-decisions/):
      "...explained in a media release announcing the decision at 2.30 pm after each
      Board meeting." Recent pages also carry it machine-readably
      (``datetime="2026-09-29T14:30+10:00"``), which takes precedence when present.
    * Earlier statements (cash-rate-change releases issued in the morning), minutes and
      press conferences: no documented time on the page -> ``None``.

Terms of use (https://www.rba.gov.au/copyright/)
    "most other material published on this website is provided under a Creative Commons
    Attribution 4.0 International License ... provided that the RBA is properly
    attributed." Excluded: logo, banknote images, third-party material, Cash Rate and
    financial-data terms, multimedia. The audio/video of media conferences is
    multimedia; the text transcripts fall under CC BY 4.0.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from typing import cast
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup, Tag

from cbtone.schema import DocType, Document, Section
from cbtone.sources.base import RawResponse, SourceAdapter

BASE = "https://www.rba.gov.au"
SYDNEY = ZoneInfo("Australia/Sydney")
FIRST_STATEMENT_YEAR = 1990
FIRST_MINUTES_YEAR = 2006
FIRST_PRESS_CONF_YEAR = 2024
STATEMENT_TIME_FROM = date(2008, 1, 1)  # 2.30 pm statements after every Board meeting

_WS = re.compile(r"\s+")
_YESTERDAY = re.compile(r"\bmeeting yesterday\b", re.I)
_MINUTES_DMY = re.compile(r"/(\d{2})(\d{2})(\d{4})\.html$")
_MINUTES_ISO = re.compile(r"/(\d{4})-(\d{2})-(\d{2})\.html$")
_MC_LINK = re.compile(r"^/speeches/\d{4}/mc-[^/]*\.html$")
_SKIP_HEADINGS = {"present", "members participating", "others participating", "minutes"}
_C1 = {
    chr(c): bytes([c]).decode("cp1252", errors="replace")
    for c in range(0x80, 0xA0)
    if bytes([c]).decode("cp1252", errors="replace") != "�"
}


def _clean(text: str) -> str:
    for bad, good in _C1.items():
        text = text.replace(bad, good)
    return _WS.sub(" ", text.replace("\xa0", " ")).strip()


def statement_release_time(d: date) -> datetime | None:
    """UTC time of the 14:30 Sydney statement, or ``None`` before 2008 (undocumented)."""
    if d < STATEMENT_TIME_FROM:
        return None
    return datetime.combine(d, dtime(14, 30), tzinfo=SYDNEY).astimezone(UTC)


class RBAAdapter(SourceAdapter):
    """See the module docstring for document types, URLs, eras, times and terms."""

    bank = "rba"

    # -- discovery -----------------------------------------------------------
    @staticmethod
    def parse_index(html: str) -> Iterator[tuple[str, str]]:
        """Yield ``(href, link_text)`` from a year index page's ``ul.list-articles``."""
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select("ul.list-articles > li > a"):
            href = a.get("href")
            if isinstance(href, str):
                yield href.split("?")[0], _clean(a.get_text(" "))

    def _index(self, url: str) -> str | None:
        try:
            return self.fetcher.get(self.bank, url).content.decode("utf-8", "replace")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    @staticmethod
    def _abs(href: str) -> str:
        return BASE + href if href.startswith("/") else href

    def _press_conference_url(self, statement_url: str) -> str | None:
        raw = self.fetcher.get(self.bank, statement_url)
        soup = BeautifulSoup(raw.content, "lxml")
        for a in soup.select("aside a[href]"):
            href = a.get("href")
            if isinstance(href, str) and _MC_LINK.match(href):
                return self._abs(href)
        return None

    def list_urls(self, start_year: int, end_year: int) -> Iterator[tuple[str, dict[str, str]]]:
        for year in range(max(start_year, FIRST_STATEMENT_YEAR), end_year + 1):
            html = self._index(f"{BASE}/monetary-policy/int-rate-decisions/{year}/")
            found: list[tuple[str, dict[str, str]]] = []
            for href, label in self.parse_index(html or ""):
                try:
                    d = datetime.strptime(label, "%d %B %Y").date()
                except ValueError:
                    continue
                url = self._abs(href)
                hints = {"doc_type": "statement", "date": d.isoformat(), "language": "en"}
                found.append((url, hints))
                if year >= FIRST_PRESS_CONF_YEAR:
                    mc = self._press_conference_url(url)
                    if mc is not None:
                        found.append((mc, {**hints, "doc_type": "press_conference"}))
            yield from sorted(found, key=lambda x: (x[1]["date"], x[1]["doc_type"] != "statement"))
        for year in range(max(start_year, FIRST_MINUTES_YEAR), end_year + 1):
            html = self._index(f"{BASE}/monetary-policy/rba-board-minutes/{year}/")
            found = []
            for href, _label in self.parse_index(html or ""):
                d_min = self.minutes_date(href)
                if d_min is not None:
                    hints = {"doc_type": "minutes", "date": d_min.isoformat(), "language": "en"}
                    found.append((self._abs(href), hints))
            yield from sorted(found, key=lambda x: x[1]["date"])

    @staticmethod
    def minutes_date(href: str) -> date | None:
        if m := _MINUTES_ISO.search(href):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := _MINUTES_DMY.search(href):
            return date(int(m[3]), int(m[2]), int(m[1]))
        return None

    # -- parsing -------------------------------------------------------------
    def parse(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        soup = BeautifulSoup(raw.content, "lxml")
        content = soup.find(id="content")
        root = content if isinstance(content, Tag) else soup
        doc_type = hints["doc_type"]
        d = date.fromisoformat(hints["date"])
        published: datetime | None = None
        if doc_type == "press_conference":
            sections = self._pc_sections(root)
        elif doc_type == "minutes":
            sections = self._minutes_sections(root)
        else:
            sections = self._statement_sections(root)
            published = self._statement_time(root, d)
            if sections and _YESTERDAY.search(sections[0].text):
                d -= timedelta(days=1)
        if not sections:
            return []
        h1 = root.find("h1")
        title = _clean(h1.get_text(" ")) if isinstance(h1, Tag) else ""
        if doc_type == "statement":
            span = root.select_one("span.rss-mr-title")
            title = _clean(span.get_text(" ")) if span else title
        return [
            Document(
                bank="rba",
                date=d,
                published_at_utc=published,
                doc_type=cast(DocType, doc_type),
                language="en",
                title=title or hints.get("title", ""),
                text="\n\n".join(s.text for s in sections),
                sections=sections,
                url=raw.url,
                sha256=raw.sha256,
                fetched_at=raw.fetched_at,
            )
        ]

    @staticmethod
    def _statement_time(root: Tag, release: date) -> datetime | None:
        t = root.select_one("div.article-data time[datetime]")
        stamp = t.get("datetime") if t else None
        if isinstance(stamp, str) and "T" in stamp:
            try:
                parsed = datetime.fromisoformat(stamp)
            except ValueError:
                parsed = None
            if parsed is not None and parsed.tzinfo is not None:
                return parsed.astimezone(UTC)
        return statement_release_time(release)

    @staticmethod
    def _blocks(container: Tag) -> list[Tag]:
        out: list[Tag] = []
        for el in container.find_all(["h2", "h3", "p", "li"]):
            if not isinstance(el, Tag):
                continue
            if el.find_parent(["aside", "nav"]) or el.find_parent(
                class_=["footnotes", "box-enquiries"]
            ):
                continue
            if el.name == "p" and el.find_parent("li"):
                continue
            if el.name == "li" and el.find("li"):
                continue
            out.append(el)
        return out

    def _statement_sections(self, root: Tag) -> list[Section]:
        body = root.select_one("[itemprop=text]")
        if body is None:
            return []
        sections: list[Section] = []
        heading: str | None = None
        for el in self._blocks(body):
            text = _clean(el.get_text(" "))
            if not text:
                continue
            if el.name in ("h2", "h3"):
                heading = text
            else:
                sections.append(Section(heading=heading, text=text))
        return sections

    def _minutes_sections(self, root: Tag) -> list[Section]:
        for sup in root.select("sup.footnote-ref"):
            sup.decompose()
        sections: list[Section] = []
        heading: str | None = None
        for el in self._blocks(root):
            text = _clean(el.get_text(" "))
            if not text or el.name == "h1":
                continue
            if el.name in ("h2", "h3"):
                heading = text
                continue
            if heading is not None and heading.lower() in _SKIP_HEADINGS:
                continue
            if heading is None:  # venue/date line ("Sydney - 3 October 2006") and intro
                continue
            sections.append(Section(heading=heading, text=text))
        return sections

    def _pc_sections(self, root: Tag) -> list[Section]:
        transcript = root.select_one("div.page-transcript")
        if transcript is None:
            return []
        sections: list[Section] = []
        first = True
        for speaker in transcript.select("h3.speaker"):
            part = speaker.find_next_sibling()
            if not isinstance(part, Tag) or "speech-part" not in (part.get("class") or []):
                continue
            name = _clean(speaker.get_text(" "))
            for p in part.find_all("p"):
                text = _clean(p.get_text(" ")).removeprefix("- ").strip()
                if not text:
                    continue
                if first:
                    sections.append(Section(heading=None, text=text))
                else:
                    sections.append(Section(heading="Q&A", text=f"{name}: {text}"))
            first = False
        return sections
