"""Series registry: what each daily series is, where it comes from and when it "closes".

The close time matters for event studies: a release at 14:00 New York time is *after* the
Singapore/Jakarta/Bangkok FX close of the same calendar day, so the first close that
reflects it is the next day's. Close times are conventions (documented in
``docs/sources/markets.md``), not exchange-grade timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo

Kind = Literal["fx", "yield"]


@dataclass(frozen=True)
class SeriesSpec:
    series: str
    kind: Kind
    close_tz: str  # IANA zone in which ``close_time`` is expressed
    close_time: time  # local wall-clock time of the daily close
    source: str
    description: str

    @property
    def unit(self) -> str:
        return "log_return" if self.kind == "fx" else "bp"

    def close_utc(self, d: date) -> datetime:
        """UTC instant of the close that is stamped with local date ``d``."""
        local = datetime.combine(d, self.close_time, tzinfo=ZoneInfo(self.close_tz))
        return local.astimezone(UTC)


# Yahoo FX "daily" bars are cut around the New York 17:00 rollover; we model that.
_FX_TZ, _FX_T = "America/New_York", time(17, 0)

FX_TICKERS: tuple[str, ...] = (
    "USDSGD=X",
    "USDIDR=X",
    "USDMYR=X",
    "USDTHB=X",
    "USDCNY=X",
    "EURUSD=X",
    "GBPUSD=X",
    "AUDUSD=X",
    "DX-Y.NYB",
)


def _fx(ticker: str) -> SeriesSpec:
    if ticker == "DX-Y.NYB":
        return SeriesSpec(ticker, "fx", _FX_TZ, _FX_T, "yfinance", "ICE US Dollar Index (DXY)")
    return SeriesSpec(ticker, "fx", _FX_TZ, _FX_T, "yfinance", f"Yahoo Finance spot {ticker}")


def _yld(series: str, tz: str, hh: int, mm: int, source: str, description: str) -> SeriesSpec:
    return SeriesSpec(series, "yield", tz, time(hh, mm), source, description)


REGISTRY: dict[str, SeriesSpec] = {
    **{t: _fx(t) for t in FX_TICKERS},
    "DGS2": _yld("DGS2", "America/New_York", 15, 30, "FRED/H.15", "US Treasury 2y CMT"),
    "DGS10": _yld("DGS10", "America/New_York", 15, 30, "FRED/H.15", "US Treasury 10y CMT"),
    "EA2Y": _yld("EA2Y", "Europe/Berlin", 17, 30, "ECB", "Euro-area AAA govt spot 2y"),
    "EA10Y": _yld("EA10Y", "Europe/Berlin", 17, 30, "ECB", "Euro-area AAA govt spot 10y"),
    "GB2Y": _yld("GB2Y", "Europe/London", 16, 0, "BoE", "UK gilt nominal spot 2y (GLC)"),
    "GB10Y": _yld("GB10Y", "Europe/London", 16, 0, "BoE", "UK gilt nominal spot 10y (GLC)"),
    "AU2Y": _yld("AU2Y", "Australia/Sydney", 16, 0, "RBA", "Australian govt 2y (F2)"),
    "AU10Y": _yld("AU10Y", "Australia/Sydney", 16, 0, "RBA", "Australian govt 10y (F2)"),
}
