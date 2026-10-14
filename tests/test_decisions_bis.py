from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from cbtone.decisions import build_decisions
from cbtone.decisions.bis import parse_bis_csv, rate_changes
from cbtone.decisions.build import bis_decisions, mas_decisions
from cbtone.decisions.mas import MasStance

FIX = Path(__file__).parent / "fixtures" / "bis_cbpol_sample.csv"


def series(bank: str, start: str, end: str) -> pl.DataFrame:
    """Slice of the BIS fixture (windows are disjoint, so always slice per case)."""
    df = parse_bis_csv(FIX.read_bytes())
    return df.filter(
        pl.col("bank") == bank,
        pl.col("date").is_between(date.fromisoformat(start), date.fromisoformat(end)),
    )


def test_parse_drops_nan_and_unknown() -> None:
    df = parse_bis_csv(FIX.read_bytes())
    assert set(df["bank"]) <= {"fed", "ecb", "boe", "rba", "bi", "bnm", "pboc", "bot"}
    assert df["rate"].is_nan().sum() == 0
    # the fixture holds ECB NaN rows around 2024-09-21/22
    ecb = df.filter(pl.col("bank") == "ecb", pl.col("date") == date(2024, 9, 21))
    assert ecb.is_empty()


def test_fed_upper_bound_2008() -> None:
    (c,) = rate_changes(series("fed", "2008-12-10", "2008-12-20"))
    assert c.date == date(2008, 12, 16)
    assert c.bp == -75.0  # 1.00 target -> 0-0.25 range (upper 0.25)
    assert c.after == pytest.approx(0.25)


def test_ecb_splice_is_not_a_policy_move() -> None:
    changes = rate_changes(series("ecb", "2024-09-10", "2024-09-26"))
    assert [(c.date, c.bp) for c in changes] == [(date(2024, 9, 18), -25.0)]


def test_meeting_matching_with_lag_and_instruments() -> None:
    s = series("ecb", "2024-06-05", "2024-06-15")
    out = bis_decisions(s, [("ecb", date(2024, 6, 6))])
    (d,) = out
    assert d.date == date(2024, 6, 6) and d.effective_date == date(2024, 6, 12)
    assert d.direction == "cut" and d.magnitude_bp == -25.0 and not d.unscheduled
    assert d.policy_instrument == "ECB MRO (fixed rate)"
    s2 = series("ecb", "2024-09-10", "2024-09-26")
    (d2,) = bis_decisions(s2, [("ecb", date(2024, 9, 12))])
    assert d2.policy_instrument == "ECB DFR" and d2.rate_after == 3.5


def test_hold_and_hike_and_next_columns() -> None:
    s = series("fed", "2024-12-12", "2024-12-20")
    meets = [("fed", date(2024, 12, 13)), ("fed", date(2024, 12, 18))]  # first one synthetic
    df = build_decisions(s, meets)
    assert df["direction"].to_list() == ["hold", "cut"]
    assert df["magnitude_bp"].to_list() == [0.0, -25.0]
    assert df["rate_after"].to_list() == [4.75, 4.5]
    assert df["next_direction"].to_list() == ["cut", None]
    assert df["next_date"].to_list() == [date(2024, 12, 18), None]
    assert df["policy_instrument"][0] == "fed funds target (upper)"


def test_unscheduled_flag() -> None:
    s = series("bi", "2026-06-05", "2026-06-20")
    out = bis_decisions(s, [("bi", date(2026, 6, 9))])
    by_date = {d.date: d for d in out}
    assert not by_date[date(2026, 6, 9)].unscheduled
    assert by_date[date(2026, 6, 18)].unscheduled
    assert by_date[date(2026, 6, 18)].direction == "hike"


def test_bank_without_calendar_is_not_flagged() -> None:
    out = bis_decisions(series("pboc", "2025-05-15", "2025-05-24"), [])
    (d,) = out
    assert d.magnitude_bp == -10.0 and not d.unscheduled


def test_noise_blips_are_ignored() -> None:
    df = series("rba", "2008-02-14", "2008-02-22")
    assert all(abs(c.bp) >= 0.5 for c in rate_changes(df))


def test_meeting_beyond_data_is_skipped() -> None:
    s = series("fed", "2024-12-12", "2024-12-20")
    out = bis_decisions(s, [("fed", date(2025, 3, 1)), ("fed", date(2024, 12, 1))])
    assert [d.direction for d in out] == ["cut"] and out[0].unscheduled


def test_mas_rows_and_parquet(tmp_path: Path) -> None:
    stances = [
        (date(2025, 1, 24), MasStance("ease", frozenset({"slope"}), 0.9)),
        (date(2025, 7, 30), MasStance("maintain", frozenset(), 0.9)),
        (date(2025, 8, 1), MasStance("maintain", frozenset(), 0.0)),  # unrecognised: dropped
    ]
    rows = mas_decisions(stances)
    assert [r.direction for r in rows] == ["cut", "hold"]
    assert math.isnan(rows[0].magnitude_bp)
    out = tmp_path / "decisions.parquet"
    df = build_decisions(series("fed", "2024-12-12", "2024-12-20"), [], stances, out)
    back = pl.read_parquet(out)
    assert back.shape == df.shape
    mas = back.filter(pl.col("bank") == "mas")
    assert mas["source"].to_list() == ["mas_text"] * 2
    assert mas["next_direction"].to_list() == ["hold", None]
