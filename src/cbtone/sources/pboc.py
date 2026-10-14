"""People's Bank of China (PBoC) adapter -- BLOCKED by robots.txt; manual-file mode only.

Document types
    * ``communique``: Monetary Policy Committee quarterly meeting communiqués
      (货币政策委员会例会 / "Monetary Policy Committee Meeting"), zh and (where published) en.

Status
    ``https://www.pbc.gov.cn/robots.txt`` (checked 2026-10-14) reads::

        User-agent: Baiduspider
        Allow: /
        User-agent: *
        Disallow: /

    so every path is disallowed for ``PoliteFetcher``. Per ``docs/specs/adapters.md`` this
    adapter therefore performs **no network access**: a human saves the pages listed in
    ``docs/sources/NEEDED_pboc.md`` into ``data/raw/pboc/manual/`` and ``list_urls`` /
    ``fetch`` read them from there. ``parse`` is written against the known pbc.gov.cn page
    layout (title in ``<h2>``/``<title>``, body in ``div#zoom``, UTF-8 or GBK) but has only been
    exercised on a synthetic fixture, because no real page could be sampled.

Manual file naming: ``<meeting-date ISO>_<lang>.html`` (e.g. ``2024-03-21_zh.html``,
``2024-03-21_en.html``). The meeting date is taken from the text when stated ("第一季度例会于
3月21日召开"), else from the filename. ``published_at_utc`` is ``None`` (no documented
release time).

Terms of use: see ``docs/sources/pboc.md`` (not yet verified: site is not crawlable).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from cbtone.schema import Document, Language, Section
from cbtone.sources.base import PoliteFetcher, RawResponse, SourceAdapter

MANUAL_DIR = Path("data/raw/pboc/manual")
_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(zh|en)\.html?$")
_ZH_MEETING = re.compile(r"(\d{4})年第[一二三四]季度例会于\s*(\d{1,2})月\s*(\d{1,2})日")
_ZH_MEETING_NOYEAR = re.compile(r"例会于\s*(\d{1,2})月\s*(\d{1,2})日")
_WS = re.compile(r"[ \t　\xa0]+")
_ZH_NOISE = ("打印本页", "关闭窗口", "字号", "责任编辑", "分享到")


def _decode(content: bytes) -> str:
    for enc in ("utf-8", "gb18030"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


class PbocAdapter(SourceAdapter):
    bank = "pboc"

    def __init__(self, fetcher: PoliteFetcher, manual_dir: Path = MANUAL_DIR) -> None:
        super().__init__(fetcher)
        self.manual_dir = manual_dir

    def list_urls(self, start_year: int, end_year: int) -> Iterator[tuple[str, dict[str, str]]]:
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
                },
            )

    def fetch(self, start_year: int, end_year: int) -> Iterator[Document]:
        for url, hints in self.list_urls(start_year, end_year):
            content = Path(url.removeprefix("file://")).read_bytes()
            raw = RawResponse(
                url=url,
                content=content,
                content_type="text/html",
                sha256=__import__("hashlib").sha256(content).hexdigest(),
                fetched_at=datetime.now(UTC),
                from_cache=True,
            )
            yield from self.parse(raw, hints)

    def parse(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        soup = BeautifulSoup(_decode(raw.content), "lxml")
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        body = soup.find(id="zoom") or soup.find(class_="TRS_Editor") or soup.body
        if not isinstance(body, Tag):
            return []
        title = ""
        h = soup.find("h2") or soup.find("h1")
        if isinstance(h, Tag):
            title = _WS.sub(" ", h.get_text(" ", strip=True))
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()
        sections: list[Section] = []
        for p in body.find_all(["p", "div"]):
            if not isinstance(p, Tag) or (p.name == "div" and p.find(["p", "div"])):
                continue
            txt = _WS.sub(" ", p.get_text(" ", strip=True)).strip()
            if not txt or any(n in txt for n in _ZH_NOISE) or txt == title:
                continue
            sections.append(Section(text=txt))
        if not sections:
            return []
        text = "\n\n".join(s.text for s in sections)
        lang: Language = "zh" if hints["language"] == "zh" else "en"
        return [
            Document(
                bank="pboc",
                date=_meeting_date(text, hints["date"]),
                published_at_utc=None,
                doc_type="communique",
                language=lang,
                parallel_id=hints.get("parallel_id"),
                title=title,
                text=text,
                sections=sections,
                url=raw.url,
                sha256=raw.sha256,
                fetched_at=raw.fetched_at,
            )
        ]


def _meeting_date(text: str, hint_iso: str) -> date:
    hint = date.fromisoformat(hint_iso)
    m = _ZH_MEETING.search(text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m2 = _ZH_MEETING_NOYEAR.search(text)
    if m2:
        return date(hint.year, int(m2.group(1)), int(m2.group(2)))
    return hint
