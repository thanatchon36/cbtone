"""Daily 2y/10y government yields from free public sources.

* FRED (US Treasury CMT: DGS2, DGS10) - public CSV endpoint.
* ECB Data Portal (euro-area AAA spot curve, 2y/10y).
* Bank of England nominal GLC spot curve (daily xlsx archive).
* RBA table F2 (Australian government 2y/10y, from 2013-05-20).

All fetch through :class:`~cbtone.sources.base.PoliteFetcher` (robots.txt, rate limit, raw
cache with SHA-256) and return ``[date, series, close]`` with yields in percent.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections.abc import Sequence
from datetime import date, datetime

import polars as pl

from cbtone.markets._xlsx import excel_date, read_sheet
from cbtone.markets.fx import SCHEMA, empty_frame
from cbtone.sources.base import PoliteFetcher

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}&cosd={start}&coed={end}"
ECB_URL = (
    "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_{tenor}"
    "?format=csvdata&startPeriod={start}&endPeriod={end}"
)
BOE_URL = (
    "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/glcnominalddata.zip"
)
RBA_URL = "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv"


def _frame(recs: list[tuple[date, str, float]], start: date, end: date) -> pl.DataFrame:
    if not recs:
        return empty_frame()
    d, s, c = zip(*recs, strict=True)
    df = pl.DataFrame({"date": list(d), "series": list(s), "close": list(c)}, schema=SCHEMA)
    return (
        df.filter(pl.col("date").is_between(start, end))
        .unique(["series", "date"])
        .sort("series", "date")
    )


# -- FRED ---------------------------------------------------------------------
def parse_fred(text: str, series_id: str) -> list[tuple[date, str, float]]:
    """FRED CSV: ``observation_date,<ID>``; missing values are ``.`` or empty."""
    out: list[tuple[date, str, float]] = []
    for row in csv.DictReader(io.StringIO(text)):
        raw = (row.get(series_id) or "").strip()
        if raw in ("", "."):
            continue
        out.append((date.fromisoformat(row["observation_date"]), series_id, float(raw)))
    return out


def fetch_fred(
    series_ids: Sequence[str], start: date, end: date, fetcher: PoliteFetcher | None = None
) -> pl.DataFrame:
    f = fetcher or PoliteFetcher()
    recs: list[tuple[date, str, float]] = []
    for sid in series_ids:
        url = FRED_URL.format(id=sid, start=start, end=end)
        recs += parse_fred(f.get("fred", url).content.decode("utf-8"), sid)
    return _frame(recs, start, end)


# -- ECB ----------------------------------------------------------------------
def parse_ecb(text: str, series: str) -> list[tuple[date, str, float]]:
    out: list[tuple[date, str, float]] = []
    for row in csv.DictReader(io.StringIO(text)):
        v = (row.get("OBS_VALUE") or "").strip()
        if v:
            out.append((date.fromisoformat(row["TIME_PERIOD"]), series, float(v)))
    return out


def fetch_ecb_yields(start: date, end: date, fetcher: PoliteFetcher | None = None) -> pl.DataFrame:
    f = fetcher or PoliteFetcher()
    recs: list[tuple[date, str, float]] = []
    for tenor, name in (("2Y", "EA2Y"), ("10Y", "EA10Y")):
        url = ECB_URL.format(tenor=tenor, start=start, end=end)
        recs += parse_ecb(f.get("ecb_sdw", url).content.decode("utf-8"), name)
    return _frame(recs, start, end)


# -- Bank of England ------------------------------------------------------------
def parse_boe_workbook(xlsx: bytes) -> list[tuple[date, str, float]]:
    """2y and 10y from the ``4. spot curve`` sheet (header row labelled ``years:``)."""
    rows = read_sheet(xlsx, "spot curve")
    cols: dict[str, str] = {}
    out: list[tuple[date, str, float]] = []
    for row in rows:
        a = row.get("A")
        if isinstance(a, str) and a.strip().lower().startswith("years"):
            for col, val in row.items():
                if val == 2.0:
                    cols[col] = "GB2Y"
                elif val == 10.0:
                    cols[col] = "GB10Y"
            continue
        if cols and isinstance(a, float):
            d = excel_date(a)
            for col, name in cols.items():
                v = row.get(col)
                if isinstance(v, float):
                    out.append((d, name, v))
    return out


def _boe_years(name: str) -> tuple[int, int] | None:
    m = re.search(r"(\d{4}) to (\d{4}|present)", name)
    if not m:
        return None
    hi = 9999 if m.group(2) == "present" else int(m.group(2))
    return int(m.group(1)), hi


def fetch_boe_yields(start: date, end: date, fetcher: PoliteFetcher | None = None) -> pl.DataFrame:
    """Large (~40 MB) archive zip, cached once; only workbooks overlapping the range are parsed."""
    f = fetcher or PoliteFetcher()
    z = zipfile.ZipFile(io.BytesIO(f.get("boe", BOE_URL).content))
    recs: list[tuple[date, str, float]] = []
    for info in z.infolist():
        yrs = _boe_years(info.filename)
        if not info.filename.endswith(".xlsx") or yrs is None:
            continue
        if yrs[1] < start.year or yrs[0] > end.year:
            continue
        recs += parse_boe_workbook(z.read(info))
    return _frame(recs, start, end)


# -- RBA ------------------------------------------------------------------------
_RBA_IDS = {"FCMYGBAG2D": "AU2Y", "FCMYGBAG10D": "AU10Y"}


def parse_rba_f2(text: str) -> list[tuple[date, str, float]]:
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    hdr = next(i for i, r in enumerate(rows) if r and r[0].strip() == "Series ID")
    cols = {i: _RBA_IDS[v] for i, v in enumerate(rows[hdr]) if v in _RBA_IDS}
    out: list[tuple[date, str, float]] = []
    for r in rows[hdr + 1 :]:
        if not r or not r[0].strip():
            continue
        d = datetime.strptime(r[0].strip(), "%d-%b-%Y").date()
        for i, name in cols.items():
            if i < len(r) and r[i].strip():
                out.append((d, name, float(r[i])))
    return out


def fetch_rba_yields(start: date, end: date, fetcher: PoliteFetcher | None = None) -> pl.DataFrame:
    f = fetcher or PoliteFetcher()
    text = f.get("rba", RBA_URL).content.decode("utf-8-sig")
    return _frame(parse_rba_f2(text), start, end)


def fetch_all_yields(start: date, end: date, fetcher: PoliteFetcher | None = None) -> pl.DataFrame:
    """US, euro-area, UK and Australian 2y/10y daily yields."""
    f = fetcher or PoliteFetcher()
    parts = [
        fetch_fred(["DGS2", "DGS10"], start, end, f),
        fetch_ecb_yields(start, end, f),
        fetch_boe_yields(start, end, f),
        fetch_rba_yields(start, end, f),
    ]
    return pl.concat(parts).sort("series", "date")
