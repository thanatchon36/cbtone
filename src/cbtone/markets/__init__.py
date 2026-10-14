"""Market data (FX and government yields) and event-window changes."""

from cbtone.markets.events import event_window
from cbtone.markets.fx import fetch_fx
from cbtone.markets.registry import FX_TICKERS, REGISTRY, SeriesSpec
from cbtone.markets.yields import (
    fetch_all_yields,
    fetch_boe_yields,
    fetch_ecb_yields,
    fetch_fred,
    fetch_rba_yields,
)

__all__ = [
    "FX_TICKERS",
    "REGISTRY",
    "SeriesSpec",
    "event_window",
    "fetch_all_yields",
    "fetch_boe_yields",
    "fetch_ecb_yields",
    "fetch_fred",
    "fetch_fx",
    "fetch_rba_yields",
]
