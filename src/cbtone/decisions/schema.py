"""Output schema of the policy-decisions table."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict

from cbtone.schema import Bank

Direction = Literal["hike", "hold", "cut"]
DecisionSource = Literal["bis", "bank", "mas_table", "mas_text"]


class Decision(BaseModel):
    """One policy decision (or scheduled meeting outcome) of one central bank.

    ``date`` is the announcement/meeting date when the decision could be matched to a meeting,
    otherwise the date the rate changed (``unscheduled=True``). ``effective_date`` is the date
    the BIS series shows the new rate (can lag the announcement, e.g. ECB main refinancing rate).
    """

    model_config = ConfigDict(frozen=True)

    bank: Bank
    date: dt.date
    direction: Direction
    magnitude_bp: float  # signed; 0.0 for holds; NaN for MAS (no published parameters)
    rate_after: float | None = None
    next_direction: Direction | None = None
    next_date: dt.date | None = None
    source: DecisionSource
    policy_instrument: str
    unscheduled: bool = False
    effective_date: dt.date | None = None
