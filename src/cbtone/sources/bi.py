"""Bank Indonesia (BI) adapter.

Document types
    * ``statement``: the press release ("Siaran Pers" / "News Release") issued after each
      Board of Governors Meeting (RDG, Rapat Dewan Gubernur) with the policy-rate decision.
      The policy rate was the BI Rate (to Aug 2016), the BI 7-Day (Reverse) Repo Rate
      (Aug 2016 - Dec 2023) and again the BI-Rate (from 21 Dec 2023).

Languages: ``id`` and ``en``. Both versions of a release share the same page slug
(``Pages/sp_<slug>.aspx``) and differ only in the first path segment, so a release found in one
language is paired by swapping ``/en/`` and ``/id/``. Both get
``parallel_id = "bi:<date>:statement"``. A language version that does not exist is served by
the site as an HTTP 200 "404" page without a release body; ``parse`` returns ``[]`` for it.

URL patterns
    * Index: ``https://www.bi.go.id/en/statistik/indikator/BI-Rate.aspx`` - table of every RDG
      decision since April 2016 (period, rate, press-release link), 10 rows per page, newest
      first. It pages through an ASP.NET postback: ``list_urls`` GETs page 1, then POSTs the
      form back (``__VIEWSTATE``, ``__EVENTVALIDATION``, ... plus the "Next" image button) via
      ``PoliteFetcher.post`` until the last page or ``start_year``. 13 pages, 128 rows.
      Hand-saved pages in ``data/raw/bi/manual/*.html`` are read as a fallback.
    * Release: ``/{en,id}/publikasi/ruang-media/news-release/Pages/sp_<slug>.aspx``; the
      slug is ``<year-1998><ordinal in year><YY>`` since 2024, and ``<ordinal><YY>`` before.
      The generic listing ``.../news-release/default.aspx`` mixes every kind of release and is
      postback-paged as well, so it is not used.

Date range: decisions from 2016-04-21 (the index table starts there; the BI Rate era before
that, 2005-2016-04, is not listed on the current site). Releases verified for 2016-2026.

Dates and times
    ``date`` is the announcement date of the decision from the index table (the last day of the
    two-day meeting). ``published_at_utc`` is ``None``: BI documents no release time, and the
    page timestamp (``M/D/YYYY h:mm AM/PM``) is inconsistent between language versions
    (e.g. 8:00 PM en vs 2:00 PM id for 17 Sep 2025). If a rule is adopted, the zone is
    ``Asia/Jakarta`` (WIB, UTC+7, no DST).

Terms of use
    No terms/copyright page found on bi.go.id; page footers read "(c) 2020 Bank Indonesia".
    No licence for reuse is stated; treat as not redistributable until BI confirms.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import cast
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from cbtone.schema import Document, Language, Section
from cbtone.sources.base import RawResponse, SourceAdapter

BASE = "https://www.bi.go.id"
INDEX_URL = f"{BASE}/en/statistik/indikator/BI-Rate.aspx"
MANUAL_SUBDIR = "manual"
MAX_PAGES = 100  # safety cap; the table has about 25 pages

_MONTHS = {
    "january": 1,
    "januari": 1,
    "february": 2,
    "februari": 2,
    "pebruari": 2,
    "march": 3,
    "maret": 3,
    "april": 4,
    "may": 5,
    "mei": 5,
    "june": 6,
    "juni": 6,
    "july": 7,
    "juli": 7,
    "august": 8,
    "agustus": 8,
    "september": 9,
    "october": 10,
    "oktober": 10,
    "november": 11,
    "nopember": 11,
    "december": 12,
    "desember": 12,
}
_DATE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
_PAGE_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})\s+\d{1,2}:\d{2}")
_WS = re.compile(r"\s+")
_NUMBER = re.compile(r"^No\.?:?\s*\d+\s*/\s*\d+\s*/\s*\w+", re.I)
_DEPT = re.compile(r"\s*(communication departe?ment|departemen komunikasi)\s*$", re.I)
_RELEASE_PATH = re.compile(r"^/(en|id)(/publikasi/ruang-media/news-release/Pages/.+)$")


def _clean(text: str) -> str:
    text = text.replace("​", "").replace("\xa0", " ")
    return _WS.sub(" ", text).strip()


def parse_date(text: str) -> date | None:
    """Parse ``'23 September 2026'`` (English or Indonesian month names)."""
    m = _DATE.search(text)
    if not m:
        return None
    month = _MONTHS.get(m.group(2).lower())
    return date(int(m.group(3)), month, int(m.group(1))) if month else None


class BIAdapter(SourceAdapter):
    """See the module docstring for document types, URLs, languages, times and terms."""

    bank = "bi"

    # -- discovery -----------------------------------------------------------
    @staticmethod
    def parse_index(html: str | bytes) -> Iterator[tuple[date, str, str]]:
        """Yield ``(date, rate_text, href)`` rows from a BI-Rate indicator table."""
        soup = BeautifulSoup(html, "lxml")
        for tr in soup.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            d = parse_date(cells[0].get_text(" "))
            a = cells[-1].find("a", href=True)
            if d is None or a is None:
                continue
            href = str(a["href"]).split("?")[0].split("#")[0]
            yield d, _clean(cells[1].get_text(" ")), href

    @staticmethod
    def next_page_form(html: str | bytes) -> dict[str, str] | None:
        """POST body that clicks "Next" on an indicator page, or ``None`` on the last page.

        Carries every hidden/text field (``__VIEWSTATE``, ``__EVENTVALIDATION``, ...).
        """
        soup = BeautifulSoup(html, "lxml")
        form = soup.find("form")
        nxt = soup.select_one("span.pagination input.next")
        if not isinstance(form, Tag) or not isinstance(nxt, Tag) or nxt.get("disabled"):
            return None
        data: dict[str, str] = {}
        for inp in form.find_all("input"):
            name = inp.get("name")
            if name and inp.get("type") in ("hidden", "text"):
                data[str(name)] = str(inp.get("value") or "")
        base = str(nxt["name"])
        data[base + ".x"] = "5"
        data[base + ".y"] = "5"
        return data

    def _index_rows(self, start_year: int = 0) -> list[tuple[date, str, str]]:
        """Rows from the live paged table (newest first, paged backwards to ``start_year``),
        plus any hand-saved pages in ``data/raw/bi/manual/``."""
        raw = self.fetcher.get(self.bank, INDEX_URL)
        rows: list[tuple[date, str, str]] = []
        for _ in range(MAX_PAGES):
            page = list(self.parse_index(raw.content))
            rows.extend(page)
            form = self.next_page_form(raw.content)
            if not page or form is None or min(r[0] for r in page).year < start_year:
                break
            raw = self.fetcher.post(self.bank, INDEX_URL, form)
        manual = Path(self.fetcher.raw_dir) / self.bank / MANUAL_SUBDIR
        if manual.is_dir():
            for f in sorted(manual.glob("*.htm*")):
                rows.extend(self.parse_index(f.read_bytes()))
        return rows

    def list_urls(self, start_year: int, end_year: int) -> Iterator[tuple[str, dict[str, str]]]:
        seen: set[str] = set()
        for d, rate, href in sorted(self._index_rows(start_year), key=lambda r: r[0]):
            if not start_year <= d.year <= end_year:
                continue
            path = urljoin(BASE, href)[len(BASE) :]
            m = _RELEASE_PATH.match(path)
            variants = (
                [(lang, f"/{lang}{m.group(2)}") for lang in ("en", "id")]
                if m
                else [("id" if path.startswith("/id/") else "en", path)]
            )
            for lang, p in variants:
                url = BASE + p
                if url in seen:
                    continue
                seen.add(url)
                yield (
                    url,
                    {
                        "doc_type": "statement",
                        "date": d.isoformat(),
                        "language": lang,
                        "parallel_id": f"bi:{d.isoformat()}:statement",
                        "policy_rate": rate,
                    },
                )

    # -- parsing -------------------------------------------------------------
    @staticmethod
    def _body(soup: BeautifulSoup) -> Tag | None:
        cands = [
            c
            for c in soup.select("div.page-description div.ms-rtestate-field")
            if _clean(c.get_text(" "))
        ]
        return max(cands, key=lambda c: len(c.get_text())) if cands else None

    @staticmethod
    def _blocks(body: Tag) -> list[str]:
        out: list[str] = []
        for el in body.find_all(["p", "li"]):
            if not isinstance(el, Tag):
                continue
            if el.name == "p" and el.find_parent("li") is not None:
                continue
            node = el
            if el.name == "li":
                node = copy.copy(el)
                for nested in node.find_all(["ol", "ul"]):
                    nested.decompose()
            out.append(_clean(node.get_text(" ")))
        return out

    def parse(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        soup = BeautifulSoup(raw.content, "lxml")
        body = self._body(soup)
        if body is None:
            return []
        lang = hints.get("language") or ("id" if "/id/" in raw.url else "en")
        sections: list[Section] = []
        after_dateline = False
        for text in self._blocks(body):
            if not text or _NUMBER.match(text):
                continue
            if after_dateline and not text.startswith("["):
                continue  # signatories after the dateline
            if text.startswith("Jakarta,"):
                after_dateline = True
                text = _DEPT.sub("", text)
            sections.append(Section(heading=None, text=text))
        if not sections:
            return []
        d = self._date(soup, hints)
        if d is None:
            return []
        h4 = soup.select_one("#layout-title")
        title = (
            _clean(h4.get_text(" "))
            if h4
            else _clean(soup.title.get_text(" ") if soup.title else "")
        )
        parallel = hints.get("parallel_id") or f"bi:{d.isoformat()}:statement"
        return [
            Document(
                bank="bi",
                date=d,
                published_at_utc=None,
                doc_type="statement",
                language=cast(Language, lang),
                parallel_id=parallel,
                title=title,
                text="\n\n".join(s.text for s in sections),
                sections=sections,
                url=raw.url,
                sha256=raw.sha256,
                fetched_at=raw.fetched_at,
            )
        ]

    @staticmethod
    def _date(soup: BeautifulSoup, hints: dict[str, str]) -> date | None:
        if hints.get("date"):
            return date.fromisoformat(hints["date"])
        for el in soup.select(".thumb-detail__desc-title"):
            m = _PAGE_DATE.search(el.get_text(" "))
            if m:  # page stamps are M/D/YYYY
                return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        return None


__all__ = ["BIAdapter", "parse_date"]
