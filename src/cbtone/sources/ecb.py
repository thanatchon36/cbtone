"""European Central Bank (ECB) adapter.

Document types
    * ``statement``: the "Monetary policy decisions" press release issued after each
      Governing Council monetary-policy meeting (titled "Decisions on ECB interest rates"
      in Jan-Feb 1999).
    * ``press_conference``: the President's introductory statement (called "Monetary policy
      statement" since 2022) followed by the Q&A transcript of the press conference.
      Intro sections carry the page's sub-headings (or ``None``); every Q&A paragraph has
      ``heading="Q&A"``.

URL patterns (English only; ``language="en"``)
    * Index (static HTML fragments, one per year; the visible list pages fill themselves
      with JavaScript from these includes):
      ``https://www.ecb.europa.eu/press/pressconf/YYYY/html/index_include.en.html`` and
      ``https://www.ecb.europa.eu/press/pr/date/YYYY/html/index_include.en.html``
      (``<dt isoDate="YYYY-MM-DD">`` + ``<dd>`` pairs).
    * Press release: ``/press/pr/date/YYYY/html/prYYMMDD.en.html`` (1999-2021) or
      ``/press/pr/date/YYYY/html/ecb.mpYYMMDD~<hash>.en.html`` (2022 onward).
    * Press conference: ``/press/press_conference/monetary-policy-statement/YYYY/html/
      isYYMMDD.en.html`` or ``ecb.isYYMMDD~<hash>.en.html``.

Date range: 1999-01 to present (first Governing Council decisions Jan 1999).

Release-time rule (``published_at_utc``; zoneinfo ``Europe/Berlin``, i.e. Frankfurt time)
    * Until 20 July 2022: decision press release 13:45, press conference 14:30.
    * From 21 July 2022: decision press release 14:15, press conference 14:45.
    Source: ECB press release "New times for ECB's monetary policy decisions and press
    conference", 27 June 2022 (https://www.ecb.europa.eu/press/pr/date/2022/html/
    ecb.pr220627~73acedf868.en.html): "monetary policy decisions will be published at
    14:15 CET (instead of 13:45). The press conferences will begin at 14:45 CET (instead
    of 14:30)." The old press-conference time is also stated in each press release
    ("press conference starting at 14:30 CET today"; "2.30 p.m." in 1999). The ECB writes
    "CET" for Frankfurt local time all year; we convert with the Frankfurt zone (so CEST in
    summer). The statement time is only set when the press release announces a press
    conference (decisions at meetings without one have no documented time -> ``None``).
    For ``press_conference`` the timestamp is the start of the press conference.

Terms of use (https://www.ecb.europa.eu/services/disclaimer/html/index.en.html)
    "Subject to the exception below, users of this website may make free use of the
    information obtained directly from it subject to the following conditions: When such
    information is distributed or reproduced, it must appear accurately and the ECB must
    be cited as the source." Exception: reproduction of "documents that bear the name of
    their authors, such as ECB Working Papers and ECB Occasional Papers, in the form of a
    different publication" needs prior written authorisation. Press releases carry
    "Reproduction is permitted provided that the source is acknowledged."
    robots.txt requests ``Crawl-delay: 5``; this adapter raises the fetcher interval to 5 s.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from datetime import time as dtime
from typing import Any, cast
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

from cbtone.schema import DocType, Document, Section
from cbtone.sources.base import PoliteFetcher, RawResponse, SourceAdapter

BASE = "https://www.ecb.europa.eu"
FRANKFURT = ZoneInfo("Europe/Berlin")  # IANA has no Europe/Frankfurt; same rules as CET/CEST
FIRST_YEAR = 1999
CRAWL_DELAY_S = 5.0  # robots.txt: Crawl-delay: 5
TIME_CHANGE = date(2022, 7, 21)  # first decision published at 14:15 / conference 14:45

_STATEMENT_TITLE = re.compile(
    r"^(monetary policy decisions|decisions on ecb interest rates)\b", re.I
)
_PC_FILE = re.compile(r"/(?:ecb\.)?is\d{6}[^/]*\.en\.html$")
_OPEN_FLOOR = re.compile(r"(at your disposal|ready to take your)[^.]*questions", re.I)
_PR_PATH = "/press/pr/date/"
_WS = re.compile(r"\s+")
_NOISE = {"* * *", "***", "* * * *"}


def _clean(text: str) -> str:
    return _WS.sub(" ", text.replace("\xa0", " ")).strip()


def release_time(doc_type: str, d: date) -> datetime:
    """UTC release time for an ECB decision (``statement``) or press conference."""
    new = d >= TIME_CHANGE
    if doc_type == "statement":
        t = dtime(14, 15) if new else dtime(13, 45)
    else:
        t = dtime(14, 45) if new else dtime(14, 30)
    return datetime.combine(d, t, tzinfo=FRANKFURT).astimezone(UTC)


class EcbAdapter(SourceAdapter):
    """See the module docstring for document types, URLs, eras, times and terms."""

    bank = "ecb"

    def __init__(self, fetcher: PoliteFetcher) -> None:
        super().__init__(fetcher)
        self.fetcher.min_interval_s = max(self.fetcher.min_interval_s, CRAWL_DELAY_S)

    # -- discovery -----------------------------------------------------------
    @staticmethod
    def parse_index(html: str) -> Iterator[tuple[str, str, str]]:
        """Yield ``(iso_date, href, title)`` from a per-year ``index_include`` fragment."""
        soup = BeautifulSoup(html, "lxml")
        for dt in soup.find_all("dt"):
            iso = dt.get("isodate")
            dd = dt.find_next_sibling("dd")
            if not isinstance(iso, str) or not isinstance(dd, Tag):
                continue
            a = dd.select_one(".title a")
            href = a.get("href") if a else None
            if a is None or not isinstance(href, str):
                continue
            yield iso, href.split("?")[0], _clean(a.get_text(" "))

    def list_urls(self, start_year: int, end_year: int) -> Iterator[tuple[str, dict[str, str]]]:
        for year in range(max(start_year, FIRST_YEAR), end_year + 1):
            seen_pc: set[str] = set()
            seen_url: set[str] = set()
            found: list[tuple[str, dict[str, str]]] = []
            for idx in (
                f"{BASE}/press/pressconf/{year}/html/index_include.en.html",
                f"{BASE}/press/pr/date/{year}/html/index_include.en.html",
            ):
                raw = self.fetcher.get(self.bank, idx)
                for iso, href, title in self.parse_index(raw.content.decode("utf-8", "replace")):
                    if not iso.startswith(str(year)) or not href.endswith(".en.html"):
                        continue
                    url = BASE + href if href.startswith("/") else href
                    if url in seen_url:
                        continue
                    if _PC_FILE.search(href) and (
                        "/press_conference/" in href or "/pressconf/" in href
                    ):
                        # the same conference is listed under two path aliases
                        if iso in seen_pc:
                            continue
                        seen_pc.add(iso)
                        doc_type = "press_conference"
                    elif _PR_PATH in href and _STATEMENT_TITLE.match(title):
                        doc_type = "statement"
                    else:
                        continue
                    seen_url.add(url)
                    found.append(
                        (url, {"doc_type": doc_type, "date": iso, "language": "en", "title": title})
                    )
            yield from sorted(found, key=lambda x: (x[1]["date"], x[1]["doc_type"]))

    # -- parsing -------------------------------------------------------------
    def parse(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        soup = BeautifulSoup(raw.content, "lxml")
        main = soup.find("main")
        if not isinstance(main, Tag):
            return []
        doc_type = hints["doc_type"]
        d = date.fromisoformat(hints["date"])
        h1 = main.find("h1")
        title_el = h1 if isinstance(h1, Tag) else main.select_one("div.title")
        title = _clean(title_el.get_text(" ")) if title_el else ""
        title = re.sub(r"^press release\s+", "", title, flags=re.I)
        if doc_type == "press_conference" and hints.get("title"):
            title = hints["title"].split(": ", 1)[-1]  # drop "Speaker, Speaker: " prefix
        title = title or hints.get("title", "")
        if doc_type == "press_conference":
            sections = self._pc_sections(main)
            published: datetime | None = release_time(doc_type, d)
        else:
            sections = self._pr_sections(main)
            body = " ".join(s.text for s in sections)
            published = release_time(doc_type, d) if "press conference" in body.lower() else None
        if not sections:
            return []
        return [
            Document(
                bank="ecb",
                date=d,
                published_at_utc=published,
                doc_type=cast(DocType, doc_type),
                language="en",
                title=title,
                text="\n\n".join(s.text for s in sections),
                sections=sections,
                url=raw.url,
                sha256=raw.sha256,
                fetched_at=raw.fetched_at,
            )
        ]

    @staticmethod
    def _classes(el: Tag) -> list[str]:
        c: Any = el.get("class")
        return list(c) if c else []

    def _blocks(self, main: Tag) -> list[Tag]:
        """Paragraph/heading/list-item elements of the article body, in order."""
        out: list[Tag] = []
        for sec in main.select("main > div.section, main > div.orderedlist, main > div.appendix"):
            for el in sec.find_all(["p", "h2", "h3", "li", "div"]):
                if not isinstance(el, Tag):
                    continue
                if el.name == "div" and "titlepage" not in self._classes(el):
                    continue
                if el.name == "p" and el.find_parent("li"):
                    continue
                if el.name == "li" and el.find("li"):
                    continue
                out.append(el)
        return out

    def _pr_sections(self, main: Tag) -> list[Section]:
        sections: list[Section] = []
        heading: str | None = None
        for el in self._blocks(main):
            text = _clean(el.get_text(" "))
            if not text or text in _NOISE or "ecb-publicationDate" in self._classes(el):
                continue
            if el.name in ("h2", "h3"):
                heading = text
                continue
            sections.append(Section(heading=heading, text=text))
        return sections

    def _pc_sections(self, main: Tag) -> list[Section]:
        blocks = self._blocks(main)
        qa_idx: int | None = None
        for i, el in enumerate(blocks):  # 1) anchor id="qa" (2020s layout)
            if el.find(id="qa") is not None:
                qa_idx = i + 1
                break
        if qa_idx is None:
            for i, el in enumerate(blocks):  # 2) 1999 transcript title page / 2004 appendix
                if el.name == "div" or el.find_parent("div", class_="appendix") is not None:
                    qa_idx = i + 1 if el.name == "div" else i
                    break
        if qa_idx is None:
            for i, el in enumerate(blocks):  # 3) "...at your disposal / ready to take questions"
                if _OPEN_FLOOR.search(_clean(el.get_text(" "))):
                    qa_idx = i + 1
                    break
        if qa_idx is None:
            for i, el in enumerate(blocks):  # 4) first "Question:" paragraph
                if re.match(r"Question\b", _clean(el.get_text(" "))):
                    qa_idx = i
                    break
        sections: list[Section] = []
        heading: str | None = None
        for i, el in enumerate(blocks):
            in_qa = qa_idx is not None and i >= qa_idx
            text = _clean(el.get_text(" "))
            classes = self._classes(el)
            if (
                not text
                or text in _NOISE
                or el.name == "div"
                or "ecb-publicationDate" in classes
                or "ecb-pressContentSubtitle" in classes
                or text.lower().startswith(("jump to the transcript", "with the transcript"))
            ):
                continue
            if el.name in ("h2", "h3") and not in_qa:
                heading = text
                continue
            sections.append(Section(heading="Q&A" if in_qa else heading, text=text))
        return sections
