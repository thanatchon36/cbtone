"""Rule-based stance extractor for MAS Monetary Policy Statements (S$NEER policy band).

MAS does not publish numeric parameters, so the stance is categorical:
tighten (steeper slope / re-centre up), maintain, ease (flatter slope, zero appreciation,
re-centre down). ``parameters`` lists which of slope / width / centre the statement *changed*;
"no change to the slope and width" clauses are discarded before matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from bs4 import BeautifulSoup

Stance = Literal["tighten", "maintain", "ease"]
Parameter = Literal["slope", "width", "centre"]

_SLOPE_NOUN = r"(?:slope|rate of appreciation|pace of appreciation|rate of crawl)"
_GAP = r"(?:[\w$\-]+\W+){0,5}?"

_NEGATED = re.compile(
    r"\b(?:with\s+)?(?:no|without\s+any)\s+(?:further\s+)?change[s]?\s+(?:to|in)\b[^.;]*",
    re.I,
)
_RETRO = re.compile(
    r"\b(?:previous|previously|last|since|had been|was|were|in (?:january|april|july|october"
    r"|march) (?:19|20)\d\d|at (?:its|the) (?:previous|last))\b",
    re.I,
)
# Future/decision sentences announce today's decision, even when they cite the previous setting.
_DECIDES = re.compile(r"\b(?:will|decided)\b", re.I)
_MONTH_YEAR = re.compile(
    r"\b(?:january|february|march|april|may|june|july|august|september|october|november"
    r"|december)\s+(?:19|20)\d\d\b|\blast year\b",
    re.I,
)
_FROM_ZERO = re.compile(r"\bfrom\b[^.;]{0,40}\bzero\b[^.;]*?\bto\b", re.I)
_TOPIC = re.compile(r"neer|policy band|appreciation|slope|re-?cent", re.I)

_TIGHTEN_SLOPE = re.compile(
    rf"\b(?:increase|raise|steepen|strengthen|step up)[a-z]*\W+{_GAP}{_SLOPE_NOUN}", re.I
)
_EASE_SLOPE = re.compile(
    rf"\b(?:reduce|lower|decrease|trim|flatten|cut|ease)[a-z]*\W+{_GAP}{_SLOPE_NOUN}", re.I
)
_ZERO = re.compile(
    r"(?<!from )\bzero\s+(?:per\s?cent|%)|\bzero\s+appreciation|\bappreciation\s+to\s+zero",
    re.I,
)
_PASSIVE = rf"{_SLOPE_NOUN}\W+{_GAP}(?:will\s+be|is\s+being|has\s+been|to\s+be)\s+"
_TIGHTEN_PASSIVE = re.compile(rf"{_PASSIVE}(?:increased|raised|steepened)", re.I)
_EASE_PASSIVE = re.compile(rf"{_PASSIVE}(?:reduced|lowered|decreased|flattened)", re.I)
_MAINTAIN = re.compile(
    rf"\b(?:maintain|continue|keep|retain|leave)[a-z]*\W+{_GAP}"
    rf"(?:{_SLOPE_NOUN}|policy band|appreciation|S\$NEER|current policy|prevailing|zero)",
    re.I,
)
_MAINTAIN_ZERO = re.compile(
    r"\b(?:maintain|continue|keep)[a-z]*\W+(?:[\w$\-]+\W+){0,12}?zero", re.I
)
_RECENTRE = re.compile(r"\bre-?cent(?:re|er)[a-z]*\b[^.;]*", re.I)
_UP = re.compile(r"\b(?:up|upward|upwards|higher|raise)\b", re.I)
_DOWN = re.compile(r"\b(?:down|downward|downwards|lower|below)\b", re.I)
_WIDTH = re.compile(r"\b(?:widen|narrow|increase the width|reduce the width)[a-z]*\b", re.I)
_TIGHTEN_GENERIC = re.compile(r"\btighten(?:ing|ed)?\b", re.I)
_EASE_GENERIC = re.compile(r"\b(?:eas(?:e|ing|ed)|loosen(?:ing)?)\b", re.I)


@dataclass(frozen=True)
class MasStance:
    direction: Stance
    parameters: frozenset[Parameter]
    confidence: float  # 0.0 = nothing recognised (direction defaults to maintain)


_DIR_TO_DECISION = {"tighten": "hike", "maintain": "hold", "ease": "cut"}


def stance_to_direction(stance: Stance) -> Literal["hike", "hold", "cut"]:
    """tighten -> hike, maintain -> hold, ease -> cut."""
    return _DIR_TO_DECISION[stance]  # type: ignore[return-value]


def _sentences(text: str) -> list[str]:
    text = text.replace("\u2019", "'").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", text) if s]


def _is_current(s: str) -> bool:
    if _DECIDES.search(s):
        return True
    return not (_RETRO.search(s) or _MONTH_YEAR.search(s))


def _analyse(sentence: str) -> tuple[set[str], set[Parameter], bool]:
    """Return (signals, changed parameters, maintain_flag) for one sentence."""
    s = _NEGATED.sub(" ", sentence)
    signals: set[str] = set()
    params: set[Parameter] = set()
    maintain = bool(_MAINTAIN.search(s))
    if _TIGHTEN_SLOPE.search(s) or _TIGHTEN_PASSIVE.search(s):
        signals.add("tighten")
        params.add("slope")
    if _EASE_SLOPE.search(s) or _EASE_PASSIVE.search(s):
        signals.add("ease")
        params.add("slope")
    if _FROM_ZERO.search(s):  # moving off a zero-appreciation path
        signals.add("tighten")
        params.add("slope")
    elif _ZERO.search(s) and not _MAINTAIN_ZERO.search(s):
        signals.add("ease")
        params.add("slope")
    for m in _RECENTRE.finditer(s):
        params.add("centre")
        clause = m.group(0)
        if _UP.search(clause):
            signals.add("tighten")
        elif _DOWN.search(clause):
            signals.add("ease")
    if _WIDTH.search(s):
        params.add("width")
    if not signals and not params and _DECIDES.search(s):
        if _TIGHTEN_GENERIC.search(s) and not re.search(r"\bnot\b|\bno need\b", s, re.I):
            signals.add("tighten")
        elif _EASE_GENERIC.search(s) and not re.search(r"\bnot\b|\bno need\b", s, re.I):
            signals.add("ease")
    return signals, params, maintain


def mas_stance(text: str) -> MasStance:
    """Classify the policy-band decision in an MPS (or its decision paragraph)."""
    sents = [s for s in _sentences(text) if _TOPIC.search(s)]
    analysed = [(s, *_analyse(s)) for s in sents]
    # Prefer the decision sentences; fall back to any non-retrospective sentence.
    decided = [a for a in analysed if _DECIDES.search(a[0]) and (a[1] or a[2] or a[3])]
    current = decided or [a for a in analysed if _is_current(a[0])] or analysed
    signals: set[str] = set()
    params: set[Parameter] = set()
    maintain = False
    for _, sg, pa, mt in current:
        signals |= sg
        params |= pa
        maintain = maintain or mt
    if "tighten" in signals and "ease" not in signals:
        return MasStance("tighten", frozenset(params), 0.9)
    if "ease" in signals and "tighten" not in signals:
        return MasStance("ease", frozenset(params), 0.9)
    if signals:  # conflicting evidence: prefer a slope-related reading, flag low confidence
        slope_sig = {"tighten", "ease"} & signals
        pick: Stance = "ease" if "ease" in slope_sig else "tighten"
        return MasStance(pick, frozenset(params), 0.4)
    if maintain or params:  # width/centre-only changes carry no tighten/ease signal
        return MasStance("maintain", frozenset(params), 0.9 if maintain else 0.6)
    return MasStance("maintain", frozenset(), 0.0)


# -- MAS's own "Past Monetary Policy Decisions" table (DECISIONS D13) ----------------------


@dataclass(frozen=True)
class TableDecision:
    date: date
    direction: Stance
    parameters: frozenset[Parameter]
    unscheduled: bool  # "*" in the table marks an off-cycle decision


_TABLE_DATE = re.compile(r"(\d{1,2} [A-Z][a-z]{2} \d{4})(\*?)")


def _table_direction(slope: str, centre: str) -> Stance:
    s, c = slope.lower(), centre.lower()
    tighten = "increase" in s or "upward" in c
    ease = "reduce" in s or "set at 0" in s or "downward" in c
    if tighten and ease:
        raise ValueError(f"conflicting table row: slope={slope!r} centre={centre!r}")
    return "tighten" if tighten else "ease" if ease else "maintain"


def parse_decision_table(html: bytes) -> list[TableDecision]:
    """Rows of MAS's decision table: date | slope | width | centre ("-" = unchanged)."""
    table = BeautifulSoup(html, "lxml").find("table")
    if table is None:
        return []
    out: list[TableDecision] = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        m = _TABLE_DATE.match(cells[0]) if len(cells) == 4 else None
        if m is None:
            continue
        slope, width, centre = cells[1:]
        params = frozenset(
            p
            for p, v in (("slope", slope), ("width", width), ("centre", centre))
            if v.strip("-\u2013 ")
        )
        out.append(
            TableDecision(
                date=datetime.strptime(m.group(1), "%d %b %Y").date(),
                direction=_table_direction(slope, centre),
                parameters=params,  # type: ignore[arg-type]
                unscheduled=bool(m.group(2)),
            )
        )
    return sorted(out, key=lambda r: r.date)
