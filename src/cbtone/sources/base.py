"""Polite, cached HTTP fetching and the adapter interface.

Rules (MISSION.md §0): honour robots.txt, ≤ 1 request / 2 s per host, a descriptive
User-Agent, and every raw response cached under ``data/raw/<bank>/`` keyed by URL,
with its SHA-256 recorded.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.robotparser
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from cbtone import __version__
from cbtone.schema import Bank, Document

USER_AGENT = (
    f"cbtone/{__version__} (+https://github.com/thanatchon36/cbtone; "
    "open-source research on public central-bank communication)"
)
MIN_INTERVAL_S = 2.0
DEFAULT_RAW_DIR = Path("data/raw")


class BlockedError(RuntimeError):
    """Raised when robots.txt disallows a URL or the host refuses automated access."""


# Interstitials some hosts serve with HTTP 200 to automated clients (bot protection,
# "maintenance" pages). Matched against the <title> of HTML responses; never cached.
BLOCK_PAGE_TITLES = (
    "maintenance",
    "access denied",
    "just a moment",
    "attention required",
    "request rejected",
    "are you a robot",
    "captcha",
)


def looks_like_block_page(content: bytes, content_type: str) -> bool:
    if "html" not in content_type.lower():
        return False
    head = content[:20000].decode("utf-8", errors="ignore").lower()
    start = head.find("<title")
    if start < 0:
        return False
    title = head[start : head.find("</title", start)]
    return any(t in title for t in BLOCK_PAGE_TITLES)


@dataclass(frozen=True)
class RawResponse:
    url: str
    content: bytes
    content_type: str
    sha256: str
    fetched_at: datetime
    from_cache: bool


class PoliteFetcher:
    """HTTP GET with robots.txt, per-host rate limit and an on-disk cache.

    Cache layout: ``<raw_dir>/<bank>/<sha256(url)[:16]>.bin`` plus a ``.json`` sidecar
    holding url, content_type, sha256 (of the bytes) and fetched_at.
    """

    def __init__(
        self,
        raw_dir: Path = DEFAULT_RAW_DIR,
        min_interval_s: float = MIN_INTERVAL_S,
        client: httpx.Client | None = None,
        offline: bool = False,
    ) -> None:
        self.raw_dir = raw_dir
        self.min_interval_s = min_interval_s
        self.offline = offline
        self._client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60.0
        )
        self._last_hit: dict[str, float] = {}
        self._host_interval: dict[str, float] = {}  # from robots.txt Crawl-delay
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    # -- cache ---------------------------------------------------------------
    def _paths(self, bank: str, url: str) -> tuple[Path, Path]:
        key = hashlib.sha256(url.encode()).hexdigest()[:16]
        d = self.raw_dir / bank
        return d / f"{key}.bin", d / f"{key}.json"

    def cached(self, bank: str, url: str) -> RawResponse | None:
        body, meta = self._paths(bank, url)
        if not (body.exists() and meta.exists()):
            return None
        m = json.loads(meta.read_text())
        return RawResponse(
            url=m["url"],
            content=body.read_bytes(),
            content_type=m["content_type"],
            sha256=m["sha256"],
            fetched_at=datetime.fromisoformat(m["fetched_at"]),
            from_cache=True,
        )

    # -- politeness ----------------------------------------------------------
    def _wait(self, host: str) -> None:
        interval = max(self.min_interval_s, self._host_interval.get(host, 0.0))
        last = self._last_hit.get(host)
        if last is not None:
            delta = time.monotonic() - last
            if delta < interval:
                time.sleep(interval - delta)
        self._last_hit[host] = time.monotonic()

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            rp: urllib.robotparser.RobotFileParser | None = urllib.robotparser.RobotFileParser()
            try:
                self._wait(parts.netloc)
                r = self._client.get(f"{host}/robots.txt")
                if r.status_code >= 400:
                    rp = None  # no robots.txt → everything allowed
                else:
                    assert rp is not None
                    rp.parse(r.text.splitlines())
            except httpx.HTTPError:
                rp = None
            self._robots[host] = rp
            if rp is not None:
                delay = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*")
                if delay:
                    self._host_interval[parts.netloc] = float(delay)
        rp = self._robots[host]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    # -- public --------------------------------------------------------------
    def get(self, bank: str, url: str, *, refresh: bool = False) -> RawResponse:
        if not refresh:
            hit = self.cached(bank, url)
            if hit is not None:
                return hit
        if self.offline:
            raise FileNotFoundError(f"offline and not cached: {url}")
        if not self.allowed(url):
            raise BlockedError(f"robots.txt disallows {url}")
        self._wait(urlsplit(url).netloc)
        r = self._client.get(url)
        if r.status_code in (401, 403, 429):
            raise BlockedError(f"HTTP {r.status_code} for {url}")
        r.raise_for_status()
        content = r.content
        if looks_like_block_page(content, r.headers.get("content-type", "")):
            raise BlockedError(f"block/interstitial page served for {url}")
        resp = RawResponse(
            url=url,
            content=content,
            content_type=r.headers.get("content-type", ""),
            sha256=hashlib.sha256(content).hexdigest(),
            fetched_at=datetime.now(UTC),
            from_cache=False,
        )
        body, meta = self._paths(bank, url)
        body.parent.mkdir(parents=True, exist_ok=True)
        body.write_bytes(content)
        meta.write_text(
            json.dumps(
                {
                    "url": url,
                    "content_type": resp.content_type,
                    "sha256": resp.sha256,
                    "fetched_at": resp.fetched_at.isoformat(),
                }
            )
        )
        return resp


class SourceAdapter(ABC):
    """One adapter per bank. Subclasses document types, URL patterns, date range,
    languages and terms of use in their class docstring."""

    bank: Bank

    def __init__(self, fetcher: PoliteFetcher) -> None:
        self.fetcher = fetcher

    @abstractmethod
    def list_urls(self, start_year: int, end_year: int) -> Iterable[tuple[str, dict[str, str]]]:
        """Yield (url, hints) for every document in range; hints carry doc_type/date/lang."""

    @abstractmethod
    def parse(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        """Turn one raw response into zero or more Documents (pure; no network)."""

    def fetch(self, start_year: int, end_year: int) -> Iterator[Document]:
        for url, hints in self.list_urls(start_year, end_year):
            raw = self.fetcher.get(self.bank, url)
            yield from self.parse(raw, hints)
