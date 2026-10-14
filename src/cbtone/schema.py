"""Core data schemas (pydantic v2). See MISSION.md §1.1 and paper §Data."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Bank = Literal["fed", "ecb", "boe", "rba", "mas", "bi", "bnm", "pboc", "bot"]
DocType = Literal[
    "statement",  # policy decision statement / press release
    "minutes",
    "press_conference",  # transcript, intro statement and/or Q&A
    "mps",  # MAS Monetary Policy Statement
    "communique",
    "other",
]
Language = Literal["en", "id", "ms", "zh", "th"]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Section(BaseModel):
    """A paragraph-level block of a document, in reading order."""

    model_config = ConfigDict(frozen=True)

    heading: str | None = None
    text: str


class Document(BaseModel):
    """One central-bank communication in one language."""

    model_config = ConfigDict(frozen=True)

    bank: Bank
    date: date  # policy-meeting / decision date the document belongs to
    published_at_utc: datetime | None = None  # release timestamp, if known
    doc_type: DocType
    language: Language
    parallel_id: str | None = None  # shared by translations of the same document
    title: str
    text: str
    sections: list[Section] = Field(default_factory=list)
    url: str
    sha256: str  # of the raw fetched bytes
    fetched_at: datetime

    @property
    def doc_id(self) -> str:
        return f"{self.bank}:{self.date.isoformat()}:{self.doc_type}:{self.language}"
