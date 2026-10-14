"""People's Bank of China (PBoC) adapter: Monetary Policy Committee (MPC) communiqués.

Document types
    * ``communique``: 中国人民银行货币政策委员会召开YYYY年第N季度例会 (zh) and "PBOC Monetary
      Policy Committee Holds QN YYYY Meeting" (en, 2023 on), one per meeting and language.

Modes (DECISIONS D10, D12)
    * www.pbc.gov.cn disallows every crawler except Baiduspider in robots.txt, so this adapter
      NEVER requests pbc.gov.cn. Nothing here gets around that.
    * Manual files: pages a human saved into ``data/raw/pboc/manual/``
      (``<meeting-date>_<zh|en>.html``, see ``docs/sources/NEEDED.md``). They are loaded first
      and take precedence.
    * Internet Archive (author-approved, D12): the Wayback CDX API lists archived communiqué
      URLs and the raw snapshot ``https://web.archive.org/web/<timestamp>id_/<pbc url>`` is
      fetched, all through ``PoliteFetcher`` (robots.txt, rate limit, cache, block-page
      rejection). ``Document.url`` is the snapshot URL; the original pbc.gov.cn URL is
      recoverable from it.

Where the communiqués lived (verified against archived pages, 2026-10-14)
    * 2009 - Apr 2015: ``/publish/huobizhengceersi/3141/<year>/<id>/<id>_.html`` (货币政策
      委员会 > 例会). Body in ``<font id=zoom>``; release time ``YYYY-MM-DD HH:MM:SS`` in the
      header row.
    * May 2015 - 2017: the news column ``/goutongjiaoliu/113456/113469/<id>/index.html``.
      Found only through archived copies of that column's front page (links whose text names
      the communiqué). Body in ``<div id=zoom>``.
    * 2017Q4 on: ``/zhengcehuobisi/125207/3870933/3870936/<id-or-hash>/index.html`` (例会信息).
    * en, 2023 on: ``/en/3688229/3688311/3688329/<id>/index.html`` (MPC Meetings; body in
      ``div.gitop``) and copies in the en news column ``/en/3688110/3688172/``. The archive
      has no older English communiqués.
    Many 2016-2022 captures are anti-bot JavaScript shells (no article text); they are skipped.

Parsing rules
    * Meeting identity: (year, quarter) from the title ("2012年第一季度例会", "Q2 2023").
    * Meeting date: from the text ("例会于4月7日在北京召开", "On June 28, ..."). Pages that only
      say "日前在北京召开" (2009 - 2015) give no day; then the date the page itself states for
      its release is used (within days of the meeting). Never the capture timestamp. A date
      outside the quarter (plus 60 days) rejects the capture.
    * The same pages are dated more exactly from PBoC's own table "货币政策委员会例会召开时间
      (1997年至今)" (archived copy, ``CHRONOLOGY``), when it covers the meeting: the release
      date can trail the meeting by days (2012Q1: met 29 Mar, released 31 Mar).
    * ``published_at_utc``: the release time the zh page states (Asia/Shanghai, UTC+8, no DST),
      else ``None`` (en pages state none).
    * ``parallel_id`` = ``pboc:<year>Q<n>:communique``, shared by the zh and en text of a
      meeting.
    * Encoding: meta charset, then UTF-8, then GB18030 (GBK/GB2312 superset).

Acceptance (D12): captures that are block/empty/shell pages, non-communiqués, or whose date
does not fit the title are skipped and the next capture of the same URL is tried; documents
are de-duplicated by (meeting date, language) and by (year-quarter, language);
``start_year``/``end_year`` apply to the meeting date.

Terms of use: not verified (docs/sources/pboc.md), so the text is treated as not
redistributable (URL + SHA-256 only).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode, urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from cbtone.schema import Document, Language, Section
from cbtone.sources.base import BlockedError, PoliteFetcher, RawResponse, SourceAdapter

MANUAL_DIR = Path("data/raw/pboc/manual")
WAYBACK = "https://web.archive.org"
CDX_URL = f"{WAYBACK}/cdx/search/cdx"
HOST = "www.pbc.gov.cn"
CST = timezone(timedelta(hours=8), "Asia/Shanghai")
CHRONOLOGY = f"{HOST}/huobizhengceersi/214481/214543/218247/2847968/index.html"
MAX_ALTERNATIVES = 8
MAX_LIST_CAPTURES = 130
MIN_LIST_LENGTH = 5000  # CDX (compressed) length below this is a JS shell / empty index page
log = logging.getLogger(__name__)

# Article-bearing directories, per language.
PREFIXES: dict[str, tuple[str, ...]] = {
    "zh": (
        f"{HOST}/publish/huobizhengceersi/3141/",
        f"{HOST}/zhengcehuobisi/125207/3870933/3870936/",
    ),
    "en": (f"{HOST}/en/3688229/3688311/3688329/",),
}
# Column front pages whose archived copies link to communiqués outside PREFIXES.
LIST_PAGES: dict[str, tuple[str, ...]] = {
    "zh": (f"{HOST}/goutongjiaoliu/113456/113469/index.html",),
    "en": (f"{HOST}/en/3688110/3688172/index.html", f"{HOST}/en/3688110/3688172/5552468/"),
}
_LINK_TEXT = {
    "zh": re.compile(r"货币政策委员会召开\d{4}年第[一二三四]季度例会"),
    "en": re.compile(r"Monetary Policy Committee Holds Q[1-4] \d{4} Meeting", re.I),
}
_ARTICLE_REST = re.compile(r"^(?:[^/?]+/(?:index\.html)?|\d{4}/[^/]+/[^/]+_\.html)$")
_REST_YEAR = re.compile(r"^(\d{4})/")

_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(zh|en)\.html?$")
_QNUM = {"一": 1, "二": 2, "三": 3, "四": 4}
_ZH_IDENT = re.compile(r"(\d{4})年第([一二三四])季度")
_ZH_DAY = re.compile(r"例会于\s*(\d{1,2})月\s*(\d{1,2})日")
_EN_TITLE = re.compile(r"\bQ([1-4])\s+(\d{4})\b")
_EN_BODY = re.compile(r"(first|second|third|fourth) quarterly meeting of (\d{4})", re.I)
_EN_DAY = re.compile(
    r"\b[Oo]n\s+(January|February|March|April|May|June|July|August|September|October|November"
    r"|December)\s+(\d{1,2})\b"
)
_EN_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_MONTH_NAMES = (
    "January February March April May June July August September October November December"
)
_MONTHS = {m: i + 1 for i, m in enumerate(_MONTH_NAMES.split())}
_STAMP = re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?:[ T]+(\d{2}):(\d{2})(?::(\d{2}))?)?(?!\d)")
_CHARSET = re.compile(rb"charset\s*=\s*[\"']?\s*([\w-]+)", re.I)
_WS = re.compile(r"[ \t\r\n　\xa0]+")
_CJK_GAP = re.compile(r"(?<=[　-〿一-鿿＀-￯])\s+(?=[　-〿一-鿿＀-￯])")
_NOISE = ("打印本页", "关闭窗口", "字号", "责任编辑", "分享到")


def _decode(content: bytes) -> str:
    """meta charset first (GB2312/GBK/GB18030 -> gb18030), then UTF-8, then GB18030."""
    if content.startswith(b"\xef\xbb\xbf"):
        return content[3:].decode("utf-8", errors="replace")
    m = _CHARSET.search(content[:4096])
    declared = m.group(1).decode("ascii", "ignore").lower() if m else ""
    order = ("gb18030", "utf-8") if declared.startswith("gb") else ("utf-8", "gb18030")
    for enc in order:
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def parse_cdx(content: bytes) -> list[dict[str, str]]:
    """Rows of a CDX ``output=json`` response (header row first; empty body = no rows)."""
    text = content.decode("utf-8", errors="replace").strip()
    if not text:
        return []
    rows = json.loads(text)
    if not rows:
        return []
    return [dict(zip(rows[0], r, strict=False)) for r in rows[1:]]


def _cdx_query(url: str, **extra: str) -> str:
    q = {
        "url": url,
        "output": "json",
        "fl": "timestamp,original,mimetype,length",
        "filter": "statuscode:200",
        "collapse": "digest",
        **extra,
    }
    return f"{CDX_URL}?{urlencode(q, safe=':,/', quote_via=quote)}"


def canonical_key(original: str, *, index: bool = True) -> str:
    """Scheme/port/``www.``/query/double-slash-insensitive identity of a pbc.gov.cn URL.

    A directory URL becomes ``.../index.html`` unless ``index`` is false (used for prefixes).
    """
    u = re.sub(r"^https?://", "", original.strip(), flags=re.I).split("?")[0].split("#")[0]
    host, _, rest = u.partition("/")
    host = host.lower().removeprefix("www.").removesuffix(":80").removesuffix(":443")
    rest = re.sub(r"/{2,}", "/", "/" + rest)
    if rest.endswith("/") and index:
        rest += "index.html"
    return host + rest


def snapshot_url(timestamp: str, original: str) -> str:
    return f"{WAYBACK}/web/{timestamp}id_/{original}"


@dataclass(frozen=True)
class Capture:
    timestamp: str
    original: str
    length: int = 0

    @property
    def snapshot_url(self) -> str:
        return snapshot_url(self.timestamp, self.original)


@dataclass
class Candidate:
    lang: str
    key: str
    captures: list[Capture]  # newest first


def _quarter_window(year: int, q: int) -> tuple[date, date]:
    start = date(year, 3 * q - 2, 1)
    end = date(year + (q == 4), 1 if q == 4 else 3 * q + 1, 1) - timedelta(days=1)
    return start, end + timedelta(days=60)


def _identity(title: str, text: str, lang: str) -> tuple[int, int] | None:
    """(year, quarter) the title names, or ``None`` if this is not an MPC regular-meeting page."""
    if lang == "zh":
        if "例会" not in title or "货币政策委员会" not in title.replace(" ", ""):
            return None
        m = _ZH_IDENT.search(title)
        return (int(m[1]), _QNUM[m[2]]) if m else None
    m2 = _EN_TITLE.search(title)
    if m2 and "Monetary Policy Committee" in title:
        return int(m2[2]), int(m2[1])
    m3 = _EN_BODY.search(text[:600])
    if m3 and "Monetary Policy Committee" in (title + text[:300]):
        return int(m3[2]), _EN_ORD[m3[1].lower()]
    return None


def _page_stamp(soup: BeautifulSoup) -> tuple[date, datetime | None] | None:
    """Release date (and time, if given) the page states outside its body."""
    el = soup.find(id="shijian")
    texts = [el.get_text(" ")] if isinstance(el, Tag) else []
    texts.append(soup.get_text(" "))
    for text in texts:
        for m in _STAMP.finditer(text):
            try:
                d = date(int(m[1]), int(m[2]), int(m[3]))
                when = (
                    datetime(
                        d.year, d.month, d.day, int(m[4]), int(m[5]), int(m[6] or 0), tzinfo=CST
                    )
                    if m[4]
                    else None
                )
            except ValueError:
                continue
            return d, when
    return None


def parse_chronology(html: str) -> dict[tuple[int, int], date]:
    """{(year, quarter): meeting date} from PBoC's 例会召开时间 table (columns = quarters)."""
    zoom = BeautifulSoup(html, "lxml").find(id="zoom")
    out: dict[tuple[int, int], date] = {}
    for tr in zoom.find_all("tr") if isinstance(zoom, Tag) else []:
        cells = [re.sub(r"\s+", "", td.get_text()) for td in tr.find_all("td")]
        y = re.fullmatch(r"(\d{4})年", cells[0]) if cells else None
        if not y:
            continue
        for q, cell in enumerate(cells[1:5], start=1):
            m = re.fullmatch(r"(\d{1,2})月(\d{1,2})日", cell)
            if m:
                try:
                    out[(int(y[1]), q)] = date(int(y[1]), int(m[1]), int(m[2]))
                except ValueError:
                    continue
    return out


def _meeting_date(
    lang: str,
    ident: tuple[int, int] | None,
    text: str,
    stamp: date | None,
    hint_iso: str,
    table: date | None = None,
) -> date:
    year = ident[0] if ident else date.fromisoformat(hint_iso).year
    head = text[:800]
    try:
        if lang == "zh":
            m = _ZH_DAY.search(head)
            if m:
                return date(year, int(m[1]), int(m[2]))
        else:
            e = _EN_DAY.search(head)
            if e:
                d = date(year, _MONTHS[e[1]], int(e[2]))
                if ident and ident[1] == 4 and d.month <= 2:  # Q4 meeting reported the next Jan
                    d = d.replace(year=year + 1)
                return d
    except ValueError:
        pass
    return table or stamp or date.fromisoformat(hint_iso)


class PbocAdapter(SourceAdapter):
    """See the module docstring. Manual files first, then Internet Archive copies (D12)."""

    bank = "pboc"

    def __init__(
        self,
        fetcher: PoliteFetcher,
        manual_dir: Path = MANUAL_DIR,
        use_archive: bool = True,
    ) -> None:
        super().__init__(fetcher)
        self.manual_dir = manual_dir
        self.use_archive = use_archive
        self.skipped: list[tuple[str, str]] = []  # (snapshot URL, reason)
        self.chronology: dict[tuple[int, int], date] = {}  # filled by fetch() from the archive

    def load_chronology(self) -> dict[tuple[int, int], date]:
        """Meeting dates from the newest archived capture of PBoC's 例会召开时间 table."""
        caps = [
            c
            for r in self._cdx(CHRONOLOGY, matchType="exact")
            if (c := self._capture(r)) is not None
        ]
        for cap in sorted(caps, key=lambda c: c.timestamp, reverse=True):
            raw = self._get(cap.snapshot_url)
            table = parse_chronology(_decode(raw.content)) if raw is not None else {}
            if len(table) >= 10:
                self.chronology = table
                break
        return self.chronology

    # -- discovery -----------------------------------------------------------
    def _cdx(self, url: str, **extra: str) -> list[dict[str, str]]:
        try:
            return parse_cdx(self.fetcher.get(self.bank, _cdx_query(url, **extra)).content)
        except FileNotFoundError:  # offline and never cached
            return []

    @staticmethod
    def _capture(row: dict[str, str]) -> Capture | None:
        mt = row.get("mimetype", "text/html")
        if not mt.startswith("text/html") or not row.get("timestamp") or not row.get("original"):
            return None
        length = row.get("length", "0")
        return Capture(row["timestamp"], row["original"], int(length) if length.isdigit() else 0)

    def _harvest(self, lang: str, start_year: int, end_year: int) -> dict[str, str]:
        """Original URLs of communiqués linked from archived column front pages (key -> URL)."""
        out: dict[str, str] = {}
        for page in LIST_PAGES[lang]:
            caps = [
                c
                for r in self._cdx(page, matchType="exact")
                if (c := self._capture(r)) is not None and c.length >= MIN_LIST_LENGTH
            ]
            for cap in sorted(caps, key=lambda c: c.timestamp, reverse=True)[:MAX_LIST_CAPTURES]:
                raw = self._get(cap.snapshot_url)
                if raw is None:
                    continue
                soup = BeautifulSoup(_decode(raw.content), "lxml")
                for a in soup.find_all("a", href=True):
                    label = f"{a.get('title', '')} {a.get_text()}"
                    text = _WS.sub("", label) if lang == "zh" else _WS.sub(" ", label)
                    if not _LINK_TEXT[lang].search(text.strip()):
                        continue
                    ident = _identity(text.strip(), "", lang)
                    if ident and not start_year <= ident[0] <= end_year:
                        continue
                    url = urljoin(cap.original, str(a["href"]))
                    if HOST in url:
                        out.setdefault(canonical_key(url), url)
        return out

    def _candidates(self, start_year: int, end_year: int) -> list[Candidate]:
        found: dict[tuple[str, str], list[Capture]] = {}
        for lang, prefixes in PREFIXES.items():
            for prefix in prefixes:
                base = canonical_key(prefix, index=False)
                for row in self._cdx(prefix, matchType="prefix"):
                    cap = self._capture(row)
                    if cap is None:
                        continue
                    key = canonical_key(cap.original)
                    rest = key.removeprefix(base)
                    if not key.startswith(base) or not _ARTICLE_REST.match(rest):
                        continue
                    ym = _REST_YEAR.match(rest)
                    if ym and not start_year - 1 <= int(ym[1]) <= end_year + 1:
                        continue
                    found.setdefault((lang, key), []).append(cap)
        for lang in LIST_PAGES:
            for key, url in self._harvest(lang, start_year, end_year).items():
                if (lang, key) in found:
                    continue
                caps = [
                    c
                    for r in self._cdx(url, matchType="exact")
                    if (c := self._capture(r)) is not None
                ]
                if caps:
                    found[(lang, key)] = caps
        return [
            Candidate(lang, key, sorted(caps, key=lambda c: c.timestamp, reverse=True))
            for (lang, key), caps in sorted(found.items())
        ]

    def _manual(self, start_year: int, end_year: int) -> Iterator[tuple[str, dict[str, str]]]:
        if not self.manual_dir.is_dir():
            return
        for p in sorted(self.manual_dir.iterdir()):
            m = _NAME.match(p.name)
            if not m or not start_year <= int(m.group(1)[:4]) <= end_year:
                continue
            iso, lang = m.groups()
            yield (
                p.resolve().as_uri(),
                {
                    "doc_type": "communique",
                    "date": iso,
                    "language": lang,
                    "parallel_id": f"pboc:{iso}:communique",
                    "source": "manual",
                },
            )

    def list_urls(self, start_year: int, end_year: int) -> Iterator[tuple[str, dict[str, str]]]:
        """Manual files, then the newest archived capture of each candidate communiqué URL.

        Archive hints carry no ``date`` (it is only known after parsing); ``alternatives`` lists the
        other capture URLs, newest first.
        """
        yield from self._manual(start_year, end_year)
        if not self.use_archive:
            return
        for c in self._candidates(start_year, end_year):
            yield (
                c.captures[0].snapshot_url,
                {
                    "doc_type": "communique",
                    "language": c.lang,
                    "source": "archive",
                    "original": c.captures[0].original,
                    "alternatives": "\n".join(x.snapshot_url for x in c.captures[1:]),
                },
            )

    # -- fetching ------------------------------------------------------------
    def _get(self, url: str) -> RawResponse | None:
        try:
            return self.fetcher.get(self.bank, url)
        except BlockedError as e:
            if "interstitial" not in str(e):
                raise  # robots.txt or HTTP 401/403/429: stop, do not work around
            self.skipped.append((url, "block/interstitial page"))
        except httpx.HTTPError as e:
            self.skipped.append((url, f"http error: {e}"))
        except FileNotFoundError:  # offline run and never cached
            self.skipped.append((url, "offline: not cached"))
        return None

    def fetch(self, start_year: int, end_year: int) -> Iterator[Document]:
        seen: set[tuple[object, str]] = set()

        def new(doc: Document) -> bool:
            ident = doc.parallel_id or doc.date.isoformat()
            keys = {(doc.date, doc.language), (ident, doc.language)}
            if keys & seen:
                return False
            seen.update(keys)
            return True

        for url, hints in self._manual(start_year, end_year):
            content = Path(url.removeprefix("file://")).read_bytes()
            raw = RawResponse(
                url=url,
                content=content,
                content_type="text/html",
                sha256=hashlib.sha256(content).hexdigest(),
                fetched_at=datetime.now(UTC),
                from_cache=True,
            )
            for doc in self.parse(raw, hints):
                if start_year <= doc.date.year <= end_year and new(doc):
                    yield doc
        if not self.use_archive:
            return
        self.load_chronology()
        for cand in self._candidates(start_year, end_year):
            found = self._first_good(cand)
            if found is not None and start_year <= found.date.year <= end_year and new(found):
                yield found

    def _first_good(self, cand: Candidate) -> Document | None:
        for cap in cand.captures[: 1 + MAX_ALTERNATIVES]:
            url = cap.snapshot_url
            raw = self._get(url)
            if raw is None:
                continue
            docs = self.parse(
                raw, {"doc_type": "communique", "language": cand.lang, "source": "archive"}
            )
            if docs:
                return docs[0]
            self.skipped.append((url, "not a communiqué / empty or shell page / date mismatch"))
        return None

    # -- parsing -------------------------------------------------------------
    def parse(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        lang_code = hints.get("language", "zh")
        lang: Language = "zh" if lang_code == "zh" else "en"
        manual = hints.get("source") == "manual"
        soup = BeautifulSoup(_decode(raw.content), "lxml")
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        body = (
            soup.find(id="zoom")
            or soup.select_one("div.gitop")
            or soup.find(class_="TRS_Editor")
            or (soup.body if manual else None)
        )
        if not isinstance(body, Tag):
            return []
        h = soup.find("h2")
        title = (
            _WS.sub(" ", h.get_text(" ", strip=True))
            if isinstance(h, Tag)
            else (soup.title.get_text(strip=True) if soup.title else "")
        )
        if lang == "zh":
            title = _CJK_GAP.sub("", title)
        sections: list[Section] = []
        paras = body.find_all("p") or [body]
        for p in paras:
            if not isinstance(p, Tag):
                continue
            txt = _WS.sub(" ", p.get_text(" ", strip=True)).strip()
            if lang == "zh":
                txt = _CJK_GAP.sub("", txt)
            if not txt or any(n in txt for n in _NOISE) or txt == title:
                continue
            sections.append(Section(text=txt))
        if not sections:
            return []
        text = "\n\n".join(s.text for s in sections)
        ident = _identity(title, text, lang)
        if ident is None and not manual:
            return []
        body.decompose()  # the release stamp is looked up in the page furniture only
        stamp = _page_stamp(soup)
        stamp_date = stamp[0] if stamp else None
        hint_iso = hints.get("date") or (stamp_date or date(1970, 1, 1)).isoformat()
        d = _meeting_date(
            lang, ident, text, stamp_date, hint_iso, self.chronology.get(ident) if ident else None
        )
        if ident is not None and not manual:
            lo, hi = _quarter_window(*ident)
            if not lo <= d <= hi:
                return []
        when = stamp[1] if stamp else None
        published = when.astimezone(UTC) if when is not None and lang == "zh" else None
        parallel = f"pboc:{ident[0]}Q{ident[1]}:communique" if ident else hints.get("parallel_id")
        return [
            Document(
                bank="pboc",
                date=d,
                published_at_utc=published,
                doc_type="communique",
                language=lang,
                parallel_id=parallel,
                title=title,
                text=text,
                sections=sections,
                url=raw.url,
                sha256=raw.sha256,
                fetched_at=raw.fetched_at,
            )
        ]
