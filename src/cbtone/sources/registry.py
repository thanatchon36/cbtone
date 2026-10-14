"""Bank -> adapter lookup and the per-(bank, doc_type) redistribution map (DECISIONS D8)."""

from __future__ import annotations

import importlib
import inspect
from typing import get_args

from cbtone.schema import Bank
from cbtone.sources.base import PoliteFetcher, SourceAdapter

BANKS: tuple[str, ...] = get_args(Bank)

# From docs/sources/<bank>.md and LICENSES.md. Anything not listed is withheld (fail closed).
REDISTRIBUTABLE: dict[str | tuple[str, str], bool] = {
    "fed": True,  # public domain (federalreserve.gov/disclaimer.htm)
    "ecb": True,
    ("ecb", "press_conference"): False,  # D8: authored documents need prior authorisation
    "mas": False,  # D7; terms require prior written permission
    "pboc": False,  # D10; terms unverified
}


def adapter_class(bank: str) -> type[SourceAdapter]:
    """The ``SourceAdapter`` subclass in ``cbtone.sources.<bank>`` whose ``bank`` matches."""
    if bank not in BANKS:
        raise ValueError(f"unknown bank {bank!r}; expected one of {', '.join(BANKS)}")
    module = importlib.import_module(f"cbtone.sources.{bank}")
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, SourceAdapter) and getattr(obj, "bank", None) == bank:
            return obj
    raise ValueError(f"no SourceAdapter with bank={bank!r} in {module.__name__}")


def make_adapter(bank: str, fetcher: PoliteFetcher) -> SourceAdapter:
    return adapter_class(bank)(fetcher)
