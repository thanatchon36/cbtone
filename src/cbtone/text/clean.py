# ruff: noqa: RUF001
"""Text normalisation for extracted central-bank documents (MISSION.md §1.1, §3)."""

from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿­"))
_QUOTES = {
    **dict.fromkeys(map(ord, "“”„‟«»"), '"'),
    **dict.fromkeys(map(ord, "‘’‚‛′"), "'"),
}
_DASHES = dict.fromkeys(map(ord, "‐‑‒–−﹘﹣－"), "-")
_EM_DASHES = dict.fromkeys(map(ord, "—―"), " - ")

_HYPHEN_BREAK = re.compile(r"(?<=[^\W\d_])-[ \t]*\r?\n[ \t]*(?=[a-z])")
_SPACES = re.compile(r"[^\S\n]+")
_SPACE_AROUND_NL = re.compile(r" ?\n ?")
_MANY_NL = re.compile(r"\n{3,}")


def normalize(text: str) -> str:
    """Return a cleaned copy of ``text``.

    NFKC, straight quotes, ASCII hyphen for dashes, zero-width characters removed,
    PDF line-break hyphenation undone ("infla-\\ntion" -> "inflation"), runs of
    spaces collapsed and 3+ newlines reduced to a paragraph break.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Soft hyphens / zero-width chars first so "infla-​\ntion" still joins.
    text = text.translate(_ZERO_WIDTH)
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_QUOTES).translate(_DASHES).translate(_EM_DASHES)
    text = _HYPHEN_BREAK.sub("", text)
    text = _SPACES.sub(" ", text)
    text = _SPACE_AROUND_NL.sub("\n", text)
    text = _MANY_NL.sub("\n\n", text)
    return text.strip()
