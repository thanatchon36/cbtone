from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from cbtone.decisions import build_decisions
from cbtone.decisions.mas import MasStance, parse_decision_table
from cbtone.sources.base import BlockedError, PoliteFetcher, RawResponse
from cbtone.sources.mas import TABLE_URL, fetch_decision_table

FIX = Path(__file__).parent / "fixtures" / "mas"
TABLE = (FIX / "decision-table-20251118.html").read_bytes()


def test_parse_decision_table_rows_and_mapping() -> None:
    rows = {r.date: r for r in parse_decision_table(TABLE)}
    assert len(rows) == 59
    assert min(rows) == date(2001, 2, 22) and max(rows) == date(2025, 10, 14)
    apr25 = rows[date(2025, 4, 14)]
    assert (apr25.direction, apr25.parameters) == ("ease", frozenset({"slope"}))
    assert rows[date(2022, 4, 14)].direction == "tighten"
    assert rows[date(2022, 4, 14)].parameters == frozenset({"slope", "centre"})
    mar20 = rows[date(2020, 3, 30)]  # brought-forward April review; not starred by MAS
    assert mar20.direction == "ease" and not mar20.unscheduled
    jul22 = rows[date(2022, 7, 14)]  # off-cycle tightening, starred
    assert jul22.direction == "tighten" and jul22.unscheduled
    oct01 = rows[date(2001, 10, 10)]  # width-only change: no tighten/ease signal
    assert (oct01.direction, oct01.parameters, oct01.unscheduled) == (
        "maintain",
        frozenset({"width"}),
        True,
    )
    assert rows[date(2025, 10, 14)].direction == "maintain"
    assert not rows[date(2025, 10, 14)].unscheduled


def test_table_wins_and_extractor_only_after_table() -> None:
    table = parse_decision_table(TABLE)
    stances = [
        (date(2025, 4, 14), MasStance("tighten", frozenset({"slope"}), 0.9)),  # contradicts table
        (date(2026, 4, 14), MasStance("tighten", frozenset({"slope"}), 0.9)),  # after the table
    ]
    df = build_decisions(None, [], stances, mas_table=table)
    mas = {d: (dirn, src) for d, dirn, src in df.select("date", "direction", "source").iter_rows()}
    assert mas[date(2025, 4, 14)] == ("cut", "mas_table")
    assert mas[date(2026, 4, 14)] == ("hike", "mas_text")
    assert df.height == 60


class _Fake(PoliteFetcher):
    def __init__(self, pages: dict[str, bytes | Exception]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def get(self, bank: str, url: str, *, refresh: bool = False) -> RawResponse:
        assert url.startswith("https://web.archive.org/")
        self.requested.append(url)
        item = self.pages[url] if url in self.pages else self.pages["cdx"]
        if isinstance(item, Exception):
            raise item
        return RawResponse(url, item, "text/html", "", datetime(2026, 1, 1, tzinfo=UTC), True)


def test_fetch_decision_table_skips_maintenance_capture() -> None:
    cdx = json.dumps(
        [["timestamp", "original"], ["20240101000000", TABLE_URL], ["20251118123423", TABLE_URL]]
    ).encode()
    snap = "https://web.archive.org/web/{}id_/" + TABLE_URL
    f = _Fake(
        {
            "cdx": cdx,
            snap.format("20251118123423"): BlockedError("block/interstitial page served"),
            snap.format("20240101000000"): TABLE,
        }
    )
    raw = fetch_decision_table(f)
    assert raw is not None and raw.url == snap.format("20240101000000")
    assert "web/20251118123423id_" in f.requested[1]  # newest tried first


def test_fetch_decision_table_none_when_nothing_usable() -> None:
    cdx = json.dumps([["timestamp", "original"]]).encode()
    assert fetch_decision_table(_Fake({"cdx": cdx})) is None
