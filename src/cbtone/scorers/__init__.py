"""Tone scorers (MISSION §3): dictionary, finance-tuned transformer, local LLM, fine-tuned model.

``get_scorer(name, **kw)`` builds a registered scorer; heavy dependencies load lazily.
"""

from __future__ import annotations

from typing import Any

from cbtone.scorers.base import DOC_CHAR_CAP, ScoreCache, Scorer, ToneScore

SCORERS = ("dict", "fomc-roberta", "llm", "ft")


def get_scorer(name: str, **kw: Any) -> Scorer:
    """``dict`` | ``fomc-roberta`` | ``llm`` | ``ft`` (``ft`` needs ``model_dir=``)."""
    if name == "dict":
        from cbtone.scorers.dictionary import DictionaryScorer

        return DictionaryScorer(**kw)
    if name == "fomc-roberta":
        from cbtone.scorers.transformer import TransformerScorer

        return TransformerScorer("fomc-roberta", **kw)
    if name == "llm":
        from cbtone.scorers.llm import LLMScorer

        return LLMScorer(**kw)
    if name == "ft":
        from cbtone.scorers.finetuned import FineTunedScorer

        model_dir = kw.pop("model_dir")
        return FineTunedScorer.load(model_dir, **kw)
    raise ValueError(f"unknown scorer {name!r}; expected one of {', '.join(SCORERS)}")


__all__ = ["DOC_CHAR_CAP", "SCORERS", "ScoreCache", "Scorer", "ToneScore", "get_scorer"]
