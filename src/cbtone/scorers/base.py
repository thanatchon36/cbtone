"""Common scorer interface (MISSION §3; RESEARCH_QUESTIONS.md §0.5).

Every scorer maps text to a ``ToneScore`` with probabilities over {hawkish, dovish, neutral} and
``index = hawkish_p - dovish_p`` in [-1, 1]. Document scoring goes through
``cbtone.text.paragraphs.policy_text`` so that every scorer reads the same pre-registered input
(tagged decision / forward-guidance / outlook / risks paragraphs, capped at 6,000 characters).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cbtone.schema import Document, Language

DOC_CHAR_CAP = 6000  # RESEARCH_QUESTIONS.md §0.5; budget ladder step 2 lowers it to 3000
_TOL = 1e-6


class ToneScore(BaseModel):
    """Tone of one text unit (sentence or document)."""

    model_config = ConfigDict(frozen=True)

    hawkish_p: float = Field(ge=0.0, le=1.0)
    dovish_p: float = Field(ge=0.0, le=1.0)
    neutral_p: float = Field(ge=0.0, le=1.0)
    index: float = Field(ge=-1.0, le=1.0)
    evidence_spans: list[str] = Field(default_factory=list)
    scorer_id: str
    model_digest: str | None = None
    prompt_id: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> ToneScore:
        total = self.hawkish_p + self.dovish_p + self.neutral_p
        if abs(total - 1.0) > 1e-3:
            raise ValueError(f"probabilities sum to {total:.4f}, not 1")
        if abs(self.index - (self.hawkish_p - self.dovish_p)) > 1e-3:
            raise ValueError("index must equal hawkish_p - dovish_p")
        return self

    @classmethod
    def from_probs(
        cls,
        hawkish: float,
        dovish: float,
        neutral: float,
        *,
        scorer_id: str,
        evidence_spans: Sequence[str] = (),
        model_digest: str | None = None,
        prompt_id: str | None = None,
    ) -> ToneScore:
        """Normalise non-negative weights to probabilities and derive the index."""
        h, d, n = (max(0.0, float(x)) for x in (hawkish, dovish, neutral))
        total = h + d + n
        if total <= _TOL:
            h, d, n, total = 0.0, 0.0, 1.0, 1.0
        h, d, n = h / total, d / total, n / total
        return cls(
            hawkish_p=h,
            dovish_p=d,
            neutral_p=n,
            index=max(-1.0, min(1.0, h - d)),
            evidence_spans=list(evidence_spans),
            scorer_id=scorer_id,
            model_digest=model_digest,
            prompt_id=prompt_id,
        )

    @property
    def label(self) -> str:
        """Argmax class: hawkish / dovish / neutral (ties resolve to neutral)."""
        best = max(self.hawkish_p, self.dovish_p, self.neutral_p)
        if self.neutral_p == best:
            return "neutral"
        return "hawkish" if self.hawkish_p == best else "dovish"


class Scorer(ABC):
    """Base class. Subclasses implement ``score_text`` and declare the languages they read."""

    scorer_id: str
    languages: frozenset[str] = frozenset({"en"})
    model_digest: str | None = None
    prompt_id: str | None = None

    def supports(self, lang: str) -> bool:
        return lang in self.languages

    @abstractmethod
    def score_text(self, text: str, lang: Language = "en") -> ToneScore:
        """Score one text unit (sentence or pre-selected document text)."""

    def score_sentences(self, sentences: Sequence[str], lang: Language = "en") -> list[ToneScore]:
        return [self.score_text(s, lang) for s in sentences]

    def score_document(self, doc: Document, cap: int = DOC_CHAR_CAP) -> ToneScore:
        """Score the pre-registered policy text of ``doc`` (RESEARCH_QUESTIONS.md §0.5)."""
        from cbtone.text.paragraphs import policy_text

        return self.score_text(policy_text(doc, cap=cap), doc.language)


class ScoreCache:
    """Content-hash cache of ``ToneScore`` JSON in SQLite, so long runs are resumable.

    Key = sha256(scorer_id | model_digest | prompt_id | variant | text). ``variant`` separates
    e.g. masked from unmasked input or temperature settings.
    """

    def __init__(self, path: Path | str = Path("data/cache/scores.sqlite")) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS scores (key TEXT PRIMARY KEY, value TEXT)")
        self._db.commit()

    @staticmethod
    def key(
        scorer_id: str,
        text: str,
        *,
        model_digest: str | None = None,
        prompt_id: str | None = None,
        variant: str = "",
    ) -> str:
        raw = "\x1f".join([scorer_id, model_digest or "", prompt_id or "", variant, text])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> ToneScore | None:
        with self._lock:
            row = self._db.execute("SELECT value FROM scores WHERE key = ?", (key,)).fetchone()
        return ToneScore.model_validate(json.loads(row[0])) if row else None

    def put(self, key: str, score: ToneScore) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO scores (key, value) VALUES (?, ?)",
                (key, score.model_dump_json()),
            )
            self._db.commit()

    def __len__(self) -> int:
        with self._lock:
            return int(self._db.execute("SELECT COUNT(*) FROM scores").fetchone()[0])

    def close(self) -> None:
        self._db.close()
