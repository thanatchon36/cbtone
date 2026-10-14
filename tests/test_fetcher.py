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
