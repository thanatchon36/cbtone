"""Zero-shot LLM tone scorer on a local Ollama server (RESEARCH_QUESTIONS.md §0.5, RQ4).

``LLMScorer`` asks an instruction-tuned model for the probabilities that a text signals a more
hawkish, dovish or neutral *future* monetary-policy stance, as in the zero-shot LLM approach to
central-bank text of Hansen & Kazinnik (2023, ``hansen2023fedspeak``) and Lopez-Lira & Tang
(2023, ``lopezlira2023chatgpt``); the sentence task and labels follow Shah, Paturi & Chava
(2023, ``shah2023trillion``). Because LLM output is sensitive to prompt wording (Sclar et al. 2024,
``sclar2024quantifying``), five registered paraphrases ``P1``..``P5`` are provided (RQ4a), and the
masked variant (``masked=True``) supports the contamination check of H4c.

Call settings follow DECISIONS.md D17: a JSON-schema ``format``, ``think=false``, ``num_ctx=8192``,
``num_predict`` 64 (sentence) or 160 (document). Plain ``format: "json"`` is not used (the model
rambles).
Every call goes through ``ScoreCache``, so a re-run never calls the model again.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Sequence
from importlib import resources
from typing import Any, Literal

import httpx

from cbtone.schema import Document, Language
from cbtone.scorers.base import DOC_CHAR_CAP, ScoreCache, Scorer, ToneScore
from cbtone.text.mask import mask_entities
from cbtone.text.paragraphs import (
    paragraphs_of,
    select_policy_paragraphs,
    tag_paragraph,
)
from cbtone.text.split import split_paragraphs, split_sentences

PROMPT_IDS: tuple[str, ...] = ("P1", "P2", "P3", "P4", "P5")
STRATEGIES: tuple[str, ...] = ("mean", "decision_weighted", "max_abs")
Mode = Literal["sentence", "document"]

DEFAULT_MODEL = "qwen3:4b"
DEFAULT_URL = "http://localhost:11434"
SEED = 20261014
NUM_CTX = 8192
NUM_PREDICT: dict[str, int] = {"sentence": 64, "document": 160}
MAX_ATTEMPTS = 3
DECISION_WEIGHT = 2.0
MAX_EVIDENCE = 3
MAX_EVIDENCE_CHARS = 300
_TOL = 1e-6

_DOC_SUFFIX = (
    '\n\nAlso return up to 3 short verbatim quotes from the text, in the field "evidence", '
    "that most support your judgement."
)
_PROBS = ("hawkish", "dovish", "neutral")


class LLMError(RuntimeError):
    """The LLM backend failed (down, unknown model tag, or three failed attempts)."""


class _BadOutput(Exception):
    """The reply was not usable (invalid JSON, wrong shape, non-finite or all-zero numbers)."""


def _schema(mode: Mode) -> dict[str, Any]:
    props: dict[str, Any] = {k: {"type": "number"} for k in _PROBS}
    if mode == "document":
        props["evidence"] = {"type": "array", "items": {"type": "string"}, "maxItems": MAX_EVIDENCE}
    return {"type": "object", "properties": props, "required": list(_PROBS)}


def load_prompt(prompt: str) -> tuple[str, str]:
    """Return ``(prompt_id, text)`` for a registered variant; the id is ``P1@<sha256[:8]>``."""
    if prompt not in PROMPT_IDS:
        raise ValueError(f"unknown prompt {prompt!r}; registered: {', '.join(PROMPT_IDS)}")
    raw = (resources.files("cbtone") / "data" / "prompts" / f"{prompt}.txt").read_bytes()
    return f"{prompt}@{hashlib.sha256(raw).hexdigest()[:8]}", raw.decode("utf-8").strip()


def _parse(resp: httpx.Response, mode: Mode) -> tuple[float, float, float, list[str]]:
    try:
        content = resp.json()["message"]["content"]
        obj = json.loads(content)
    except (ValueError, KeyError, TypeError) as exc:
        raise _BadOutput(f"invalid JSON reply: {exc}") from exc
    if not isinstance(obj, dict):
        raise _BadOutput("reply is not a JSON object")
    vals: list[float] = []
    for key in _PROBS:
        v = obj.get(key)
        if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v) or v < 0:
            raise _BadOutput(f"field {key!r} missing or not a non-negative number: {v!r}")
        vals.append(float(v))
    if sum(vals) <= _TOL:
        raise _BadOutput("all probabilities are zero")
    evidence: list[str] = []
    raw_ev = obj.get("evidence")
    if mode == "document" and isinstance(raw_ev, list):
        evidence = [
            e.strip()[:MAX_EVIDENCE_CHARS] for e in raw_ev if isinstance(e, str) and e.strip()
        ]
        evidence = evidence[:MAX_EVIDENCE]
    return vals[0], vals[1], vals[2], evidence


class LLMScorer(Scorer):
    """Hawkish/dovish/neutral probabilities from a local Ollama model.

    ``calls_made`` counts HTTP requests to ``/api/chat`` (retries included); ``cache_hits`` counts
    results served from ``ScoreCache`` without a request. Use as a context manager, or call
    ``close``.
    """

    scorer_id = "llm"
    languages = frozenset({"en", "id", "ms", "th", "zh"})

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        prompt: str = "P1",
        *,
        temperature: float = 0.0,
        masked: bool = False,
        cache: ScoreCache | None = None,
        base_url: str = DEFAULT_URL,
        timeout: float = 120.0,
        retry_wait: float = 0.5,
        seed: int = SEED,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.masked = masked
        self.seed = seed
        self.retry_wait = retry_wait
        self.cache = cache if cache is not None else ScoreCache()
        self.prompt_id, self._system = load_prompt(prompt)
        self.calls_made = 0
        self.cache_hits = 0
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)
        self.model_digest = self._resolve_digest()

    # -- lifecycle -----------------------------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> LLMScorer:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- backend -------------------------------------------------------------------------------

    def _resolve_digest(self) -> str:
        """Digest of the model tag from ``/api/tags``; fail clearly if Ollama/the tag is absent."""
        url = str(self._client.base_url)
        try:
            resp = self._client.get("/api/tags")
        except httpx.TransportError as exc:
            raise LLMError(f"Ollama is not reachable at {url}: {exc!r}") from exc
        if resp.status_code != 200:
            raise LLMError(f"Ollama /api/tags returned HTTP {resp.status_code} at {url}")
        try:
            models = resp.json()["models"]
            by_name = {}
            for m in models:
                for name in (m.get("name"), m.get("model")):
                    if isinstance(name, str):
                        by_name[name] = str(m["digest"])
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise LLMError(f"unexpected /api/tags reply from {url}: {exc!r}") from exc
        for tag in (self.model, f"{self.model}:latest" if ":" not in self.model else self.model):
            if tag in by_name:
                return by_name[tag]
        raise LLMError(
            f"model {self.model!r} is not available in Ollama at {url}; "
            f"installed: {sorted(by_name) or 'none'} (try `ollama pull {self.model}`)"
        )

    def _chat(self, system: str, user: str, mode: Mode) -> tuple[float, float, float, list[str]]:
        """One structured chat call; up to ``MAX_ATTEMPTS`` tries on 5xx, timeout or bad JSON."""
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "format": _schema(mode),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {
                "temperature": self.temperature,
                "num_predict": NUM_PREDICT[mode],
                "num_ctx": NUM_CTX,
                "seed": self.seed,
            },
        }
        last = "no attempt"
        for attempt in range(MAX_ATTEMPTS):
            if attempt:
                time.sleep(self.retry_wait * attempt)
            self.calls_made += 1
            try:
                resp = self._client.post("/api/chat", json=payload)
            except httpx.TransportError as exc:  # includes timeouts and connection errors
                last = f"{type(exc).__name__}: {exc}"
                continue
            if resp.status_code >= 500:
                last = f"HTTP {resp.status_code}"
                continue
            if resp.status_code >= 400:  # a client error will not fix itself
                raise LLMError(
                    f"Ollama rejected the request: HTTP {resp.status_code} {resp.text[:200]}"
                )
            try:
                return _parse(resp, mode)
            except _BadOutput as exc:
                last = str(exc)
        raise LLMError(f"LLM call failed after {MAX_ATTEMPTS} attempts: {last}")

    # -- scoring -------------------------------------------------------------------------------

    def _variant(self, mode: Mode) -> str:
        return f"{mode}|masked={int(self.masked)}|T={self.temperature:g}|seed={self.seed}"

    def _score(self, text: str, lang: Language, mode: Mode) -> ToneScore:
        if not text.strip():
            raise ValueError("cannot score empty text")
        if not self.supports(lang):
            raise ValueError(f"LLMScorer does not support language {lang!r}")
        if self.masked:
            text = mask_entities(text, lang)
        key = ScoreCache.key(
            self.scorer_id,
            text,
            model_digest=self.model_digest,
            prompt_id=self.prompt_id,
            variant=self._variant(mode),
        )
        cached = self.cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        system = self._system + (_DOC_SUFFIX if mode == "document" else "")
        h, d, n, evidence = self._chat(system, f"Text:\n{text}", mode)
        score = ToneScore.from_probs(
            h,
            d,
            n,
            scorer_id=self.scorer_id,
            evidence_spans=evidence,
            model_digest=self.model_digest,
            prompt_id=self.prompt_id,
        )
        self.cache.put(key, score)
        return score

    def score_text(self, text: str, lang: Language = "en") -> ToneScore:
        """One call on ``text`` (sentence settings: ``num_predict`` 64, no evidence)."""
        return self._score(text, lang, "sentence")

    def score_sentences(self, sentences: Sequence[str], lang: Language = "en") -> list[ToneScore]:
        """One call per sentence; sentences are never batched into one prompt (RQ4a design)."""
        return [self._score(s, lang, "sentence") for s in sentences]

    def score_document(self, doc: Document, cap: int = DOC_CHAR_CAP) -> ToneScore:
        """Default document mode: one call on ``policy_text(doc)`` (§0.5), with evidence quotes."""
        from cbtone.text.paragraphs import policy_text

        return self._score(policy_text(doc, cap=cap), doc.language, "document")

    # -- sentence-level aggregation (RQ4a) -----------------------------------------------------

    @staticmethod
    def document_sentences(doc: Document, cap: int = DOC_CHAR_CAP) -> list[tuple[str, str]]:
        """``(sentence, paragraph_tag)`` pairs over the same input as ``policy_text(doc, cap)``."""
        paras = select_policy_paragraphs(paragraphs_of(doc), doc.language, cap)
        if not paras:
            paras = split_paragraphs(doc.text[:cap])
        out: list[tuple[str, str]] = []
        for para in paras:
            tag = tag_paragraph(para, doc.language)
            out.extend((s, tag) for s in split_sentences(para, doc.language) if s.strip())
        return out

    def score_document_by_sentences(
        self, doc: Document, strategy: str = "mean", cap: int = DOC_CHAR_CAP
    ) -> ToneScore:
        """Score each sentence of the policy text separately, then ``aggregate`` them."""
        pairs = self.document_sentences(doc, cap)
        if not pairs:
            raise ValueError(f"no sentences to score in {doc.doc_id}")
        scores = self.score_sentences([s for s, _ in pairs], doc.language)
        return self.aggregate(scores, strategy, tags=[t for _, t in pairs])

    def aggregate(
        self,
        sentence_scores: Sequence[ToneScore],
        strategy: str = "mean",
        *,
        tags: Sequence[str] | None = None,
    ) -> ToneScore:
        """Combine sentence scores into one document score.

        ``mean``: mean probabilities. ``decision_weighted``: weighted mean where sentences from
        paragraphs tagged ``decision`` (``tags``, one per score) weigh 2 and others 1. ``max_abs``:
        the sentence with the largest ``|index|`` (first on ties).
        """
        if strategy not in STRATEGIES:
            raise ValueError(f"unknown strategy {strategy!r}; use one of {STRATEGIES}")
        if not sentence_scores:
            raise ValueError("no sentence scores to aggregate")
        if strategy == "max_abs":
            best = max(sentence_scores, key=lambda s: abs(s.index))
            return self._combine([best], [1.0])
        weights = [1.0] * len(sentence_scores)
        if strategy == "decision_weighted":
            if tags is None or len(tags) != len(sentence_scores):
                raise ValueError("decision_weighted needs one paragraph tag per sentence score")
            weights = [DECISION_WEIGHT if t == "decision" else 1.0 for t in tags]
        return self._combine(sentence_scores, weights)

    def _combine(self, scores: Sequence[ToneScore], weights: Sequence[float]) -> ToneScore:
        total = sum(weights)
        h = sum(w * s.hawkish_p for w, s in zip(weights, scores, strict=True)) / total
        d = sum(w * s.dovish_p for w, s in zip(weights, scores, strict=True)) / total
        n = sum(w * s.neutral_p for w, s in zip(weights, scores, strict=True)) / total
        evidence = list(dict.fromkeys(e for s in scores for e in s.evidence_spans))[:MAX_EVIDENCE]
        return ToneScore.from_probs(
            h,
            d,
            n,
            scorer_id=self.scorer_id,
            evidence_spans=evidence,
            model_digest=self.model_digest,
            prompt_id=self.prompt_id,
        )
