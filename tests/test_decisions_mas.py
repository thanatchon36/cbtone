"""MAS stance extractor tests.

The strings below are short *illustrative* sentences in MPS phrasing used as unit tests of the
rules. They are NOT the gold set: that lives in fixtures/mas_stance_gold.csv and must be
quoted from cited public statements.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from cbtone.decisions.mas import mas_stance, stance_to_direction

GOLD = Path(__file__).parent / "fixtures" / "mas_stance_gold.csv"

CASES = [
    (
        "MAS will increase the rate of appreciation of the S$NEER policy band slightly. "
        "There will be no change to the width of the policy band and the level at which it is "
        "centred.",
        "tighten",
        {"slope"},
    ),
    (
        "MAS will reduce slightly the rate of appreciation of the S$NEER policy band, with no "
        "change to the width and the level at which it is centred.",
        "ease",
        {"slope"},
    ),
    (
        "MAS will re-centre the mid-point of the policy band up to the prevailing level of the "
        "S$NEER. There will be no change to the slope and the width of the policy band.",
        "tighten",
        {"centre"},
    ),
    (
        "MAS will maintain the prevailing rate of appreciation of the S$NEER policy band. "
        "There will be no change to the width of the policy band and the level at which it is "
        "centred.",
        "maintain",
        set(),
    ),
    (
        "MAS will adopt zero percent per annum appreciation of the policy band, and re-centre "
        "the mid-point of the band at the prevailing level of the S$NEER.",
        "ease",
        {"slope", "centre"},
    ),
    (
        "MAS will continue with its policy of zero percent per annum appreciation of the "
        "S$NEER policy band.",
        "maintain",
        set(),
    ),
    ("MAS will widen the policy band.", "maintain", {"width"}),
]


@pytest.mark.parametrize(("text", "direction", "params"), CASES)
def test_rules(text: str, direction: str, params: set[str]) -> None:
    r = mas_stance(text)
    assert r.direction == direction
    assert set(r.parameters) == params
    assert r.confidence >= 0.5


def test_retrospective_sentence_does_not_override_decision() -> None:
    text = (
        "In October 2021, MAS had increased the rate of appreciation of the S$NEER policy band. "
        "MAS will maintain the prevailing rate of appreciation of the S$NEER policy band."
    )
    assert mas_stance(text).direction == "maintain"


def test_unrecognised_text_has_zero_confidence() -> None:
    assert mas_stance("Core inflation is expected to average 2% this year.").confidence == 0.0


def test_mapping() -> None:
    assert [stance_to_direction(s) for s in ("tighten", "maintain", "ease")] == [
        "hike",
        "hold",
        "cut",
    ]


def _gold_rows() -> list[dict[str, str]]:
    lines = [ln for ln in GOLD.read_text().splitlines() if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def test_gold_set() -> None:
    rows = _gold_rows()
    if not rows:
        pytest.skip("TODO: mas_stance_gold.csv empty; see docs/sources/NEEDED_mas_decisions.md")
    assert len(rows) >= 20
    for r in rows:
        assert r["url"].startswith("https://www.mas.gov.sg/")
    hits = sum(mas_stance(r["decision_paragraph"]).direction == r["label_direction"] for r in rows)
    assert hits >= 18, f"{hits}/{len(rows)}"
