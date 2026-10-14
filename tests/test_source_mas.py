"""Offline tests for the MAS adapter.

Manual-file fixtures (``mas-monetary-policy-statement-13oct23.html``, ``undated-page.html``) are
SYNTHETIC. The ``snapshot-*.html`` and ``cdx-prefix-sample.json`` fixtures are real Internet
Archive captures (scripts/styles stripped to keep them small); ``snapshot-maintenance.html`` is a
real archived MAS "Maintenance" page.
"""

import json
import os
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from cbtone.sources.base import BlockedError, PoliteFetcher, RawResponse, looks_like_block_page
from cbtone.sources.mas import (
    CDX_PREFIXES,
    MasAdapter,
    _cdx_query,
    date_from_name,
    date_from_text,
    parse_cdx,
    statement_date,
)

FIX = Path(__file__).parent / "fixtures" / "mas"
BOILERPLATE = ["Share", "Last updated", "Skip to main", "Footer boilerplate", "Script boilerplate"]


def _adapter(tmp_path: Path) -> MasAdapter:
    return MasAdapter(
        PoliteFetcher(raw_dir=tmp_path, offline=True), manual_dir=tmp_path / "m", use_archive=False
    )


def _load(tmp_path: Path, *names: str) -> list:
    m = tmp_path / "m"
    m.mkdir()
    for n in names:
        shutil.copy(FIX / n, m / n)
    return list(_adapter(tmp_path).load_manual())


def test_date_from_name() -> None:
    assert date_from_name("mps-2023-10-13.html") == date(2023, 10, 13)
    assert date_from_name("mas-monetary-policy-statement-13oct23.html") == date(2023, 10, 13)
    assert date_from_name("monetary-policy-statement-14-oct-10") == date(2010, 10, 14)
    assert date_from_name("monetary-policy-statement-28jan15") == date(2015, 1, 28)
    assert date_from_name("mas-reaffirms-monetary-policy-10-apr-2001") == date(2001, 4, 10)
    assert date_from_name("Monetary-Policy-Statement-12Oct12.aspx") == date(2012, 10, 12)
    assert date_from_name("notes.html") is None


def test_date_from_text() -> None:
    assert date_from_text("Monetary Policy Statement, 13 October 2023") == date(2023, 10, 13)
    assert date_from_text("nothing") is None


def test_slug_html(tmp_path: Path) -> None:
    (doc,) = _load(tmp_path, "mas-monetary-policy-statement-13oct23.html")
    assert (doc.bank, doc.doc_type, doc.language) == ("mas", "mps", "en")
    assert doc.date == date(2023, 10, 13)
    assert doc.doc_id == "mas:2023-10-13:mps:en"
    assert doc.url == (
        "https://www.mas.gov.sg/news/monetary-policy-statements/2023/"
        "mas-monetary-policy-statement-13oct23"
    )
    assert doc.title == "Synthetic Monetary Policy Statement"
    assert len(doc.sha256) == 64
    assert doc.fetched_at.tzinfo is UTC
    assert doc.published_at_utc is None


def test_boilerplate_and_sections(tmp_path: Path) -> None:
    (doc,) = _load(tmp_path, "mas-monetary-policy-statement-13oct23.html")
    for b in BOILERPLATE:
        assert b not in doc.text
    assert "Placeholder sentence gamma" in doc.text
    assert len(doc.sections) == 4
    assert doc.sections[0].heading == "Overview"
    assert doc.sections[2].heading == "Policy"
    assert doc.text == "\n\n".join(s.text for s in doc.sections)


def test_date_from_text_and_slug_url(tmp_path: Path) -> None:
    (doc,) = _load(tmp_path, "undated-page.html")
    assert doc.date == date(2022, 4, 14)
    assert doc.url.endswith("/monetary-policy-statements/2022/undated-page")


def test_fetch_year_filter_and_mtime(tmp_path: Path) -> None:
    _load(tmp_path, "mas-monetary-policy-statement-13oct23.html", "undated-page.html")
    p = tmp_path / "m" / "undated-page.html"
    ts = datetime(2026, 5, 1, tzinfo=UTC).timestamp()
    os.utime(p, (ts, ts))
    a = _adapter(tmp_path)
    assert [d.date.year for d in a.fetch(2023, 2023)] == [2023]
    (d22,) = a.fetch(2022, 2022)
    assert d22.fetched_at == datetime(2026, 5, 1, tzinfo=UTC)


def test_missing_dir_and_ignored_files(tmp_path: Path) -> None:
    assert list(_adapter(tmp_path).load_manual()) == []
    (tmp_path / "m").mkdir()
    (tmp_path / "m" / "readme.txt").write_text("x")
    assert list(_adapter(tmp_path).load_manual()) == []


# ---------------------------------------------------------------------------
# Internet Archive mode (DECISIONS D11)
# ---------------------------------------------------------------------------
MPS = "https://www.mas.gov.sg/news/monetary-policy-statements"
SNAP = "https://web.archive.org/web"
U2008 = f"{MPS}/2008/monetary-policy-statement-10-apr-08"
U2025 = f"{MPS}/2025/mas-monetary-policy-statement-14oct25"
U2001 = f"{MPS}/2001/monetary-policy-statement-22-feb-01"
U2026 = f"{MPS}/2026/mas-monetary-policy-statement-27jul26"
CDX_PREFIX_URL = _cdx_query(CDX_PREFIXES[0], matchType="prefix", collapse="urlkey")


def _fixture(name: str) -> bytes:
    return (FIX / name).read_bytes()


def _cdx_json(*rows: tuple[str, str]) -> bytes:
    body = [["timestamp", "original", "statuscode", "mimetype"]]
    body += [[ts, orig, "200", "text/html"] for ts, orig in rows]
    return json.dumps(body).encode()


class FakeFetcher(PoliteFetcher):
    """Serves canned responses; records every URL asked for; never touches the network."""

    def __init__(self, tmp_path: Path, pages: dict[str, bytes | Exception]) -> None:
        super().__init__(raw_dir=tmp_path, offline=True)
        self.pages = pages
        self.requested: list[str] = []

    def get(self, bank: str, url: str, *, refresh: bool = False) -> RawResponse:
        assert bank == "mas"
        assert url.startswith("https://web.archive.org/"), f"must only hit the archive: {url}"
        self.requested.append(url)
        item = self.pages.get(url)
        if item is None:
            if "/cdx/" in url:
                item = b"[]"
            else:
                raise httpx.HTTPError(f"not archived: {url}")
        if isinstance(item, Exception):
            raise item
        ctype = "application/json" if "/cdx/" in url else "text/html; charset=utf-8"
        if looks_like_block_page(item, ctype):
            raise BlockedError(f"block/interstitial page served for {url}")
        return RawResponse(url, item, ctype, "", datetime(2026, 10, 14, tzinfo=UTC), False)


def _archive(tmp_path: Path, pages: dict[str, bytes | Exception]) -> tuple[MasAdapter, FakeFetcher]:
    ff = FakeFetcher(tmp_path, pages)
    return MasAdapter(ff, manual_dir=tmp_path / "manual"), ff


def _sample_pages() -> dict[str, bytes | Exception]:
    return {
        CDX_PREFIX_URL: _fixture("cdx-prefix-sample.json"),
        f"{SNAP}/20220827025421id_/{U2008}": _fixture("snapshot-2008-04-10.html"),
        f"{SNAP}/20251014002326id_/{U2025}": _fixture("snapshot-2025-10-14.html"),
        f"{SNAP}/20201018032820id_/{U2001}": _fixture("snapshot-2001-02-22.html"),
    }


def test_fixtures_are_small_and_maintenance_is_a_block_page() -> None:
    for p in FIX.glob("snapshot-*.html"):
        assert p.stat().st_size < 150_000, p.name
    assert looks_like_block_page(_fixture("snapshot-maintenance.html"), "text/html")
    assert not looks_like_block_page(_fixture("snapshot-2025-10-14.html"), "text/html")


def test_statement_date_filters_non_statements() -> None:
    assert statement_date(U2008) == date(2008, 4, 10)
    assert statement_date(f"{MPS}/2001/mas-reaffirms-monetary-policy-10-apr-2001") == date(
        2001, 4, 10
    )
    old = "http://www.mas.gov.sg:80/News-and-Publications/Monetary-Policy-Statements-and-Speeches/"
    assert statement_date(f"{old}2012/Monetary-Policy-Statement-12Oct12.aspx") == date(2012, 10, 12)
    assert statement_date(f"{old}2012/Speech-by-Mr-Tharman.aspx") is None
    for bad in (
        MPS,  # index
        f"{MPS}?q=monetary+policy+statements",  # listing/search
        f"{MPS}/2001/-/media/MAS%20Media%20Library/Icons/Social-linkedin",
        f"{MPS}/2005/mas-press-statement",  # no date in slug
        f"{U2025}?utm_source=chatgpt.com",  # tracking variant
        f"{MPS}/2024/mas-monetary-policy-statement-29jan24%0A",
        f"{MPS}/2023/mas-monetary-policy-statement-13oct23&data=05|01|x",
        f"{MPS}/2024/mas-monetary-policy-statement-14oct25",  # folder year != slug year
        "https://example.org/news/monetary-policy-statements/2025/mas-monetary-policy-14oct25",
    ):
        assert statement_date(bad) is None, bad


def test_parse_cdx() -> None:
    rows = parse_cdx(_fixture("cdx-prefix-sample.json"))
    assert rows[0] == {
        "timestamp": "20250323204814",
        "original": MPS,
        "statuscode": "200",
        "mimetype": "text/html",
    }
    assert len(rows) == 14
    assert parse_cdx(b"") == []
    assert parse_cdx(b"[]") == []
    assert parse_cdx(b'[["timestamp","original"]]') == []


def test_cdx_query_shape() -> None:
    q = _cdx_query("www.mas.gov.sg/news/monetary-policy-statements/", matchType="prefix")
    assert q.startswith("https://web.archive.org/cdx/search/cdx?url=www.mas.gov.sg/news/")
    for part in ("output=json", "filter=statuscode:200", "matchType=prefix"):
        assert part in q


def test_list_urls_filters_and_picks_latest(tmp_path: Path) -> None:
    a, ff = _archive(tmp_path, _sample_pages())
    urls = dict(a.list_urls(2001, 2026))
    dates = sorted(h["date"] for h in urls.values())
    assert dates == [
        "2001-02-22",
        "2001-04-10",
        "2008-04-10",
        "2024-10-14",
        "2025-10-14",
        "2026-01-29",
        "2026-07-27",
    ]
    assert f"{SNAP}/20251014002326id_/{U2025}" in urls
    assert urls[f"{SNAP}/20251014002326id_/{U2025}"]["original"] == U2025
    # every CDX prefix was asked, and nothing but the archive was contacted
    assert len(ff.requested) == len(CDX_PREFIXES)
    assert all(u.startswith("https://web.archive.org/cdx/") for u in ff.requested)


def test_fetch_archive_documents(tmp_path: Path) -> None:
    pages = _sample_pages()
    a, _ = _archive(tmp_path, pages)
    docs = list(a.fetch(2001, 2026))
    by = {d.date: d for d in docs}
    # 2001-04-10 / 2024 / 2026 snapshots are not served by the fake: skipped as HTTP errors
    assert date(2025, 10, 14) in by and date(2008, 4, 10) in by and date(2001, 2, 22) in by
    d = by[date(2025, 10, 14)]
    assert d.url == f"{SNAP}/20251014002326id_/{U2025}"
    assert d.bank == "mas" and d.doc_type == "mps" and d.language == "en"
    assert d.doc_id == "mas:2025-10-14:mps:en"
    assert "S$NEER" in d.text and len(d.sha256) == 64
    assert len({x.date for x in docs}) == len(docs)  # de-duplicated by date


def test_title_month_fallback_when_text_has_no_day(tmp_path: Path) -> None:
    a, _ = _archive(tmp_path, _sample_pages())
    (d,) = a.fetch(2008, 2008)
    assert d.date == date(2008, 4, 10)
    assert "April 2008" in d.title


def test_year_filter_requests_only_that_year(tmp_path: Path) -> None:
    a, ff = _archive(tmp_path, _sample_pages())
    docs = list(a.fetch(2025, 2025))
    assert [d.date for d in docs] == [date(2025, 10, 14)]
    snaps = [u for u in ff.requested if "/web/" in u]
    assert snaps == [f"{SNAP}/20251014002326id_/{U2025}"]


def test_date_mismatch_is_rejected(tmp_path: Path) -> None:
    pages = _sample_pages()
    # the 2008 URL serves another statement (22 Feb 2001): slug date != page date
    pages[f"{SNAP}/20220827025421id_/{U2008}"] = _fixture("snapshot-2001-02-22.html")
    a, _ = _archive(tmp_path, pages)
    assert list(a.fetch(2008, 2008)) == []
    assert any("date mismatch" in why for _, why in a.skipped)


def test_not_a_statement_is_rejected(tmp_path: Path) -> None:
    pages = _sample_pages()
    pages[f"{SNAP}/20220827025421id_/{U2008}"] = b"<html><title>Hi</title><body></body></html>"
    a, _ = _archive(tmp_path, pages)
    assert list(a.fetch(2008, 2008)) == []
    assert any("not a statement" in why for _, why in a.skipped)


def test_fallback_to_next_older_then_newer_capture(tmp_path: Path) -> None:
    maint = _fixture("snapshot-maintenance.html")
    good = _fixture("snapshot-2025-10-14.html")
    primary = f"{SNAP}/20251014002326id_/{U2025}"
    alts = _cdx_query(U2025, matchType="exact", collapse="digest")
    pages: dict[str, bytes | Exception] = {
        CDX_PREFIX_URL: _cdx_json(("20251014002326", U2025)),
        primary: maint,
        alts: _cdx_json(
            ("20251013000000", U2025),
            ("20251014002326", U2025),
            ("20251020000000", U2025),
            ("20251101000000", U2025),
        ),
        f"{SNAP}/20251013000000id_/{U2025}": maint,  # next-older: maintenance too
        f"{SNAP}/20251020000000id_/{U2025}": good,  # next-newer: real
    }
    a, ff = _archive(tmp_path, pages)
    (d,) = a.fetch(2025, 2025)
    assert d.url == f"{SNAP}/20251020000000id_/{U2025}"
    snaps = [u for u in ff.requested if "/web/" in u]
    assert snaps == [primary, f"{SNAP}/20251013000000id_/{U2025}", d.url]  # older before newer
    assert [why for _, why in a.skipped] == ["maintenance/bot page"] * 2


def test_all_captures_maintenance_means_missing(tmp_path: Path) -> None:
    maint = _fixture("snapshot-maintenance.html")
    ts = ["20260729222817", "20260820164342"]
    pages: dict[str, bytes | Exception] = {
        CDX_PREFIX_URL: _cdx_json((ts[0], U2026)),
        _cdx_query(U2026, matchType="exact", collapse="digest"): _cdx_json(
            *[(t, U2026) for t in ts]
        ),
    }
    pages.update({f"{SNAP}/{t}id_/{U2026}": maint for t in ts})
    a, _ = _archive(tmp_path, pages)
    assert list(a.fetch(2026, 2026)) == []
    assert len(a.skipped) == 2


def test_http_error_skips_capture(tmp_path: Path) -> None:
    pages = _sample_pages()
    pages[f"{SNAP}/20251014002326id_/{U2025}"] = httpx.ReadTimeout("slow")
    a, _ = _archive(tmp_path, pages)
    assert list(a.fetch(2025, 2025)) == []
    assert a.skipped[0][1].startswith("http error")


@pytest.mark.parametrize(
    "msg", ["robots.txt disallows https://web.archive.org/x", "HTTP 429 for x"]
)
def test_robots_or_rate_limit_stops_the_run(tmp_path: Path, msg: str) -> None:
    pages = _sample_pages()
    pages[f"{SNAP}/20251014002326id_/{U2025}"] = BlockedError(msg)
    a, _ = _archive(tmp_path, pages)
    with pytest.raises(BlockedError):
        list(a.fetch(2025, 2025))


def test_manual_files_take_precedence(tmp_path: Path) -> None:
    m = tmp_path / "manual"
    m.mkdir()
    shutil.copy(FIX / "snapshot-2025-10-14.html", m / "mas-monetary-policy-statement-14oct25.html")
    a, ff = _archive(tmp_path, _sample_pages())
    docs = list(a.fetch(2025, 2026))
    assert [d.date for d in docs] == [date(2025, 10, 14)]
    assert not docs[0].url.startswith(
        "https://web.archive.org/"
    )  # the manual copy, not the archive
    assert not [u for u in ff.requested if U2025 in u]  # no snapshot was fetched for it


def test_manual_out_of_range_does_not_block_archive(tmp_path: Path) -> None:
    m = tmp_path / "manual"
    m.mkdir()
    shutil.copy(FIX / "snapshot-2025-10-14.html", m / "mas-monetary-policy-statement-14oct25.html")
    a, _ = _archive(tmp_path, _sample_pages())
    assert [d.date for d in a.fetch(2008, 2008)] == [date(2008, 4, 10)]


def test_dedupe_by_date_and_old_layout_fallback(tmp_path: Path) -> None:
    new = f"{MPS}/2012/monetary-policy-statement-12-oct-12"
    old = (
        "http://www.mas.gov.sg:80/News-and-Publications/Monetary-Policy-Statements-and-Speeches/"
        "2012/Monetary-Policy-Statement-12Oct12.aspx"
    )
    good = _fixture("snapshot-2025-10-14.html").replace(b"14 October 2025", b"12 October 2012")
    pages: dict[str, bytes | Exception] = {
        CDX_PREFIX_URL: _cdx_json(("20220812162454", new), ("20130126071900", old)),
        _cdx_query(CDX_PREFIXES[2], matchType="prefix", collapse="urlkey"): _cdx_json(
            ("20130126071900", old)
        ),
        f"{SNAP}/20220812162454id_/{new}": httpx.HTTPError("gone"),
        f"{SNAP}/20130126071900id_/{old}": good,
    }
    a, _ = _archive(tmp_path, pages)
    caps = a._candidates(2012, 2012)
    assert [c.original for c in caps[date(2012, 10, 12)]] == [new, old]  # new layout first
    pages[f"{SNAP}/20220812162454id_/{new}"] = good
    (d,) = a.fetch(2012, 2012)  # one document per date even with two layouts
    assert d.url == f"{SNAP}/20220812162454id_/{new}"


def test_old_layout_used_when_new_layout_unusable(tmp_path: Path) -> None:
    new = f"{MPS}/2012/monetary-policy-statement-12-oct-12"
    old = (
        "http://www.mas.gov.sg:80/News-and-Publications/Monetary-Policy-Statements-and-Speeches/"
        "2012/Monetary-Policy-Statement-12Oct12.aspx"
    )
    maint = _fixture("snapshot-maintenance.html")
    good = _fixture("snapshot-2025-10-14.html").replace(b"14 October 2025", b"12 October 2012")
    pages: dict[str, bytes | Exception] = {
        CDX_PREFIX_URL: _cdx_json(("20220812162454", new), ("20130126071900", old)),
        f"{SNAP}/20220812162454id_/{new}": maint,
        f"{SNAP}/20130126071900id_/{old}": good,
    }
    a, _ = _archive(tmp_path, pages)
    (d,) = a.fetch(2012, 2012)
    assert d.url == f"{SNAP}/20130126071900id_/{old}"
    assert d.date == date(2012, 10, 12)


def test_archive_can_be_disabled(tmp_path: Path) -> None:
    ff = FakeFetcher(tmp_path, _sample_pages())
    a = MasAdapter(ff, manual_dir=tmp_path / "manual", use_archive=False)
    assert list(a.fetch(2001, 2026)) == []
    assert ff.requested == []
