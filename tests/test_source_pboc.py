"""Offline tests for the pboc adapter.

Fixtures are real Internet Archive copies of pbc.gov.cn pages (D12), saved raw (``id_`` snapshots):
    * zh_2012q1_old.html     /publish/huobizhengceersi/3141/... layout (``<font id=zoom>``)
    * zh_2015q4_news.html    /goutongjiaoliu/113456/113469/... layout (``<div id=zoom>``)
    * zh_2023q1_new.html     /zhengcehuobisi/125207/3870933/3870936/... layout
    * en_2023q2.html         /en/3688229/3688311/3688329/... (``div.gitop``)
    * shell_empty.html       anti-bot JavaScript shell served instead of an index page
    * nonmeeting_chronology.html  a real page with ``#zoom`` that is not a communiqué
The network is never touched: ``FakeFetcher`` answers CDX and snapshot URLs from dicts.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from cbtone.sources import pboc
from cbtone.sources.base import BlockedError, PoliteFetcher, RawResponse
from cbtone.sources.pboc import PbocAdapter, canonical_key, parse_cdx

FIX = Path(__file__).parent / "fixtures" / "pboc"
HDR = ["timestamp", "original", "mimetype", "length"]
OLD = "http://www.pbc.gov.cn:80/publish/huobizhengceersi/3141/2012/20120331165124501390320/20120331165124501390320_.html"
NEWS = "http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2996192/index.html"
NEW = "https://www.pbc.gov.cn/zhengcehuobisi/125207/3870933/3870936/4853561/index.html"
NEW_HASH = "https://www.pbc.gov.cn/zhengcehuobisi/125207/3870933/3870936/c123e809210f41d0bda2d2455448bab3/index.html"
EN = "http://www.pbc.gov.cn/en/3688229/3688311/3688329/4988706/index.html"
ZH_PFX = "www.pbc.gov.cn/publish/huobizhengceersi/3141/"
ZH2_PFX = "www.pbc.gov.cn/zhengcehuobisi/125207/3870933/3870936/"
EN_PFX = "www.pbc.gov.cn/en/3688229/3688311/3688329/"
NEWS_LIST = "www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html"
CHRON = "http://www.pbc.gov.cn/huobizhengceersi/214481/214543/218247/2847968/index.html"


def fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


def rows(*r: tuple[str, str]) -> bytes:
    return json.dumps([HDR, *[[ts, orig, "text/html", "9000"] for ts, orig in r]]).encode()


def snap(ts: str, orig: str) -> str:
    return pboc.snapshot_url(ts, orig)


class FakeFetcher(PoliteFetcher):
    """Answers CDX (by url + matchType) and snapshot GETs from dicts; records every URL."""

    def __init__(self, cdx: dict[tuple[str, str], bytes], pages: dict[str, bytes | Exception]):
        self.cdx = cdx
        self.pages = pages
        self.calls: list[str] = []

    def get(self, bank: str, url: str, *, refresh: bool = False) -> RawResponse:
        self.calls.append(url)
        assert urlsplit(url).netloc == "web.archive.org", url  # never pbc.gov.cn itself
        if url.startswith(pboc.CDX_URL):
            q = parse_qs(urlsplit(url).query)
            body: bytes | Exception = self.cdx.get((q["url"][0], q["matchType"][0]), b"")
        else:
            body = self.pages.get(url, FileNotFoundError(url))
        if isinstance(body, Exception):
            raise body
        return RawResponse(url, body, "text/html", "ab" * 32, datetime.now(UTC), True)


def raw(content: bytes, url: str = "u") -> RawResponse:
    return RawResponse(
        url, content, "text/html", "cd" * 32, datetime(2026, 10, 14, tzinfo=UTC), True
    )


def adapter(tmp_path: Path, fetcher: PoliteFetcher | None = None, **kw: object) -> PbocAdapter:
    f = fetcher or FakeFetcher({}, {})
    return PbocAdapter(f, manual_dir=tmp_path / "manual", **kw)  # type: ignore[arg-type]


ZH = {"language": "zh", "source": "archive"}
EN_H = {"language": "en", "source": "archive"}


# -- parse: real pages ---------------------------------------------------------------------
def test_parse_new_layout_zh_date_from_text(tmp_path: Path) -> None:
    (doc,) = adapter(tmp_path).parse(raw(fx("zh_2023q1_new.html")), ZH)
    assert doc.date == date(2023, 4, 7)  # "例会于4月7日在北京召开", not the 2023-04-14 release
    assert doc.published_at_utc == datetime(2023, 4, 14, 9, 23, 42, tzinfo=UTC)  # 17:23:42 CST
    assert doc.parallel_id == "pboc:2023Q1:communique" and doc.language == "zh"
    assert doc.title == "中国人民银行货币政策委员会召开2023年第一季度例会"
    assert len(doc.sections) == 5 and "打印" not in doc.text and "总第100次" in doc.text
    assert doc.doc_type == "communique" and doc.bank == "pboc"


def test_parse_news_layout_no_day_uses_page_date(tmp_path: Path) -> None:
    (doc,) = adapter(tmp_path).parse(raw(fx("zh_2015q4_news.html")), ZH)
    assert "日前在北京召开" in doc.text  # the text names no day
    assert doc.date == date(2015, 12, 28)  # the page's own release date
    assert doc.published_at_utc == datetime(2015, 12, 28, 8, 59, tzinfo=UTC)
    assert doc.parallel_id == "pboc:2015Q4:communique"
    assert "稳健的货币政策" in doc.text


def test_parse_old_layout_font_zoom(tmp_path: Path) -> None:
    (doc,) = adapter(tmp_path).parse(raw(fx("zh_2012q1_old.html")), ZH)
    assert doc.date == date(2012, 3, 31) and doc.parallel_id == "pboc:2012Q1:communique"
    assert len(doc.sections) == 4 and doc.text.startswith("中国人民银行货币政策委员会2012年")


def test_parse_en(tmp_path: Path) -> None:
    (doc,) = adapter(tmp_path).parse(raw(fx("en_2023q2.html")), EN_H)
    assert doc.language == "en" and doc.date == date(2023, 6, 28)
    assert doc.published_at_utc is None  # en pages state no release time
    assert doc.parallel_id == "pboc:2023Q2:communique"
    assert doc.title == "PBOC Monetary Policy Committee Holds Q2 2023 Meeting"
    assert doc.text.startswith("On June 28, the Monetary Policy Committee")


def test_parse_rejects_shell_and_non_communique(tmp_path: Path) -> None:
    a = adapter(tmp_path)
    assert a.parse(raw(fx("shell_empty.html")), ZH) == []
    assert a.parse(raw(fx("nonmeeting_chronology.html")), ZH) == []
    assert a.parse(raw(b""), ZH) == []
    assert a.parse(raw(fx("en_2023q2.html")), ZH) == []  # en page is not a zh communiqué


def test_parse_date_must_fit_title_quarter(tmp_path: Path) -> None:
    text = fx("zh_2023q1_new.html").decode().replace("例会于4月7日", "例会于9月7日")
    assert adapter(tmp_path).parse(raw(text.encode()), ZH) == []
    ok = fx("zh_2023q1_new.html").decode().replace("例会于4月7日", "例会于3月30日")
    (doc,) = adapter(tmp_path).parse(raw(ok.encode()), ZH)
    assert doc.date == date(2023, 3, 30)


def test_parse_en_q4_meeting_reported_in_january(tmp_path: Path) -> None:
    html = (
        "<html><head><title>PBOC Monetary Policy Committee Holds Q4 2024 Meeting</title></head>"
        "<body><h2>PBOC Monetary Policy Committee Holds Q4 2024 Meeting</h2>"
        '<div class="gitop"><p>On January 2, the Monetary Policy Committee of the PBOC '
        "held the fourth quarterly meeting of 2024.</p></div></body></html>"
    )
    (doc,) = adapter(tmp_path).parse(raw(html.encode()), EN_H)
    assert doc.date == date(2025, 1, 2) and doc.parallel_id == "pboc:2024Q4:communique"


def test_parse_en_older_format_day_at_end(tmp_path: Path) -> None:
    # wording of the 2021-22 English pages ("PBC", the day after the verb)
    html = (
        "<html><body><h2>PBC Monetary Policy Committee Holds Q1 2021 Meeting</h2>"
        '<div class="gitop"><p>The Monetary Policy Committee of the People\u2019s Bank of China '
        "(PBC) held the first quarterly meeting of 2021 (its 92nd&nbsp;meeting) on March 24 in "
        "Beijing.</p></div></body></html>"
    )
    (doc,) = adapter(tmp_path).parse(raw(html.encode()), EN_H)
    assert doc.date == date(2021, 3, 24) and doc.parallel_id == "pboc:2021Q1:communique"


def test_parse_en_identity_from_body_when_title_lacks_quarter(tmp_path: Path) -> None:
    html = (
        "<html><body><h2>Monetary Policy Committee Meeting</h2><div class='gitop'><p>On March 3, "
        "the Monetary Policy Committee held the first quarterly meeting of 2020.</p></div>"
        "</body></html>"
    )
    (doc,) = adapter(tmp_path).parse(raw(html.encode()), EN_H)
    assert doc.parallel_id == "pboc:2020Q1:communique" and doc.date == date(2020, 3, 3)


# -- encoding ------------------------------------------------------------------------------
@pytest.mark.parametrize("enc", ["gb2312", "gbk", "gb18030"])
def test_gbk_pages_decode(tmp_path: Path, enc: str) -> None:
    html = fx("zh_2012q1_old.html").decode().replace("charset=utf-8", f"charset={enc}")
    content = html.encode("gb18030")  # superset: every character in the page encodes
    with pytest.raises(UnicodeDecodeError):
        content.decode("utf-8")
    (doc,) = adapter(tmp_path).parse(raw(content), ZH)
    assert doc.date == date(2012, 3, 31) and "稳健的货币政策" in doc.text


def test_decode_gbk_without_meta_and_bom() -> None:
    s = "<title>中国人民银行货币政策委员会</title>"
    assert pboc._decode(s.encode("gb18030")) == s  # no meta: utf-8 fails, gb18030 wins
    assert pboc._decode(b"\xef\xbb\xbf" + s.encode()) == s
    assert "�" in pboc._decode(b"<meta charset=utf-8>\xff\xff\x81")


# -- CDX helpers ---------------------------------------------------------------------------
def test_chronology_table_and_exact_dates(tmp_path: Path) -> None:
    table = pboc.parse_chronology(fx("nonmeeting_chronology.html").decode())
    assert len(table) > 60 and table[(2012, 1)] == date(2012, 3, 29)
    assert table[(2015, 4)] == date(2015, 12, 23) and table[(1997, 2)] == date(1997, 7, 31)
    assert (1997, 1) not in table  # blank cell
    assert pboc.parse_chronology("<html></html>") == {}
    a = adapter(tmp_path, build())
    assert a.chronology == {} and len(a.load_chronology()) == len(table)
    (doc,) = a.parse(raw(fx("zh_2012q1_old.html")), ZH)
    assert doc.date == date(2012, 3, 29) and doc.published_at_utc is not None
    assert doc.published_at_utc.date() == date(2012, 3, 31)
    # text day beats the table (2023Q1 states 4月7日)
    a.chronology[(2023, 1)] = date(2023, 4, 1)
    (new,) = a.parse(raw(fx("zh_2023q1_new.html")), ZH)
    assert new.date == date(2023, 4, 7)
    # a table date outside the quarter window rejects the capture
    a.chronology[(2012, 1)] = date(2012, 9, 1)
    assert a.parse(raw(fx("zh_2012q1_old.html")), ZH) == []


def test_chronology_unavailable_falls_back_to_page_date(tmp_path: Path) -> None:
    a = adapter(tmp_path, FakeFetcher({}, {}))
    assert a.load_chronology() == {}
    (doc,) = a.parse(raw(fx("zh_2012q1_old.html")), ZH)
    assert doc.date == date(2012, 3, 31)


def test_parse_cdx_and_keys() -> None:
    assert parse_cdx(b"") == [] and parse_cdx(b"[]") == []
    out = parse_cdx(rows(("20120403174002", OLD)))
    assert out[0]["original"] == OLD and out[0]["timestamp"] == "20120403174002"
    # scheme, :80, www., query and double slashes do not matter; dir == index.html
    a = canonical_key("http://www.pbc.gov.cn:80/en//3688/1/index.html?x=1")
    assert (
        a
        == canonical_key("https://pbc.gov.cn/en/3688/1/index.html")
        == "pbc.gov.cn/en/3688/1/index.html"
    )
    assert canonical_key("https://www.pbc.gov.cn/en/3688/1/") == a
    assert snap("2012", "http://x/y") == "https://web.archive.org/web/2012id_/http://x/y"


# -- fetch: discovery, fallback, dedupe, filters ---------------------------------------------
def build(extra_pages: dict[str, bytes | Exception] | None = None) -> FakeFetcher:
    shell = fx("shell_empty.html")
    zh_q2 = (
        fx("zh_2023q1_new.html")
        .decode()
        .replace("第一季度", "第二季度")
        .replace("4月7日", "6月28日")
    )
    cdx = {
        (ZH_PFX, "prefix"): rows(
            ("20150614000000", OLD),  # newest capture is a shell -> fallback
            ("20120403174002", OLD),
            ("20120403174002", OLD.replace("20120331165124501390320", "x")),  # unrelated, 404s
            ("20130101000000", "http://www.pbc.gov.cn:80/publish/huobizhengceersi/3141/index.html"),
        ),
        (ZH2_PFX, "prefix"): rows(
            ("20240103185742", NEW),
            ("20250101000000", NEW_HASH),  # same meeting under a migrated URL: de-duplicated
            (
                "20240103185743",
                "https://www.pbc.gov.cn/zhengcehuobisi/125207/3870933/3870936/index.html",
            ),
            ("20251231000000", ZH2_PFX.join(["https://", "999/index.html"])),  # only a shell
        ),
        (EN_PFX, "prefix"): rows(("20240104154235", EN)),
        (NEWS_LIST, "exact"): rows(("20151229000000", NEWS_LIST.join(["http://", ""]))),
        ("www.pbc.gov.cn/en/3688110/3688172/index.html", "exact"): b"",
        ("www.pbc.gov.cn/en/3688110/3688172/5552468/", "exact"): b"",
        (NEWS, "exact"): rows(("20160515180042", NEWS), ("20151228184819", NEWS)),
        (pboc.CHRONOLOGY, "exact"): rows(("20160526224053", CHRON), ("20160405141510", CHRON)),
    }
    list_html = (
        '<html><body><a href="/goutongjiaoliu/113456/113469/2996192/index.html">'
        "中国人民银行货币政策委员会召开2015年第四季度例会</a>"
        '<a href="/goutongjiaoliu/113456/113469/1/index.html">央行有关负责人答记者问</a>'
        '<a href="/goutongjiaoliu/113456/113469/2/index.html" title="中国人民银行货币政策委员会召开'
        '2016年第一季度例会">中国人民银行货币政策委员会召开2016年第一...</a>'
        '<a href="http://example.com/x">中国人民银行货币政策委员会召开2015年第一季度例会</a>'
        "</body></html>"
    ).encode() + b" " * 100
    pages: dict[str, bytes | Exception] = {
        snap("20150614000000", OLD): shell,
        snap("20120403174002", OLD): fx("zh_2012q1_old.html"),
        snap(
            "20130101000000", "http://www.pbc.gov.cn:80/publish/huobizhengceersi/3141/index.html"
        ): shell,
        snap("20240103185742", NEW): fx("zh_2023q1_new.html"),
        snap("20250101000000", NEW_HASH): fx("zh_2023q1_new.html"),
        snap("20251231000000", "https://999/index.html"): shell,
        snap("20240104154235", EN): fx("en_2023q2.html"),
        snap("20151229000000", "http://" + NEWS_LIST): list_html,
        snap("20160515180042", NEWS): shell,
        snap("20151228184819", NEWS): fx("zh_2015q4_news.html"),
        snap("20160526224053", CHRON): shell,  # newest capture is a shell: fall back
        snap("20160405141510", CHRON): fx("nonmeeting_chronology.html"),
        **(extra_pages or {}),
    }
    # the 2023 zh pages here are Q2 (pairs with the en copy); the migrated hash URL is a duplicate
    pages[snap("20240103185742", NEW)] = zh_q2.encode()
    pages[snap("20250101000000", NEW_HASH)] = zh_q2.encode()
    return FakeFetcher(cdx, pages)


def test_fetch_archive_end_to_end(tmp_path: Path) -> None:
    f = build()
    a = adapter(tmp_path, f)
    docs = list(a.fetch(2010, 2026))
    got = sorted((d.date.isoformat(), d.language) for d in docs)
    assert got == [
        ("2012-03-29", "zh"),  # PBoC's meeting-date table, not the 03-31 release stamp
        ("2015-12-23", "zh"),  # found through a link on an archived column front page
        ("2023-06-28", "en"),
        ("2023-06-28", "zh"),
    ]
    by = {(d.date.year, d.language): d for d in docs}
    # zh and en of the same meeting share the parallel_id
    assert by[(2023, "zh")].parallel_id == by[(2023, "en")].parallel_id == "pboc:2023Q2:communique"
    # Document.url is the snapshot of the capture that parsed, not pbc.gov.cn
    assert by[(2015, "zh")].url == snap("20151228184819", NEWS)  # newer shell capture skipped
    assert by[(2012, "zh")].url == snap("20120403174002", OLD)  # shell at 2015 skipped
    assert all(d.url.startswith("https://web.archive.org/web/") for d in docs)
    reasons = " ".join(r for _, r in a.skipped)
    assert "not a communiqué" in reasons
    # the duplicate migrated URL was fetched but dropped by (date, language)
    assert snap("20250101000000", NEW_HASH) in f.calls or snap("20240103185742", NEW) in f.calls


def test_harvest_uses_title_attribute_and_year_range(tmp_path: Path) -> None:
    a = adapter(tmp_path, build())
    keys = a._harvest("zh", 2010, 2026)
    assert "pbc.gov.cn/goutongjiaoliu/113456/113469/2/index.html" in keys  # text truncated
    assert "pbc.gov.cn/goutongjiaoliu/113456/113469/2996192/index.html" in keys
    assert not any("example.com" in k for k in keys) and not any(
        k.endswith("/1/index.html") for k in keys
    )
    assert set(a._harvest("zh", 2017, 2026)) == set()  # the 2015 and 2016 links fall outside


def test_fetch_year_filter(tmp_path: Path) -> None:
    f = build()
    docs = list(adapter(tmp_path, f).fetch(2023, 2023))
    assert sorted((d.date.year, d.language) for d in docs) == [(2023, "en"), (2023, "zh")]
    old = snap("20120403174002", OLD)
    assert old not in f.calls  # 2012 old-layout URL is not even fetched
    assert [d.date.year for d in adapter(tmp_path, build()).fetch(2012, 2012)] == [2012]
    assert list(adapter(tmp_path, build()).fetch(2000, 2009)) == []


def test_fetch_manual_takes_precedence_and_blocks_archive_duplicate(tmp_path: Path) -> None:
    man = tmp_path / "manual"
    man.mkdir()
    zh_q2 = (
        fx("zh_2023q1_new.html")
        .decode()
        .replace("第一季度", "第二季度")
        .replace("4月7日", "6月28日")
    )
    (man / "2023-06-28_zh.html").write_text(zh_q2)
    (man / "readme.txt").write_text("ignored")
    (man / "2011-13-99_zh.html").write_text("x")  # bad name pattern still matches; no body -> []
    f = build()
    docs = list(adapter(tmp_path, f).fetch(2023, 2023))
    zh = [d for d in docs if d.language == "zh"]
    assert len(zh) == 1 and zh[0].url.startswith("file://")  # manual file, not the archive copy
    assert [d.language for d in docs].count("en") == 1  # the archive en copy is still added
    assert zh[0].sha256 and zh[0].parallel_id == "pboc:2023Q2:communique"
    items = list(adapter(tmp_path, f).list_urls(2023, 2023))
    assert items[0][1]["source"] == "manual" and items[0][1]["date"] == "2023-06-28"
    assert {h["source"] for _, h in items[1:]} == {"archive"}


def test_manual_page_without_title_identity_still_loads(tmp_path: Path) -> None:
    man = tmp_path / "manual"
    man.mkdir()
    (man / "2024-03-21_zh.html").write_text(
        "<html><body><h2>货币政策委员会会议</h2><p>会议于3月21日召开。</p></body></html>"
    )
    (doc,) = list(adapter(tmp_path).fetch(2024, 2024))
    assert doc.parallel_id == "pboc:2024-03-21:communique" and doc.date == date(2024, 3, 21)


def test_list_urls_archive_hints(tmp_path: Path) -> None:
    items = list(adapter(tmp_path, build()).list_urls(2010, 2026))
    urls = {u for u, _ in items}
    assert snap("20150614000000", OLD) in urls  # newest capture first
    h = dict(items)[snap("20150614000000", OLD)]
    assert h["language"] == "zh" and snap("20120403174002", OLD) in h["alternatives"]
    assert all(u.startswith("https://web.archive.org/web/") for u in urls)


def test_use_archive_false_makes_no_requests(tmp_path: Path) -> None:
    f = build()
    assert list(adapter(tmp_path, f, use_archive=False).fetch(2010, 2026)) == []
    assert f.calls == []


# -- failure handling ------------------------------------------------------------------------
def test_interstitial_and_http_errors_are_skipped_robots_stops(tmp_path: Path) -> None:
    f = build({snap("20150614000000", OLD): BlockedError("block/interstitial page served for u")})
    a = adapter(tmp_path, f)
    assert any(d.date.year == 2012 for d in a.fetch(2012, 2012))
    assert any("interstitial" in r for _, r in a.skipped)

    f2 = build({snap("20150614000000", OLD): httpx.ConnectError("boom")})
    a2 = adapter(tmp_path, f2)
    assert any(d.date.year == 2012 for d in a2.fetch(2012, 2012))
    assert any("http error" in r for _, r in a2.skipped)

    f3 = build({snap("20150614000000", OLD): BlockedError("robots.txt disallows u")})
    with pytest.raises(BlockedError):  # robots / 403 / 429: stop and report, never work around
        list(adapter(tmp_path, f3).fetch(2012, 2012))


def test_offline_uncached_pages_are_skipped(tmp_path: Path) -> None:
    f = FakeFetcher({(ZH_PFX, "prefix"): rows(("20120403174002", OLD))}, {})
    a = adapter(tmp_path, f)
    assert list(a.fetch(2010, 2026)) == []
    assert any("offline: not cached" in r for _, r in a.skipped)
    off = PbocAdapter(PoliteFetcher(raw_dir=tmp_path, offline=True), manual_dir=tmp_path / "m")
    assert list(off.fetch(2010, 2026)) == []  # CDX never cached: nothing, no crash


def test_non_html_and_malformed_cdx_rows_ignored(tmp_path: Path) -> None:
    body = json.dumps(
        [
            HDR,
            ["2012", OLD, "application/pdf", "9"],
            ["", OLD, "text/html", "9"],
            ["2012", OLD, "text/html", "n/a"],
        ]
    ).encode()
    f = FakeFetcher({(ZH_PFX, "prefix"): body}, {snap("2012", OLD): fx("zh_2012q1_old.html")})
    docs = list(adapter(tmp_path, f).fetch(2012, 2012))
    assert [d.date.year for d in docs] == [2012]
