"""BIS "Central bank policy rates" (dataflow ``WS_CBPOL``, daily) -> rate changes.

Fetched through :class:`~cbtone.sources.base.PoliteFetcher` (bank key ``"bis"``) from the
BIS SDMX v2 API as CSV. Which rate each series is (verified on the BIS series metadata):

* US ``fed``: mid-point of the target range (single target before 2008-12-16). We add 12.5 bp
  from 2008-12-16 so ``rate_after`` is the *upper bound*; changes are unaffected.
* XM ``ecb``: the **main refinancing operations (MRO) fixed rate** up to 2024-09-17, then the
  **deposit facility rate (DFR)** from 2024-09-18, when the ECB's operational framework made the
  DFR the steering rate. The splice is not a policy move: the 2024-09-12 decision was a 25 bp DFR
  cut (MRO cut 60 bp, effective 18 Sep), so we compare the first DFR print against
  ``MRO - 50 bp`` (the spread in force). Before 2024 the MRO moved with the DFR in most
  meetings but not all (spread changes in 2008-09, 2011, 2022), so ECB magnitudes pre-2024
  are MRO magnitudes.
* Others: GB Bank Rate, AU cash rate target, ID BI policy rate, MY OPR, CN 1y LPR (1y lending
  rate before 2019-08-20), TH 1-day repo rate.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from typing import Final

import polars as pl

from cbtone.schema import Bank
from cbtone.sources.base import PoliteFetcher

BIS_BASE: Final = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0"
REF_AREA_TO_BANK: Final[dict[str, Bank]] = {
    "US": "fed",
    "XM": "ecb",
    "GB": "boe",
    "AU": "rba",
    "ID": "bi",
    "MY": "bnm",
    "CN": "pboc",
    "TH": "bot",
}
US_UPPER_FROM: Final = date(2008, 12, 16)
ECB_DFR_FROM: Final = date(2024, 9, 18)
ECB_SPREAD_MRO_DFR: Final = 0.50  # percentage points in force on 2024-09-17
MIN_CHANGE_PP: Final = 0.005  # 0.5 bp

_INSTRUMENT: Final[dict[str, str]] = {
    "boe": "Bank Rate",
    "rba": "cash rate target",
    "bi": "BI policy rate",
    "bnm": "OPR",
    "pboc": "1y LPR / 1y lending rate",
    "bot": "1-day repo rate",
}


def bis_url(start: str = "1999-01-01") -> str:
    areas = "+".join(REF_AREA_TO_BANK)
    return f"{BIS_BASE}/D.{areas}?format=csv&detail=dataonly&startPeriod={start}"


def fetch_bis_csv(fetcher: PoliteFetcher, start: str = "1999-01-01") -> bytes:
    return fetcher.get("bis", bis_url(start)).content


def parse_bis_csv(content: bytes) -> pl.DataFrame:
    """Return ``bank, date, rate`` (percent), NaN/missing observations dropped, sorted."""
    raw = pl.read_csv(io.BytesIO(content), infer_schema_length=0)
    df = (
        raw.select(
            pl.col("REF_AREA"),
            pl.col("TIME_PERIOD").str.to_date("%Y-%m-%d").alias("date"),
            pl.col("OBS_VALUE").cast(pl.Float64, strict=False).alias("rate"),
        )
        .filter(pl.col("REF_AREA").is_in(list(REF_AREA_TO_BANK)))
        .drop_nulls("rate")
        .filter(pl.col("rate").is_not_nan())
    )
    banks = pl.col("REF_AREA").replace_strict(REF_AREA_TO_BANK, return_dtype=pl.String)
    return df.with_columns(banks.alias("bank")).select("bank", "date", "rate").sort("bank", "date")


def instrument(bank: str, on: date) -> str:
    if bank == "fed":
        return "fed funds target (upper)" if on >= US_UPPER_FROM else "fed funds target"
    if bank == "ecb":
        return "ECB DFR" if on >= ECB_DFR_FROM else "ECB MRO (fixed rate)"
    return _INSTRUMENT[bank]


def adjust_rates(series: pl.DataFrame) -> pl.DataFrame:
    """Apply the Fed upper-bound conversion (other banks untouched)."""
    return series.with_columns(
        pl.when((pl.col("bank") == "fed") & (pl.col("date") >= US_UPPER_FROM))
        .then(pl.col("rate") + 0.125)
        .otherwise(pl.col("rate"))
        .alias("rate")
    )


@dataclass(frozen=True)
class RateChange:
    bank: str
    date: date  # first date the new rate is observed
    before: float
    after: float

    @property
    def bp(self) -> float:
        return round((self.after - self.before) * 100.0, 4)


def rate_changes(series: pl.DataFrame) -> list[RateChange]:
    """Day-on-day changes between consecutive non-missing observations (adjusted series)."""
    out: list[RateChange] = []
    adj = adjust_rates(series).sort("bank", "date")
    for bank in adj["bank"].unique(maintain_order=True):
        sub = adj.filter(pl.col("bank") == bank)
        dates = sub["date"].to_list()
        rates = sub["rate"].to_list()
        for i in range(1, len(rates)):
            before = rates[i - 1]
            if bank == "ecb" and dates[i] == ECB_DFR_FROM:
                before -= ECB_SPREAD_MRO_DFR  # MRO -> DFR splice, not a policy move
            if abs(rates[i] - before) >= MIN_CHANGE_PP:  # drops BIS rounding blips
                out.append(RateChange(str(bank), dates[i], before, rates[i]))
    return out
