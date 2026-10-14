from datetime import date, timedelta

import polars as pl

from cbtone.markets.fx import clean_fx


def _series(name: str, closes: list[float]) -> pl.DataFrame:
    d0 = date(2008, 10, 1)
    return pl.DataFrame(
        {
            "date": [d0 + timedelta(days=i) for i in range(len(closes))],
            "series": [name] * len(closes),
            "close": closes,
        }
    )


def test_isolated_spike_is_dropped():
    closes = [1.36, 1.35, 1.36, 1.37, 1.36, 1.4957, 1.36, 1.34, 1.36, 1.35, 1.36]
    clean, dropped = clean_fx(_series("EURUSD=X", closes))
    assert clean.height == 10 and 1.4957 not in clean["close"].to_list()
    assert dropped.select("series", "reason").rows() == [("EURUSD=X", "spike")]


def test_decimal_shift_is_dropped():
    closes = [8900.0, 8910.0, 8905.0, 8920.0, 8930.0, 888.1, 8915.0, 8900.0, 8925.0, 8910.0]
    clean, dropped = clean_fx(_series("USDIDR=X", closes))
    assert dropped.height == 1 and clean["close"].min() > 8000


def test_stale_plateau_is_dropped():
    closes = [11700.0, 11720.0, 11710.0, 11730.0, 9612.45, 9612.45, 9612.45, 11800.0, 11810.0]
    closes += [11790.0, 11820.0, 11800.0]
    clean, dropped = clean_fx(_series("USDIDR=X", closes))
    assert dropped.height == 3 and set(dropped["reason"]) == {"stale"}
    assert clean["close"].min() > 11000


def test_genuine_crash_is_kept():
    # AUD/USD late Oct 2008: neighbours fall too, so it is a move, not a bad tick
    closes = [0.6677, 0.6708, 0.6690, 0.6700, 0.6207, 0.6053, 0.6505, 0.6712, 0.6698, 0.669, 0.67]
    clean, dropped = clean_fx(_series("AUDUSD=X", closes))
    assert dropped.height == 0 and clean.height == len(closes)


def test_yields_untouched():
    df = pl.concat([_series("DGS2", [5.0, 0.1, 5.0, 5.0, 5.0, 5.0])])
    clean, dropped = clean_fx(df)
    assert clean.equals(df) and dropped.height == 0


def test_short_run_of_different_bad_values_is_dropped():
    # USD/IDR 2013-12-05..10: two adjacent bad values that are not exact repeats
    closes = [11900.0, 11885.0, 11972.0, 9612.45, 9610.0, 11813.0, 11834.0, 11878.0, 11999.0]
    closes += [11988.0, 11973.0]
    clean, dropped = clean_fx(_series("USDIDR=X", closes))
    assert dropped.height == 2 and set(dropped["reason"]) == {"run"}
    assert clean["close"].min() > 11000
