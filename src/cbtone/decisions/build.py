"""Assemble ``decisions.parquet`` from BIS rate changes, meeting calendars and MAS text."""

from __future__ import annotations

import bisect
import math
from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import cast

import polars as pl

from cbtone.decisions.bis import instrument, parse_bis_csv, rate_changes
from cbtone.decisions.mas import MasStance, TableDecision, stance_to_direction
from cbtone.decisions.schema import Decision, Direction
from cbtone.schema import Bank

# Calendar days after a meeting within which a rate change counts as that meeting's outcome.
# Spec default is 3; the ECB's MRO changes took effect up to ~6 days after the announcement.
DEFAULT_WINDOW_DAYS = 3
BANK_WINDOW_DAYS: dict[str, int] = {"ecb": 7}
PRE_DAYS = 3  # a change up to 3 days *before* the recorded meeting date still matches

SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "bank": pl.String,
    "date": pl.Date,
    "direction": pl.String,
    "magnitude_bp": pl.Float64,
    "rate_after": pl.Float64,
    "next_direction": pl.String,
    "next_date": pl.Date,
    "source": pl.String,
    "policy_instrument": pl.String,
    "unscheduled": pl.Boolean,
    "effective_date": pl.Date,
}


def _direction(bp: float) -> Direction:
    return "hike" if bp > 0 else "cut"


def bis_decisions(
    bis_csv: bytes | pl.DataFrame,
    meetings: Iterable[tuple[str, date]],
    window_days: dict[str, int] | None = None,
) -> list[Decision]:
    """Hike/cut/hold rows from BIS rate changes and meeting dates.

    Rules: a meeting with no rate change in ``[date - 3, date + window]`` is a hold; a change
    with no such meeting is ``unscheduled=True``. Banks with no meetings at all (calendar
    unknown) get changes only, ``unscheduled=False``, and no holds. Meetings after the last
    BIS observation (+window) are skipped, since a hold could not be verified.
    """
    series = parse_bis_csv(bis_csv) if isinstance(bis_csv, bytes) else bis_csv
    windows = {**BANK_WINDOW_DAYS, **(window_days or {})}
    by_bank_meet: dict[str, list[date]] = {}
    for bank, d in meetings:
        by_bank_meet.setdefault(bank, []).append(d)
    changes_by_bank: dict[str, list[tuple[date, float, float]]] = {}
    for c in rate_changes(series):
        changes_by_bank.setdefault(c.bank, []).append((c.date, c.bp, c.after))

    out: list[Decision] = []
    for bank in series["bank"].unique(maintain_order=True):
        b = str(bank)
        sub = series.filter(pl.col("bank") == b)
        sdates, srates = sub["date"].to_list(), sub["rate"].to_list()
        first, last = sdates[0], sdates[-1]
        win = windows.get(b, DEFAULT_WINDOW_DAYS)
        meets = sorted(set(by_bank_meet.get(b, [])))
        changes = changes_by_bank.get(b, [])
        matched: dict[date, list[tuple[date, float, float]]] = {m: [] for m in meets}
        for ch in changes:
            cd = ch[0]
            # latest meeting on/before the change, else the earliest within PRE_DAYS after it
            i = bisect.bisect_right(meets, cd) - 1
            m: date | None = None
            if i >= 0 and (cd - meets[i]).days <= win:
                m = meets[i]
            elif i + 1 < len(meets) and (meets[i + 1] - cd).days <= PRE_DAYS:
                m = meets[i + 1]
            if m is None:
                out.append(
                    Decision(
                        bank=cast(Bank, b),
                        date=cd,
                        direction=_direction(ch[1]),
                        magnitude_bp=ch[1],
                        rate_after=ch[2],
                        source="bis",
                        policy_instrument=instrument(b, cd),
                        unscheduled=bool(meets),
                        effective_date=cd,
                    )
                )
            else:
                matched[m].append(ch)
        for m, chs in matched.items():
            if chs:
                net = round(sum(c[1] for c in chs), 4)
                direction: Direction = _direction(net) if net != 0 else "hold"
                out.append(
                    Decision(
                        bank=cast(Bank, b),
                        date=m,
                        direction=direction,
                        magnitude_bp=net,
                        rate_after=chs[-1][2],
                        source="bis",
                        policy_instrument=instrument(b, chs[-1][0]),
                        effective_date=chs[-1][0],
                    )
                )
            elif first <= m and m + timedelta(days=win) <= last:
                k = bisect.bisect_right(sdates, m) - 1
                out.append(
                    Decision(
                        bank=cast(Bank, b),
                        date=m,
                        direction="hold",
                        magnitude_bp=0.0,
                        rate_after=_adj_rate(b, m, srates[k]),
                        source="bis",
                        policy_instrument=instrument(b, m),
                        effective_date=m,
                    )
                )
    return out


def _adj_rate(bank: str, on: date, rate: float) -> float:
    from cbtone.decisions.bis import US_UPPER_FROM

    return rate + 0.125 if bank == "fed" and on >= US_UPPER_FROM else rate


def mas_decisions(
    stances: Iterable[tuple[date, MasStance]], min_confidence: float = 0.5
) -> list[Decision]:
    """MAS rows (tighten/maintain/ease -> hike/hold/cut), magnitude NaN, no rate level."""
    return [
        Decision(
            bank="mas",
            date=d,
            direction=stance_to_direction(s.direction),
            magnitude_bp=math.nan,
            rate_after=None,
            source="mas_text",
            policy_instrument="S$NEER band",
        )
        for d, s in stances
        if s.confidence >= min_confidence
    ]


def mas_table_decisions(rows: Iterable[TableDecision]) -> list[Decision]:
    """MAS rows from the bank's own decision table (authoritative; D13)."""
    return [
        Decision(
            bank="mas",
            date=r.date,
            direction=stance_to_direction(r.direction),
            magnitude_bp=math.nan,
            rate_after=None,
            source="mas_table",
            policy_instrument="S$NEER band",
            unscheduled=r.unscheduled,
        )
        for r in rows
    ]


def _to_frame(decisions: Sequence[Decision]) -> pl.DataFrame:
    if not decisions:
        return pl.DataFrame(schema=SCHEMA)
    df = pl.DataFrame([d.model_dump() for d in decisions], schema_overrides=SCHEMA)
    df = df.sort("bank", "date", "source")
    return df.with_columns(
        pl.col("direction").shift(-1).over("bank").alias("next_direction"),
        pl.col("date").shift(-1).over("bank").alias("next_date"),
    ).select(list(SCHEMA))


def build_decisions(
    bis_csv: bytes | pl.DataFrame | None,
    meetings: Iterable[tuple[str, date]] = (),
    mas_stances: Iterable[tuple[date, MasStance]] = (),
    out_path: Path | None = None,
    *,
    mas_table: Iterable[TableDecision] = (),
) -> pl.DataFrame:
    """Decisions table; writes parquet to ``out_path`` (e.g. data/corpus/decisions.parquet).

    MAS: the bank's own decision table wherever it reaches; the text extractor only for
    statements dated after the table's last row.
    """
    meetings = list(meetings)
    table = list(mas_table)
    last = max((r.date for r in table), default=None)
    rows: list[Decision] = []
    if bis_csv is not None:
        rows += bis_decisions(bis_csv, meetings)
    rows += mas_table_decisions(table)
    rows += mas_decisions((d, s) for d, s in mas_stances if last is None or d > last)
    df = _to_frame(rows)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out_path)
    return df


def meetings_from_documents(documents: pl.DataFrame) -> list[tuple[str, date]]:
    """(bank, date) of ``statement`` documents (MAS ``mps`` handled by the stance extractor)."""
    sel = documents.filter(pl.col("doc_type") == "statement", pl.col("bank") != "mas").select(
        "bank", "date"
    )
    return [(str(b), d) for b, d in sel.unique().iter_rows()]


def mas_stances_from_documents(documents: pl.DataFrame) -> list[tuple[date, MasStance]]:
    from cbtone.decisions.mas import mas_stance

    sel = documents.filter(
        pl.col("bank") == "mas", pl.col("doc_type") == "mps", pl.col("language") == "en"
    ).select("date", "text")
    return [(d, mas_stance(t)) for d, t in sel.iter_rows()]


def build_from_corpus(
    bis_csv: bytes | pl.DataFrame | None,
    documents_path: Path = Path("data/corpus/documents.parquet"),
    out_path: Path = Path("data/corpus/decisions.parquet"),
    mas_table: Iterable[TableDecision] = (),
) -> pl.DataFrame:
    docs = pl.read_parquet(documents_path)
    return build_decisions(
        bis_csv,
        meetings_from_documents(docs),
        mas_stances_from_documents(docs),
        out_path,
        mas_table=mas_table,
    )
