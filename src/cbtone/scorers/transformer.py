"""Encoder-classifier scorer: FOMC-RoBERTa (Shah, Paturi & Chava 2023), id ``fomc-roberta``.

``TransformerScorer`` wraps a sequence-classification checkpoint that outputs hawkish / dovish /
neutral logits. Sentence probabilities are the softmax of the logits mapped onto the three stance
classes. A longer text is split into sentences (``cbtone.text.split.split_sentences``), each
sentence is scored, and the document score is the mean of the sentence probabilities (the evidence
spans are the three sentences with the largest ``|index|``). Heavy dependencies (torch,
transformers, huggingface_hub) are imported lazily, so ``import cbtone`` works without the
``[transformers]`` extra.

Label mappings (verified 2026-10-14)
------------------------------------
``fomc-roberta`` = ``gtfintechlab/FOMC-RoBERTa`` (RoBERTa-large fine-tuned on the "Trillion Dollar
Words" FOMC sentences; CC-BY-NC-4.0; Shah, Paturi & Chava 2023, ACL):

* ``LABEL_0`` dovish, ``LABEL_1`` hawkish, ``LABEL_2`` neutral.
* Source: the authors' code repository README ("Label Interpretation" section,
  github.com/gtfintechlab/fomc-hawkish-dovish) and the identical statement on the dataset card
  ``gtfintechlab/fomc_communication``. The model repository itself is gated (manual approval), so
  its own ``README.md`` and ``config.json`` (``id2label``) could **not** be fetched anonymously.
  The model's public API metadata (sha, tags ``hawkish-dovish-classification``) was read. Both
  sources above refer to the model by that name and use the default ``LABEL_n`` ids.
  ``_check_labels`` fails loudly at load time if the downloaded ``config.json`` has an ``id2label``
  of the wrong size or with named (non-``LABEL_n``) classes that contradict the map, so a wrong
  mapping cannot be applied silently once the user has access.
* ``model_digest`` is pinned to the Hugging Face commit sha
  ``aa3bc4281fb1fe73c8872e09ad5c64b898f90d83`` (``HfApi().model_info(repo).sha``, last modified
  2023-09-12). ``from_pretrained`` is called with ``revision=<sha>``.
* Access was never granted during the study. The paper uses a local replication of the same recipe
  (``experiments/train_fomc_roberta.py``, DECISIONS D21), saved in ``FineTunedScorer`` format with
  scorer id ``fomc-roberta-repl``. This class remains for users who have access to the original.

``cb-roberta`` = ``Moritz-Pfeifer/CentralBankRoBERTa-sentiment-classifier`` is **not registered**.
Its ``config.json`` has ``id2label = {0: "negative", 1: "positive"}`` (a binary head, no neutral
class) and its model card (Pfeifer & Marohl 2023, J. Finance and Data Science) describes it as a
sentiment classifier that detects whether a sentence is "positive or negative for either households,
firms, the financial sector or the government". That is sentiment about the *economy* for an agent,
not a hawkish/dovish stance on future policy. For a central bank, tightening is "negative for
households and firms" while it is also the hawkish act, so positive-to-hawkish would often have the
wrong sign, and nothing on the card supports that reading. ``get_spec("cb-roberta")`` raises with
this explanation (see ``UNSUITABLE``).

Licence: FOMC-RoBERTa is CC-BY-NC-4.0, used for evaluation and scoring at run time only, never
redistributed (docs/sources/LICENSES.md).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from cbtone.schema import Language
from cbtone.scorers.base import ScoreCache, Scorer, ToneScore
from cbtone.text.split import split_sentences

BATCH_SIZE = 16
MAX_LENGTH = 256
N_EVIDENCE = 3
_GENERIC_LABEL = re.compile(r"^LABEL_(\d+)$")


@dataclass(frozen=True)
class ModelSpec:
    """A registered checkpoint: repo, pinned commit sha and the logit index of each stance."""

    scorer_id: str
    repo: str
    revision: str  # Hugging Face commit sha; becomes ToneScore.model_digest
    id2stance: dict[int, str]  # logit index -> "hawkish" | "dovish" | "neutral"


MODEL_SPECS: dict[str, ModelSpec] = {
    "fomc-roberta": ModelSpec(
        scorer_id="fomc-roberta",
        repo="gtfintechlab/FOMC-RoBERTa",
        revision="aa3bc4281fb1fe73c8872e09ad5c64b898f90d83",
        id2stance={0: "dovish", 1: "hawkish", 2: "neutral"},
    ),
}

UNSUITABLE: dict[str, str] = {
    "cb-roberta": (
        "Moritz-Pfeifer/CentralBankRoBERTa-sentiment-classifier is a binary positive/negative "
        "sentiment model (id2label {0: negative, 1: positive}; positive or negative 'for "
        "households, firms, the financial sector or the government', Pfeifer & Marohl 2023), not a "
        "hawkish/dovish stance model, and has no neutral class. Its card does not support mapping "
        "positive to hawkish and negative to dovish, so it is not registered."
    ),
}


def get_spec(name: str) -> ModelSpec:
    """Look up a registered checkpoint (Shah, Paturi & Chava 2023 for ``fomc-roberta``)."""
    if name in MODEL_SPECS:
        return MODEL_SPECS[name]
    if name in UNSUITABLE:
        raise ValueError(f"{name!r} is not registered: {UNSUITABLE[name]}")
    raise ValueError(f"unknown transformer scorer {name!r}; registered: {sorted(MODEL_SPECS)}")


def resolve_revision(repo: str) -> str:
    """Current Hugging Face commit sha of ``repo`` (network call; used to (re)pin a spec)."""
    from huggingface_hub import HfApi

    sha = HfApi().model_info(repo).sha
    if sha is None:
        raise RuntimeError(f"Hugging Face returned no sha for {repo}")
    return str(sha)


def _check_labels(spec: ModelSpec, id2label: dict[Any, Any]) -> None:
    """Fail loudly if the downloaded config disagrees with the registered label map."""
    labels = {int(k): str(v) for k, v in id2label.items()}
    if sorted(labels) != sorted(spec.id2stance):
        raise ValueError(f"{spec.repo}: id2label has {len(labels)} classes {labels}, expected 3")
    for idx, name in labels.items():
        if _GENERIC_LABEL.match(name):
            continue  # generic LABEL_n ids: the authors' README map applies
        low = name.lower()
        if low in spec.id2stance.values() and low != spec.id2stance[idx]:
            raise ValueError(
                f"{spec.repo}: config id2label[{idx}]={name!r} contradicts the registered "
                f"map {spec.id2stance}"
            )


class TransformerScorer(Scorer):
    """Hawkish/dovish/neutral scorer around a RoBERTa sequence classifier (Shah et al. 2023).

    ``model`` and ``tokenizer`` may be injected (tests, or reuse of a loaded model); otherwise they
    are loaded lazily on first use from ``spec.repo`` at ``spec.revision``.
    """

    languages = frozenset({"en"})

    def __init__(
        self,
        name: str = "fomc-roberta",
        *,
        cache: ScoreCache | None = None,
        device: str | None = None,
        batch_size: int = BATCH_SIZE,
        max_length: int = MAX_LENGTH,
        model: Any = None,
        tokenizer: Any = None,
    ) -> None:
        self.spec = get_spec(name)
        self.scorer_id = self.spec.scorer_id
        self.model_digest = self.spec.revision
        self.cache = cache
        self.batch_size = batch_size
        self.max_length = max_length
        self._device = device
        self._model = model
        self._tokenizer = tokenizer
        self._variant = f"max_length={max_length}"

    # ---- model plumbing -------------------------------------------------------------------

    @property
    def device(self) -> str:
        """``mps`` when available, else ``cpu`` (unless set explicitly)."""
        if self._device is None:
            import torch

            self._device = "mps" if torch.backends.mps.is_available() else "cpu"
        return self._device

    def _load(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        try:
            tokenizer = AutoTokenizer.from_pretrained(self.spec.repo, revision=self.spec.revision)
            model = AutoModelForSequenceClassification.from_pretrained(
                self.spec.repo, revision=self.spec.revision
            )
        except OSError as exc:  # gated / offline / missing repo
            raise RuntimeError(
                f"cannot load {self.spec.repo}@{self.spec.revision[:8]}: {exc}. If the repo is "
                "gated, request access on huggingface.co and run `hf auth login`."
            ) from exc
        _check_labels(self.spec, dict(model.config.id2label))
        model.to(self.device)
        model.eval()
        self._tokenizer, self._model = tokenizer, model

    def _probs(self, texts: Sequence[str]) -> list[tuple[float, float, float]]:
        """(hawkish, dovish, neutral) softmax probabilities per text, in input order."""
        import torch

        self._load()
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))  # less padding
        out: list[tuple[float, float, float]] = [(0.0, 0.0, 1.0)] * len(texts)
        stance_col = {s: i for i, s in self.spec.id2stance.items()}
        for lo in range(0, len(order), self.batch_size):
            idx = order[lo : lo + self.batch_size]
            enc = self._tokenizer(
                [texts[i] for i in idx],
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            enc = {k: v.to(self.device) for k, v in enc.items()}
            with torch.inference_mode():
                logits = self._model(**enc).logits
            probs = torch.softmax(logits.float(), dim=-1).cpu().tolist()
            for i, row in zip(idx, probs, strict=True):
                out[i] = (
                    row[stance_col["hawkish"]],
                    row[stance_col["dovish"]],
                    row[stance_col["neutral"]],
                )
        return out

    # ---- scoring --------------------------------------------------------------------------

    def _require_english(self, lang: str) -> None:
        if not self.supports(lang):
            raise ValueError(f"{self.scorer_id} reads English only, not {lang!r}; check supports()")

    def _score_units(self, units: Sequence[str]) -> list[ToneScore]:
        """Score sentence-like units (no further splitting), through the cache, deduplicated."""
        scores: dict[str, ToneScore] = {}
        todo: list[str] = []
        for u in dict.fromkeys(units):
            hit = self._cache_get(u)
            if hit is not None:
                scores[u] = hit
            else:
                todo.append(u)
        for u, (h, d, n) in zip(todo, self._probs(todo) if todo else [], strict=True):
            score = ToneScore.from_probs(
                h, d, n, scorer_id=self.scorer_id, model_digest=self.model_digest
            )
            scores[u] = score
            self._cache_put(u, score)
        return [scores[u] for u in units]

    def _cache_key(self, unit: str) -> str:
        return ScoreCache.key(
            self.scorer_id, unit, model_digest=self.model_digest, variant=self._variant
        )

    def _cache_get(self, unit: str) -> ToneScore | None:
        return self.cache.get(self._cache_key(unit)) if self.cache is not None else None

    def _cache_put(self, unit: str, score: ToneScore) -> None:
        if self.cache is not None:
            self.cache.put(self._cache_key(unit), score)

    def score_sentences(self, sentences: Sequence[str], lang: Language = "en") -> list[ToneScore]:
        """Score each given sentence as is (batched); no evidence spans."""
        self._require_english(lang)
        return self._score_units(sentences)

    def score_text(self, text: str, lang: Language = "en") -> ToneScore:
        """Split ``text`` into sentences, score each, return the mean probabilities.

        Aggregation by mean sentence probability follows the document measure of Shah, Paturi &
        Chava (2023); ``evidence_spans`` are the 3 sentences with the largest ``|index|``.
        """
        self._require_english(lang)
        sentences = split_sentences(text, "en")
        if not sentences:
            return ToneScore.from_probs(
                0.0, 0.0, 1.0, scorer_id=self.scorer_id, model_digest=self.model_digest
            )
        scores = self._score_units(sentences)
        n = len(scores)
        ranked = sorted(range(n), key=lambda i: (-abs(scores[i].index), i))
        evidence = [sentences[i] for i in ranked[:N_EVIDENCE]]
        return ToneScore.from_probs(
            sum(s.hawkish_p for s in scores) / n,
            sum(s.dovish_p for s in scores) / n,
            sum(s.neutral_p for s in scores) / n,
            scorer_id=self.scorer_id,
            evidence_spans=evidence,
            model_digest=self.model_digest,
        )
