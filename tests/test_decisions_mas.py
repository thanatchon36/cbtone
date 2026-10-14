"""MAS stance extractor tests.

The strings below are short *illustrative* sentences in MPS phrasing used as unit tests of the
rules. They are NOT the gold set: that lives in fixtures/mas_stance_gold.csv and must be
quoted from cited public statements.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from cbtone.decisions.mas import mas_stance, stance_to_direction

_MAS_URL = re.compile(r"https://(?:web\.archive\.org/web/\d+id_/)?https?://www\.mas\.gov\.sg/")
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
        pytest.skip("mas_stance_gold.csv is empty")
    assert len(rows) >= 20
    for r in rows:
        # MAS's own site, or an Internet Archive snapshot of it (D11)
        assert re.match(
            r"https://(?:web\.archive\.org/web/\d+id_/)?https?://www\.mas\.gov\.sg/", r["url"]
        )
        assert r["label_direction"] in {"tighten", "maintain", "ease"}
    hits = sum(mas_stance(r["decision_paragraph"]).direction == r["label_direction"] for r in rows)
    assert hits >= 18, f"{hits}/{len(rows)}"


@pytest.mark.parametrize(
    ("sentence", "direction"),
    [
        # passive voice (Jan 2015, Apr 2025)
        (
            "MAS will continue with the policy of a modest and gradual appreciation of the S$NEER "
            "policy band. However, the slope of the policy band will be reduced.",
            "ease",
        ),
        (
            "However, the rate of appreciation of the policy band will be reduced slightly.",
            "ease",
        ),
        ("The slope of the S$NEER policy band will be increased slightly.", "tighten"),
        # forward decision that mentions the previous setting (Oct 2021)
        (
            "MAS will therefore raise slightly the slope of the S$NEER policy band, from zero "
            "percent previously.",
            "tighten",
        ),
        # maintain at zero with a long gap (Oct 2016)
        (
            "MAS will therefore maintain the rate of appreciation of the S$NEER policy band at "
            "zero percent.",
            "maintain",
        ),
        # a genuine move to zero is still ease
        ("MAS will reduce the slope of the policy band to zero percent.", "ease"),
        # "has therefore decided" is a decision; the back-reference before it is not
        (
            "In the October 2017 Monetary Policy Statement, MAS kept the slope of the S$NEER "
            "policy band at zero percent. MAS has therefore decided to increase slightly the slope "
            "of the S$NEER policy band, from zero percent previously.",
            "tighten",
        ),
        # back-reference to an earlier review is ignored
        (
            "In its April 2025 monetary policy review, MAS kept the S$NEER policy band on a modest "
            "and gradual appreciation path, but reduced its slope slightly. MAS will maintain the "
            "prevailing rate of appreciation of the S$NEER policy band.",
            "maintain",
        ),
        # moving away from zero appreciation is a tightening
        (
            "Further, we will shift the policy band from that of a zero percent appreciation to "
            "one of modest and gradual appreciation.",
            "tighten",
        ),
        # generic 'easing' outside a decision sentence carries no signal
        (
            "In October 2012, MAS maintained the modest and gradual appreciation path of the "
            "S$NEER policy band. The S$NEER rose on speculation of an early exit from "
            "quantitative easing in the US. MAS will continue with the modest and gradual "
            "appreciation path of the S$NEER policy band.",
            "maintain",
        ),
    ],
)
def test_grammar_cases(sentence: str, direction: str) -> None:
    assert mas_stance(sentence).direction == direction
