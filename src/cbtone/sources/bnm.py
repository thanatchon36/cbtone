"""Bank Negara Malaysia (BNM) adapter: Monetary Policy Committee statements, English + Malay.

Document types
    * ``statement``: the "Monetary Policy Statement" (Malay: "Pernyataan Dasar Monetari")
      issued on the last day of every Monetary Policy Committee (MPC) meeting. Each statement
      is published in both languages, so every meeting yields two documents:
      ``language="en"`` and ``language="ms"``, sharing ``parallel_id`` =
      ``"bnm:<YYYY-MM-DD>:statement"``.

Languages and how translations are paired
    The site (Liferay) chooses the language from a session cookie, and the localised page has
    the same path in both languages (the ``/ms/`` prefix and ``?languageId=`` do not work: 404 or
    English). To stay stateless the adapter always asks for the language explicitly through the
    portal's own language-switch endpoint, which redirects to the page:
    ``/c/portal/update_language?p_l_id=<id>&redirect=<path>&languageId=en_US|ms_MY``.
    The English and Malay pages of one meeting share the slug ``monetary-policy-statement-DDMMYYYY``
    (DDMMYYYY = decision date), which is what pairs them. ``parse`` takes the language from
    ``<html lang>`` (falling back to the hint), so a session-language leak cannot mislabel a page.

URL patterns
    * Index (one static table, all years, English or Malay labels):
      ``https://www.bnm.gov.my/monetary-stability/opr-decisions`` (columns: date, change in OPR,
      new OPR level, link "View Statement" / "Lihat Pernyataan").
    * Statement: ``https://www.bnm.gov.my/-/monetary-policy-statement-DDMMYYYY``.
    * Fetched URLs (these are the ``url`` of the Documents):
      ``https://www.bnm.gov.my/c/portal/update_language?p_l_id=182&redirect=%2F-%2F
      monetary-policy-statement-DDMMYYYY&languageId=en_US`` (``ms_MY`` for Malay).

Date range: 2004-05-26 to present (141 statements to 2026-09 in the index: 3-8 a year in
2004-2009, six a year from 2010). The OPR was introduced in April 2004; the MPC was set up by
the Central Bank of Malaysia Act 2009.

Release-time rule (``published_at_utc``; zone ``Asia/Kuala_Lumpur``, UTC+8, no DST)
    Every statement header carries the embargo: "Not for publication or broadcast before 1500
    on Thursday, 3 November 2022". The adapter reads that time (1800 in the 2004, 2010 and 2016
    samples, 1500 in the 2020, 2022 and 2026 samples) and converts it from Kuala Lumpur time.
    The MPS of Nov 2022 also states the rule: "The Monetary Policy Statement will be released
    at 3 p.m. on the final day of each MPC meeting." If the header has no embargo time,
    ``published_at_utc`` is ``None``.

Untranslated pages: for 2005-12-15 and 2013-07-11 the Malay page only says "Artikel ini cuma
terdapat dalam Bahasa Inggeris buat masa sekarang." (English only); ``parse`` returns ``[]`` for
such placeholders, so those meetings have an English document only.

Cleaning: only paragraphs of the statement body are kept. The embargo header, signature block
("Bank Negara Malaysia <date>"), copyright line, schedule tables (and their captions) and
everything from a "See also" / "Lihat Juga" paragraph on are dropped. The old (2004-2009)
pages put a whole statement in one ``<p>`` separated by ``<br>`` pairs; those are split into
one section per paragraph.

Terms of use (https://www.bnm.gov.my/terms-of-use): "the entire contents of BNM website are
subject to copyright as a collective work" and "User shall not modify, publish, transmit,
participate in the transfer or sale, create derivative works, or in any way exploit or
reproduce, any of the content of BNM website, in whole or in part. User may download material
for User's personal use only, provided that it is not for the purpose of private or commercial
gain." Redistribution needs BNM's express written permission, so the text is not redistributable;
see docs/sources/bnm.md. robots.txt does not restrict these paths (no Crawl-delay).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from datetime import time as dtime
from typing import cast
from urllib.parse import quote
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Comment, Tag

from cbtone.schema import Document, Language, Section
from cbtone.sources.base import RawResponse, SourceAdapter

log = logging.getLogger(__name__)
BASE = "https://www.bnm.gov.my"
INDEX_PATH = "/monetary-stability/opr-decisions"
INDEX_PAGE_ID = 1515
STATEMENT_PAGE_ID = 182
KUALA_LUMPUR = ZoneInfo("Asia/Kuala_Lumpur")
FIRST_YEAR = 2004
LANG_IDS: dict[str, str] = {"en": "en_US", "ms": "ms_MY"}

_SLUG = re.compile(r"/-/monetary-policy-statement-(\d{2})(\d{2})(\d{4})(?![\d])")
_EMBARGO = re.compile(r"(\d{4})\s+(?:on|pada)\b", re.I)
_HEADER_DATE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*$")
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "mac": 3, "apr": 4, "may": 5, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "ogo": 8, "sep": 9, "oct": 10, "okt": 10, "nov": 11, "dec": 12,
    "dis": 12,
}  # fmt: skip
_PLACEHOLDER = re.compile(
    r"cuma terdapat dalam Bahasa Inggeris|only available in (?:Bahasa Malaysia|Malay)", re.I
)
_SEE_ALSO = re.compile(r"^(see also|lihat juga)\b", re.I)
_WS = re.compile(r"[ \t\r\f\v]+")


def _clean(text: str) -> str:
    return _WS.sub(" ", text.replace("\xa0", " ")).strip()


def update_language_url(path: str, language: str, page_id: int = STATEMENT_PAGE_ID) -> str:
    """URL that serves ``path`` in ``language`` (``en`` or ``ms``) regardless of cookies."""
    return (
        f"{BASE}/c/portal/update_language?p_l_id={page_id}"
        f"&redirect={quote(path, safe='')}&languageId={LANG_IDS[language]}"
    )


def release_time(d: date, hhmm: str) -> datetime:
    """UTC instant of an embargo time ``HHMM`` on date ``d`` in Kuala Lumpur."""
    return datetime.combine(d, dtime(int(hhmm[:2]), int(hhmm[2:])), tzinfo=KUALA_LUMPUR).astimezone(
        UTC
    )


def parallel_id(d: date) -> str:
    return f"bnm:{d.isoformat()}:statement"


class BNMAdapter(SourceAdapter):
    """See the module docstring for document types, URLs, eras, times and terms."""

    bank = "bnm"

    # -- discovery -----------------------------------------------------------
    @staticmethod
    def parse_index(html: str | bytes) -> Iterator[tuple[date, str]]:
        """Yield ``(decision_date, statement_path)`` from the OPR decisions table."""
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = a.get("href")
            m = _SLUG.search(href) if isinstance(href, str) else None
            if m is None:
                continue
            try:
                d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                continue
            yield d, f"/-/monetary-policy-statement-{m.group(1)}{m.group(2)}{m.group(3)}"

    def list_urls(self, start_year: int, end_year: int) -> Iterator[tuple[str, dict[str, str]]]:
        raw = self.fetcher.get(
            self.bank, update_language_url(INDEX_PATH, "en", page_id=INDEX_PAGE_ID)
        )
        entries = sorted(set(self.parse_index(raw.content)))
        for d, path in entries:
            if not max(start_year, FIRST_YEAR) <= d.year <= end_year:
                continue
            for lang in ("en", "ms"):
                yield (
                    update_language_url(path, lang),
                    {
                        "doc_type": "statement",
                        "date": d.isoformat(),
                        "language": lang,
                        "parallel_id": parallel_id(d),
                    },
                )

    # -- parsing -------------------------------------------------------------
    @staticmethod
    def _header_date(header: Tag) -> date | None:
        small = header.select_one("span.text-muted")
        m = _HEADER_DATE.search(_clean(small.get_text(" "))) if small else None
        month = _MONTHS.get(m.group(2)[:3].lower()) if m else None
        if m is None or month is None:
            return None
        return date(int(m.group(3)), month, int(m.group(1)))

    @staticmethod
    def _is_table_caption(el: Tag) -> bool:
        """Short paragraph directly before a table (a long one is statement text)."""
        if len(el.get_text()) > 150:
            return False
        nxt = el.find_next_sibling()
        return isinstance(nxt, Tag) and (nxt.name == "table" or nxt.find("table") is not None)

    @staticmethod
    def _paragraphs(el: Tag) -> list[str]:
        for br in el.find_all("br"):
            br.replace_with("\n")
        return [t for t in (_clean(x) for x in el.get_text().split("\n")) if t]

    def parse(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        soup = BeautifulSoup(raw.content, "lxml")
        # Some pages (e.g. 2008-10-24) carry a "Press Releases" listing asset before the
        # statement asset: pick the article that has the statement header.
        art = next(
            (a for a in soup.select(".journal-content-article") if a.select_one(".article-header")),
            None,
        )
        if art is None:
            log.warning("no statement article in %s", raw.url)
            return []
        for c in art.find_all(string=lambda t: isinstance(t, Comment)):
            c.extract()
        header = art.select_one(".article-header")
        title_el = header.find("h2") if header else None
        title = _clean(title_el.get_text(" ")) if title_el else hints.get("title", "")

        d: date | None = date.fromisoformat(hints["date"]) if hints.get("date") else None
        if d is None and header is not None:
            d = self._header_date(header)
        if d is None:
            return []
        em = _EMBARGO.search(header.get_text(" ")) if header else None
        published = release_time(d, em.group(1)) if em else None

        html_lang = soup.html.get("lang") if soup.html else None
        code = (html_lang if isinstance(html_lang, str) else hints.get("language", "en"))[:2]
        language = cast(Language, code if code in LANG_IDS else hints.get("language", "en"))

        sections: list[Section] = []
        for el in art.find_all(["p", "li", "h3", "h4", "h5"]):
            if not isinstance(el, Tag):
                continue
            if (
                el.find_parent("table") is not None
                or el.find_parent(class_="article-header") is not None
                or el.get("id") == "copy-pr"
                or (el.name == "p" and el.find_parent("li") is not None)
            ):
                continue
            first = _clean(el.get_text(" "))
            if _SEE_ALSO.match(first):
                break  # everything after "See also" is link lists
            if not first or first.startswith("©") or self._is_table_caption(el):
                continue
            for text in self._paragraphs(el):
                sections.append(Section(heading=None, text=text))
        if not sections:
            return []
        if len(sections) == 1 and _PLACEHOLDER.search(sections[0].text):
            log.warning("untranslated placeholder page %s", raw.url)
            return []
        return [
            Document(
                bank="bnm",
                date=d,
                published_at_utc=published,
                doc_type="statement",
                language=language,
                parallel_id=hints.get("parallel_id") or parallel_id(d),
                title=title,
                text="\n\n".join(s.text for s in sections),
                sections=sections,
                url=raw.url,
                sha256=raw.sha256,
                fetched_at=raw.fetched_at,
            )
        ]
