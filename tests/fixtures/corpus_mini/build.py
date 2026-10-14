"""Rebuild this tiny corpus from the adapter test fixtures (offline).

    uv run --no-sync python tests/fixtures/corpus_mini/build.py

Only Fed (public domain) and RBA (CC BY 4.0) text is used, so the files are redistributable.
The fixture HTML files are trimmed real pages; the URLs recorded here are the public index or
press-release locations for the same decisions, not byte-exact fetch URLs.
"""

from __future__ import annotations

import hashlib
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

from cbtone.schema import Document
from cbtone.sources.base import PoliteFetcher, RawResponse
from cbtone.sources.fed import FedAdapter
from cbtone.sources.rba import RBAAdapter
from cbtone.sources.snapshot import build_snapshot

HERE = Path(__file__).resolve().parent
FIX = HERE.parent
FETCHED = datetime(2026, 1, 1, tzinfo=UTC)

FED = [
    ("statement_2013-09-18.htm", "2013-09-18", "monetary20130918a"),
    ("statement_2026-01-28.htm", "2026-01-28", "monetary20260128a"),
]
RBA = [
    ("statement_2023.html", "2023-10-03", "2023"),
    ("statement_2024.html", "2024-12-10", "2024"),
    ("statement_2026.html", "2026-09-29", "2026"),
]


def _raw(path: Path, url: str, ctype: str) -> RawResponse:
    content = path.read_bytes()
    return RawResponse(
        url=url,
        content=content,
        content_type=ctype,
        sha256=hashlib.sha256(content).hexdigest(),
        fetched_at=FETCHED,
        from_cache=True,
    )


def build() -> str:
    docs: list[Document] = []
    with tempfile.TemporaryDirectory() as tmp:
        fetcher = PoliteFetcher(raw_dir=Path(tmp), offline=True)
        fed, rba = FedAdapter(fetcher), RBAAdapter(fetcher)
        for name, iso, slug in FED:
            url = f"https://www.federalreserve.gov/newsevents/pressreleases/{slug}.htm"
            raw = _raw(FIX / "fed" / name, url, "text/html")
            docs += fed.parse(raw, {"doc_type": "statement", "date": iso})
        for name, iso, year in RBA:
            url = f"https://www.rba.gov.au/monetary-policy/int-rate-decisions/{year}/"
            raw = _raw(FIX / "rba" / name, url, "text/html")
            docs += rba.parse(raw, {"doc_type": "statement", "date": iso})
    return build_snapshot(
        docs,
        HERE,
        {"fed": True, "rba": True},
        snapshot_date=date(2026, 10, 14),
    )


if __name__ == "__main__":
    print(build())
