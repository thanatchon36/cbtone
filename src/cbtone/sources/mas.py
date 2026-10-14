"""Monetary Authority of Singapore (MAS) adapter: Monetary Policy Statements.

Document types
    * ``mps``: the MAS Monetary Policy Statement (English only; ``language="en"``).

Modes (DECISIONS D7, D11)
    * www.mas.gov.sg itself serves a "Maintenance" bot-protection page (HTTP 200) to the cbtone
      fetcher, so this adapter NEVER requests mas.gov.sg. Nothing here gets around the block.
    * Manual files: pages a human saved by hand into ``data/raw/mas/manual/`` (see
      ``docs/sources/NEEDED.md``). They are loaded first and take precedence.
    * Internet Archive (author-approved, D11): for statements not covered by manual files, the
      Wayback CDX API lists archived statement URLs and the raw snapshot
      ``https://web.archive.org/web/<ts>id_/<mas url>`` is fetched, all through ``PoliteFetcher``
      (robots.txt, 2 s interval, cache, block-page rejection). A capture is accepted only if it is
      a statement page whose parsed date equals the date in its slug (if the text has no
      day, the month and year in the title must match); maintenance-page captures are
      skipped and the next-older/next-newer capture of that URL (CDX ``collapse=digest``) is tried.
      ``Document.url`` is the snapshot URL.

URL patterns (canonical, for reference)
    * Index: ``https://www.mas.gov.sg/monetary-policy/mas-monetary-policy-statements`` and
      ``/monetary-policy/past-monetary-policy-decisions``.
    * Statement: ``/news/monetary-policy-statements/YYYY/<slug>`` with slugs such as
      ``monetary-policy-statement-14-oct-10`` (to 2014), ``monetary-policy-statement-14oct15``
      (2015) and ``mas-monetary-policy-statement-13oct23`` (2016 on).

    * Older layout (2012-2013 captures): ``/News-and-Publications/
      Monetary-Policy-Statements-and-Speeches/YYYY/Monetary-Policy-Statement-12Oct12.aspx``
      (also lower-case and ``/en/`` variants).

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
import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx
from bs4 import BeautifulSoup, Tag

from cbtone.schema import Document, Section
from cbtone.sources.base import BlockedError, PoliteFetcher, RawResponse, SourceAdapter

BASE = "https://www.mas.gov.sg"
MPS_PATH = "/news/monetary-policy-statements"
DEFAULT_MANUAL_DIR = Path("data/raw/mas/manual")
WAYBACK = "https://web.archive.org"
CDX_URL = f"{WAYBACK}/cdx/search/cdx"
CDX_PREFIXES = (
    "www.mas.gov.sg/news/monetary-policy-statements/",
    "mas.gov.sg/news/monetary-policy-statements/",
    "www.mas.gov.sg/news-and-publications/monetary-policy-statements",
    "www.mas.gov.sg/en/news-and-publications/monetary-policy-statements",
)
MAX_ALTERNATIVES = 8
log = logging.getLogger(__name__)
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_MONTH_NUM = {m: i + 1 for i, m in enumerate(_MONTHS)}
_MONTH_NUM.update({"sept": 9})

_ISO = re.compile(r"(?<!\d)(\d{4})[-_.](\d{2})[-_.](\d{2})(?!\d)")
_SLUG = re.compile(
    r"(?<![0-9a-z])(\d{1,2})[-_]?(" + "|".join(_MONTHS) + r")[-_]?(\d{4}|\d{2})(?![0-9])", re.I
)
# Statement URLs: current layout and the 2012-13 ".aspx" layout (scheme/port/case-insensitive).
_URL_NEW = re.compile(
    r"^https?://(?:www\.)?mas\.gov\.sg(?::80)?/news/monetary-policy-statements/(\d{4})/"
    r"([a-z0-9-]+)/?$",
    re.I,
)
_URL_OLD = re.compile(
    r"^https?://(?:www\.)?mas\.gov\.sg(?::80)?/(?:en/)?news-and-publications/"
    r"monetary-policy-statements-and-speeches/(\d{4})/(monetary-policy-statement-[a-z0-9]+)"
    r"(?:\.aspx)?/?$",
    re.I,
)
_TEXT_DATE = re.compile(
    r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October"
    r"|November|December)\s+(\d{4})\b"
)
_TITLE_MONTH = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November"
    r"|December)\s+(\d{4})\b"
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
        if len(m[3]) == 2:
            yy += 2000 if yy < 90 else 1900
        try:
            return date(yy, _MONTH_NUM[m[2].lower()], int(m[1]))
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


@dataclass(frozen=True)
class Capture:
    """One Wayback capture of a MAS statement URL."""

    timestamp: str
    original: str
    date: date  # statement date from the slug

    @property
    def stem(self) -> str:
        return self.original.rstrip("/").rsplit("/", 1)[-1].removesuffix(".aspx")

    @property
    def snapshot_url(self) -> str:
        return f"{WAYBACK}/web/{self.timestamp}id_/{self.original}"


def statement_date(original: str) -> date | None:
    """Slug date if ``original`` is a MAS statement URL (index/listing pages give ``None``)."""
    m = _URL_NEW.match(original) or _URL_OLD.match(original)
    if not m:
        return None
    d = date_from_name(m[2])
    return d if d is not None and d.year == int(m[1]) else None


def parse_cdx(content: bytes) -> list[dict[str, str]]:
    """Rows of a CDX ``output=json`` response (first row is the header; empty body = no rows)."""
    text = content.decode("utf-8", errors="replace").strip()
    if not text:
        return []
    rows = json.loads(text)
    if not rows:
        return []
    head = rows[0]
    return [dict(zip(head, r, strict=False)) for r in rows[1:]]


def _cdx_query(url: str, **extra: str) -> str:
    q = {
        "url": url,
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype",
        "filter": "statuscode:200",
        **extra,
    }
    return f"{CDX_URL}?{urlencode(q, safe=':,/', quote_via=quote)}"


class MasAdapter(SourceAdapter):
    """See the module docstring. Manual files first, then Internet Archive copies (D11)."""

    bank = "mas"

    def __init__(
        self,
        fetcher: PoliteFetcher,
        manual_dir: Path = DEFAULT_MANUAL_DIR,
        use_archive: bool = True,
    ) -> None:
        super().__init__(fetcher)
        self.manual_dir = manual_dir
        self.use_archive = use_archive
        self.skipped: list[tuple[str, str]] = []  # (snapshot URL, reason)

    # -- discovery -----------------------------------------------------------
    def _candidates(self, start_year: int, end_year: int) -> dict[date, list[Capture]]:
        """Archived statement URLs by statement date (latest capture of each distinct URL).

        New-layout URLs come before the old ``.aspx`` layout for the same date.
        """
        found: dict[str, Capture] = {}
        for prefix in CDX_PREFIXES:
            raw = self.fetcher.get(
                self.bank, _cdx_query(prefix, matchType="prefix", collapse="urlkey")
            )
            for row in parse_cdx(raw.content):
                orig = row.get("original", "")
                d = statement_date(orig)
                if d is None or not (start_year <= d.year <= end_year):
                    continue
                if not row.get("mimetype", "text/html").startswith(
                    ("text/html", "application/pdf")
                ):
                    continue
                key = re.sub(r"^https?://(www\.)?|:80", "", orig.lower()).rstrip("/")
                key = key.removesuffix(".aspx").replace("/en/news-and", "/news-and")
                cap = Capture(row["timestamp"], orig, d)
                if key not in found or cap.timestamp > found[key].timestamp:
                    found[key] = cap
        out: dict[date, list[Capture]] = {}
        for cap in sorted(found.values(), key=lambda c: (c.date, "/news/" not in c.original)):
            out.setdefault(cap.date, []).append(cap)
        return out

    def _alternatives(self, cap: Capture) -> list[Capture]:
        """Other captures of the same URL (distinct content), next-older first, then newer."""
        raw = self.fetcher.get(
            self.bank, _cdx_query(cap.original, matchType="exact", collapse="digest")
        )
        ts = sorted(
            {r["timestamp"] for r in parse_cdx(raw.content) if r.get("timestamp")} - {cap.timestamp}
        )
        older = [t for t in reversed(ts) if t < cap.timestamp]
        newer = [t for t in ts if t > cap.timestamp]
        return [Capture(t, cap.original, cap.date) for t in (older + newer)[:MAX_ALTERNATIVES]]

    def list_urls(self, start_year: int, end_year: int) -> Iterator[tuple[str, dict[str, str]]]:
        """Snapshot URL of the latest capture of each archived statement URL in range."""
        for d, caps in self._candidates(start_year, end_year).items():
            for c in caps:
                yield (
                    c.snapshot_url,
                    {
                        "doc_type": "mps",
                        "language": "en",
                        "filename": c.stem,
                        "date": d.isoformat(),
                        "original": c.original,
                    },
                )

    def fetch(self, start_year: int, end_year: int) -> Iterator[Document]:
        have: set[date] = set()
        for doc in self.load_manual(self.manual_dir):
            if start_year <= doc.date.year <= end_year:
                have.add(doc.date)
                yield doc
        if not self.use_archive:
            return
        for d, caps in self._candidates(start_year, end_year).items():
            if d in have:
                continue
            archived = self._first_good(caps)
            if archived is not None:
                have.add(d)
                yield archived

    def _first_good(self, caps: list[Capture]) -> Document | None:
        for cap in caps:  # distinct URLs for the same statement date
            tried = [cap]
            i = 0
            while i < len(tried):
                doc = self._try_capture(tried[i])
                if doc is not None:
                    return doc
                if i == 0:  # primary capture failed: look up the alternatives once
                    tried += self._alternatives(cap)
                i += 1
        return None

    def _try_capture(self, cap: Capture) -> Document | None:
        url = cap.snapshot_url
        try:
            raw = self.fetcher.get(self.bank, url)
        except BlockedError as e:
            if "interstitial" not in str(e):
                raise  # robots.txt or HTTP 401/403/429: stop, do not work around
            self.skipped.append((url, "maintenance/bot page"))
            return None
        except httpx.HTTPError as e:
            self.skipped.append((url, f"http error: {e}"))
            return None
        hints = {
            "doc_type": "mps",
            "language": "en",
            "filename": cap.stem,
            "date": cap.date.isoformat(),
            "url": url,
        }
        docs = self.parse(raw, hints)
        if not docs:
            self.skipped.append((url, "not a statement (no text)"))
            return None
        doc = docs[0]
        found = date_from_text(doc.title + "\n" + doc.text)
        if found is None:  # e.g. Apr 2008: no day in the text; the title says "April 2008"
            ym = _TITLE_MONTH.search(doc.title)
            if ym:
                found = date(int(ym[2]), _MONTH_NUM[ym[1][:3].lower()], cap.date.day)
        if found != cap.date:
            self.skipped.append((url, f"date mismatch: slug {cap.date}, page {found}"))
            return None
        return doc

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
        url = (
            hints.get("url")
            or canonical
            or (raw.url if raw.url.startswith("http") else _slug_url(stem, d))
        )
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
