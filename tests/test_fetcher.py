from pathlib import Path

import httpx
import pytest

from cbtone.sources.base import BlockedError, PoliteFetcher


def _client(robots: str, status: int = 200) -> tuple[httpx.Client, list[str]]:
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text=robots)
        return httpx.Response(
            status, content=b"<html>hi</html>", headers={"content-type": "text/html"}
        )

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_get_caches_and_hashes(tmp_path: Path) -> None:
    client, calls = _client("User-agent: *\nAllow: /\n")
    f = PoliteFetcher(raw_dir=tmp_path, min_interval_s=0, client=client)
    r1 = f.get("fed", "https://example.org/a.htm")
    r2 = f.get("fed", "https://example.org/a.htm")
    assert not r1.from_cache and r2.from_cache
    assert r1.sha256 == r2.sha256 and len(r1.sha256) == 64
    assert calls.count("https://example.org/a.htm") == 1


def test_robots_disallow(tmp_path: Path) -> None:
    client, _ = _client("User-agent: *\nDisallow: /private\n")
    f = PoliteFetcher(raw_dir=tmp_path, min_interval_s=0, client=client)
    with pytest.raises(BlockedError):
        f.get("fed", "https://example.org/private/x")


def test_403_is_blocked(tmp_path: Path) -> None:
    client, _ = _client("", status=403)
    f = PoliteFetcher(raw_dir=tmp_path, min_interval_s=0, client=client)
    with pytest.raises(BlockedError):
        f.get("mas", "https://example.org/x")


def test_offline_miss(tmp_path: Path) -> None:
    f = PoliteFetcher(raw_dir=tmp_path, offline=True)
    with pytest.raises(FileNotFoundError):
        f.get("fed", "https://example.org/x")


def test_block_page_with_200_is_blocked_and_not_cached(tmp_path: Path) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(
            200,
            content=b"<html><head><title>Maintenance</title></head></html>",
            headers={"content-type": "text/html"},
        )

    f = PoliteFetcher(
        raw_dir=tmp_path,
        min_interval_s=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(BlockedError):
        f.get("mas", "https://example.org/mps")
    assert f.cached("mas", "https://example.org/mps") is None


def test_crawl_delay_is_honoured(tmp_path: Path) -> None:
    client, _ = _client("User-agent: *\nCrawl-delay: 5\nAllow: /\n")
    f = PoliteFetcher(raw_dir=tmp_path, min_interval_s=0, client=client)
    assert f.allowed("https://example.org/a")
    assert f._host_interval["example.org"] == 5.0


def test_post_is_polite_and_cached_per_body(tmp_path: Path) -> None:
    seen: list[tuple[str, str, bytes]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, req.url.path, req.content))
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        return httpx.Response(200, content=req.content, headers={"content-type": "text/html"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    f = PoliteFetcher(raw_dir=tmp_path, min_interval_s=0, client=client)
    url = "https://example.org/index.aspx"
    p2 = f.post("bi", url, {"page": "2", "__VIEWSTATE": "abc"})
    p3 = f.post("bi", url, {"page": "3", "__VIEWSTATE": "abc"})
    again = f.post("bi", url, {"__VIEWSTATE": "abc", "page": "2"})  # same body, other order
    assert p2.content != p3.content
    assert again.from_cache and again.content == p2.content
    assert [m for m, p, _ in seen if p != "/robots.txt"] == ["POST", "POST"]
    assert f.cached("bi", url) is None  # a POST never answers a GET lookup
    with pytest.raises(BlockedError):
        f.post("bi", "https://example.org/private/x", {"a": "1"})
