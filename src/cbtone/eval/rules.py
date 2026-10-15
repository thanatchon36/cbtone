"""Pre-registered decision rules (RESEARCH_QUESTIONS.md §0.7, §0.9 and per-RQ minimum samples).

These encode thresholds frozen at ``prereg-v1``; changing any constant here is a deviation that
must be recorded in DECISIONS.md and reported in the paper.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

RQ1_MIN_OOS, RQ1_MIN_HIKE, RQ1_MIN_CUT = 40, 8, 8
RQ2_MIN_EVENTS = 30
RQ3_MIN_PAIRS = 30
RQ4C_MIN_POST_CUTOFF = 30
RQ5_MIN_SILVER = 50
MIN_POWERED_BANKS = 3
RQ3_RHO, RQ3_FLIP = 0.70, 0.10
RQ4A_ALPHA, RQ4A_ICC, RQ4A_RHO = 0.667, 0.75, 0.70
RQ4B_MIN_F1 = 0.50
RQ4C_MIN_SHARE = 0.50
RQ5_DROP = 0.10

# REVIEW.md §2 ranges for the "> 2x off literature" sanity rule: (low, high) plausible values.
LITERATURE_RANGES: dict[str, tuple[float, float]] = {
    "fomc_f1_dictionary": (0.50 / 2, min(1.0, 0.50 * 2)),
    "fomc_f1_llm_zero_shot": (0.587 / 2, min(1.0, 0.587 * 2)),
    "fomc_f1_finetuned": (0.717 / 2, min(1.0, 0.717 * 2)),
    "fomc_f1_fomc_roberta": (0.717 / 2, min(1.0, 0.717 * 2)),  # D21: sanity range, not a test
    "tone_policy_pseudo_r2": (0.0, 0.12 * 2),
    "llm_lexicon_corr": (0.49 / 2, min(0.98, 0.49 * 2)),
}


def rq1_powered(n_oos: int, n_hike: int, n_cut: int) -> bool:
    return n_oos >= RQ1_MIN_OOS and n_hike >= RQ1_MIN_HIKE and n_cut >= RQ1_MIN_CUT


def rq2_powered(n_events: int) -> bool:
    return n_events >= RQ2_MIN_EVENTS


def rq3_powered(n_pairs: int) -> bool:
    return n_pairs >= RQ3_MIN_PAIRS


@dataclass(frozen=True)
class MajorityVerdict:
    verdict: str  # "supported" | "refuted" | "untestable"
    n_powered: int
    n_success: int


def majority(
    success_by_bank: Mapping[str, bool], powered_by_bank: Mapping[str, bool]
) -> MajorityVerdict:
    """Strict majority of the powered banks; < 3 powered banks -> untestable (§0.7)."""
    powered = [b for b, ok in powered_by_bank.items() if ok]
    wins = sum(1 for b in powered if success_by_bank.get(b, False))
    if len(powered) < MIN_POWERED_BANKS:
        return MajorityVerdict("untestable", len(powered), wins)
    return MajorityVerdict(
        "supported" if wins * 2 > len(powered) else "refuted", len(powered), wins
    )


def ci_excludes_zero_positive(lo: float, hi: float) -> bool:
    return lo > 0 and hi > 0


def sanity_flags(name: str, value: float, kind: str = "metric") -> list[str]:
    """Reasons a headline number fails the MISSION §0 sanity rules (empty list = passes).

    kind: "metric" (exactly 0/1 is suspicious), "rate" (0 or 100 %), "corr" (> 0.95 suspicious).
    The literature range check applies when ``name`` is in ``LITERATURE_RANGES``.
    """
    flags: list[str] = []
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return [f"{name}: NaN"]
    if kind in ("metric", "rate") and value in (0.0, 1.0):
        flags.append(f"{name}: exactly {value}")
    if kind == "corr" and abs(value) > 0.95:
        flags.append(f"{name}: |corr| {value:.3f} > 0.95")
    if name in LITERATURE_RANGES:
        lo, hi = LITERATURE_RANGES[name]
        if not lo <= value <= hi:
            flags.append(f"{name}: {value:.3f} outside 2x literature range [{lo:.3f}, {hi:.3f}]")
    return flags
