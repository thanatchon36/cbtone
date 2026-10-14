# ruff: noqa: SIM905
"""Tiny script- and stopword-based language detector for en/id/ms/zh/th (MISSION.md §3)."""

from __future__ import annotations

import re

from cbtone.schema import Language

_WORD = re.compile(r"[a-z]+")

_EN = frozenset(
    "the and of to in is that for with on as are at by this be has have will was it its from "
    "which an or not been their inflation policy".split()
)
# Shared Indonesian/Malay function words score for both; distinctive ones weigh more.
_ID_MS = frozenset(
    "yang dan di untuk dengan dari ini pada akan dalam tidak juga telah oleh sebagai ke itu "
    "atau lebih bank inflasi ekonomi".split()
)
_ID_ONLY = frozenset(
    "karena kebijakan bahwa persen sebesar tetap dapat sehingga namun mencatat "
    "meningkat menurun suku bunga".split()
)
_MS_ONLY = frozenset(
    "kerana bagi dasar peratus kadar ialah sebanyak mengekalkan "
    "daripada mereka beliau sahaja turut bagaimanapun".split()
)


def _is_thai(ch: str) -> bool:
    return "฀" <= ch <= "๿"


def _is_han(ch: str) -> bool:
    return "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿"


def detect_language(text: str) -> Language | None:
    """Guess the language of ``text``; ``None`` if there is too little evidence.

    Script decides th/zh when they make up a meaningful share of letters; otherwise
    Latin-script text is scored on en/id/ms stopwords.
    """
    thai = sum(_is_thai(c) for c in text)
    han = sum(_is_han(c) for c in text)
    latin = sum(("a" <= c <= "z") or ("A" <= c <= "Z") for c in text)
    total = thai + han + latin
    if total == 0:
        return None
    if thai / total >= 0.3:
        return "th"
    if han / total >= 0.3:
        return "zh"
    words = _WORD.findall(text.lower())
    if not words:
        return None
    en = sum(w in _EN for w in words)
    shared = sum(w in _ID_MS for w in words)
    id_only = sum(w in _ID_ONLY for w in words)
    ms_only = sum(w in _MS_ONLY for w in words)
    id_score = shared + 3 * id_only
    ms_score = shared + 3 * ms_only
    best = max(en, id_score, ms_score)
    if best == 0:
        return None
    if en >= id_score and en >= ms_score:
        return "en"
    return "ms" if ms_score > id_score else "id"
