"""Monetary Authority of Singapore (MAS) adapter: Monetary Policy Statements, manual files.

Document types
    * ``mps``: the MAS Monetary Policy Statement (English only; ``language="en"``).

Status: BLOCKED for automated access. www.mas.gov.sg serves a "Maintenance" bot-protection
page (HTTP 200) to the cbtone fetcher (DECISIONS D7), so ``list_urls`` yields nothing and the
adapter reads pages that a human saved by hand into ``data/raw/mas/manual/`` (see
``docs/sources/NEEDED.md``). Nothing here gets around the block.

URL patterns (canonical, for reference)
    * Index: ``https://www.mas.gov.sg/monetary-policy/mas-monetary-policy-statements`` and
      ``/monetary-policy/past-monetary-policy-decisions``.
    * Statement: ``/news/monetary-policy-statements/YYYY/<slug>`` with slugs such as
      ``monetary-policy-statement-14-oct-10`` (to 2014), ``monetary-policy-statement-14oct15``
      (2015) and ``mas-monetary-policy-statement-13oct23`` (2016 on).

Date range: 2001 to present (semi-annual April/October from 2003, off-cycle statements
Oct 2001, Jan 2015, Mar 2020, Jan 2022 and Jan 2025, quarterly from 2024).

Manual-file conventions
    * File format: saved HTML ("save page as") or PDF. Anything else is ignored.
    * Date, in order: the file name (``mps-2023-10-13``, ``13oct23`` slug, ``14-oct-10`` slug),
      then the statement text ("Monetary Policy Statement ... 13 October 2023").
    * ``url``: ``<link rel=canonical>`` or ``og:url`` of the saved HTML if it is a mas.gov.sg
      URL, else derived from the slug (``/news/monetary-policy-statements/YYYY/<stem>``).
    * ``sha256`` is that of the file bytes; ``fetched_at`` is the file mtime in UTC.
    * ``published_at_utc`` is ``None`` (no documented release-time rule).

Terms of use (https://www.mas.gov.sg/terms-of-use): prior written permission from MAS is
required to reproduce, republish or distribute site content, apart from a personal,
non-commercial download of a single copy. Do not redistribute the text; see docs/sources/mas.md.
"""

from __future__ import annotations

import hashlib
import io
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from cbtone.schema import Document, Section
from cbtone.sources.base import PoliteFetcher, RawResponse, SourceAdapter

BASE = "https://www.mas.gov.sg"
MPS_PATH = "/news/monetary-policy-statements"
DEFAULT_MANUAL_DIR = Path("data/raw/mas/manual")
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_MONTH_NUM = {m: i + 1 for i, m in enumerate(_MONTHS)}
_MONTH_NUM.update({"sept": 9})

_ISO = re.compile(r"(?<!\d)(\d{4})[-_.](\d{2})[-_.](\d{2})(?!\d)")
_SLUG = re.compile(
    r"(?<![0-9a-z])(\d{1,2})[-_]?(" + "|".join(_MONTHS) + r")[-_]?(\d{2})(?![0-9])", re.I
)
_TEXT_DATE = re.compile(
    r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October"
    r"|November|December)\s+(\d{4})\b"
)
_WS = re.compile(r"\s+")
_DROP_TAGS = ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "button"]
_DROP_CLASS = re.compile(
    r"share|social|breadcrumb|cookie|related|print|skip|sidebar|feedback|last-?updated|nav", re.I
)
_BOILERPLATE = re.compile(
    r"^(share( this)?( page)?|print|skip to (main )?content|back to top|last updated.*"
    r"|download( pdf)?|related (links|content)|feedback)$",
    re.I,
)


def _clean(text: str) -> str:
    return _WS.sub(" ", text.replace("\xa0", " ")).strip()


def date_from_name(name: str) -> date | None:
    """Date from a file name / slug, or ``None``."""
    stem = Path(name).stem
    m = _ISO.search(stem)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = _SLUG.search(stem)
    if m:
        yy = int(m[3])
        try:
            return date(2000 + yy if yy < 90 else 1900 + yy, _MONTH_NUM[m[2].lower()], int(m[1]))
        except ValueError:
            return None
    return None


def date_from_text(text: str) -> date | None:
    """First ``D Month YYYY`` date in the opening of the text."""
    m = _TEXT_DATE.search(text[:3000])
    if not m:
        return None
    try:
        return date(int(m[3]), _MONTH_NUM[m[2][:3].lower()], int(m[1]))
    except ValueError:
        return None


def _slug_url(stem: str, d: date) -> str:
    return f"{BASE}{MPS_PATH}/{d.year}/{stem}"


class MasAdapter(SourceAdapter):
    """See the module docstring. Live discovery is disabled (blocked); use manual files."""

    bank = "mas"

    def __init__(self, fetcher: PoliteFetcher, manual_dir: Path = DEFAULT_MANUAL_DIR) -> None:
        super().__init__(fetcher)
        self.manual_dir = manual_dir

    # -- discovery -----------------------------------------------------------
    def list_urls(self, start_year: int, end_year: int) -> Iterator[tuple[str, dict[str, str]]]:
        """Nothing live: MAS is blocked (D7). Use ``load_manual``."""
        return iter(())

    def fetch(self, start_year: int, end_year: int) -> Iterator[Document]:
        for doc in self.load_manual(self.manual_dir):
            if start_year <= doc.date.year <= end_year:
                yield doc

    def load_manual(self, dir: Path | None = None) -> Iterator[Document]:
        d = dir if dir is not None else self.manual_dir
        if not d.is_dir():
            return
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in (".html", ".htm", ".pdf") or not p.is_file():
                continue
            raw = RawResponse(
                url=p.name,  # parse() derives the canonical/slug URL
                content=p.read_bytes(),
                content_type="application/pdf" if p.suffix.lower() == ".pdf" else "text/html",
                sha256="",
                fetched_at=datetime.fromtimestamp(p.stat().st_mtime, tz=UTC),
                from_cache=True,
            )
            yield from self.parse(raw, {"doc_type": "mps", "language": "en", "filename": p.name})

    # -- parsing -------------------------------------------------------------
    def parse(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        name = hints.get("filename") or raw.url.rsplit("/", 1)[-1]
        sha = raw.sha256 or hashlib.sha256(raw.content).hexdigest()
        is_pdf = (
            raw.content_type.lower().startswith("application/pdf") or raw.content[:5] == b"%PDF-"
        )
        canonical: str | None = None
        if is_pdf:
            title, sections = self._pdf_sections(raw.content)
        else:
            title, sections, canonical = self._html_sections(raw.content)
        if not sections:
            return []
        text = "\n\n".join(s.text for s in sections)
        d: date | None = None
        if hints.get("date"):
            d = date.fromisoformat(hints["date"])
        d = d or date_from_name(name) or (date_from_name(canonical) if canonical else None)
        d = d or date_from_text(title + "\n" + text)
        if d is None:
            return []
        stem = Path(name).stem
        url = canonical or (raw.url if raw.url.startswith("http") else _slug_url(stem, d))
        return [
            Document(
                bank="mas",
                date=d,
                published_at_utc=None,
                doc_type="mps",
                language="en",
                title=title or f"MAS Monetary Policy Statement - {d:%B %Y}",
                text=text,
                sections=sections,
                url=url,
                sha256=sha,
                fetched_at=raw.fetched_at,
            )
        ]

    @staticmethod
    def _html_sections(content: bytes) -> tuple[str, list[Section], str | None]:
        soup = BeautifulSoup(content, "lxml")
        canonical: str | None = None
        link = soup.find("link", rel="canonical")
        cands = [link.get("href") if isinstance(link, Tag) else None]
        og = soup.find("meta", property="og:url")
        cands.append(og.get("content") if isinstance(og, Tag) else None)
        for c in cands:
            if isinstance(c, str) and re.match(r"https?://(www\.)?mas\.gov\.sg/", c):
                canonical = c.split("?")[0].split("#")[0]
                break
        h1 = soup.find("h1")
        title = _clean(h1.get_text(" ")) if isinstance(h1, Tag) else ""
        if not title:
            ogt = soup.find("meta", property="og:title")
            title = _clean(str(ogt.get("content", ""))) if isinstance(ogt, Tag) else ""
        if not title and soup.title:
            title = _clean(soup.title.get_text(" "))
        for t in soup.find_all(_DROP_TAGS):
            t.decompose()
        for t in soup.find_all(True):
            if not isinstance(t, Tag) or t.attrs is None:
                continue
            cls = " ".join(t.get("class") or []) + " " + str(t.get("id") or "")
            if _DROP_CLASS.search(cls) and t.name not in ("html", "body", "main", "article"):
                t.decompose()
        root = soup.find("main") or soup.find("article") or soup.body or soup
        sections: list[Section] = []
        heading: str | None = None
        for el in root.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
            if not isinstance(el, Tag):
                continue
            if el.name == "p" and el.find_parent("li"):
                continue
            if el.name == "li" and el.find(["li", "p"]):
                continue
            text = _clean(el.get_text(" "))
            if not text or _BOILERPLATE.match(text):
                continue
            if el.name == "h1":
                continue
            if el.name in ("h2", "h3", "h4"):
                heading = text
                continue
            sections.append(Section(heading=heading, text=text))
        return title, sections, canonical

    @staticmethod
    def _pdf_sections(content: bytes) -> tuple[str, list[Section]]:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        paras = [_clean(p) for p in re.split(r"\n\s*\n", text)]
        paras = [p for p in paras if p and not re.fullmatch(r"\d{1,3}", p)]
        if len(paras) < 2:  # no blank lines: treat each line as a block
            paras = [_clean(p) for p in text.splitlines() if _clean(p)]
        title = paras[0] if paras else ""
        return title, [Section(text=p) for p in paras[1:]]
