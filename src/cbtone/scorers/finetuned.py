"""Fine-tuned multilingual scorer (``ft-xlmr``): XLM-RoBERTa-base on LLM silver labels.

Base model: Conneau et al. (2020), "Unsupervised cross-lingual representation learning at scale"
(XLM-R), fine-tuned as a sequence classifier in the Devlin et al. (2019) fashion with AdamW
(Loshchilov & Hutter 2019). The three-way hawkish / dovish / neutral task follows Shah, Paturi &
Chava (2023, ``shah2023trillion``) and RESEARCH_QUESTIONS.md §0.5.

Licensing rule (docs/sources/LICENSES.md): ``gtfintechlab/fomc_communication`` is CC-BY-NC-4.0
and is evaluation-only, so :func:`train` refuses any row whose ``source`` mentions it.

Heavy dependencies (torch, transformers) are imported lazily; ``import cbtone`` works without the
``[transformers]`` extra. LoRA (peft) is not used: this is a full fine-tune with the embedding
matrix frozen by default (it is 192 M of XLM-R's 278 M parameters and dominates optimiser time).
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import polars as pl
from pydantic import BaseModel, Field

from cbtone.schema import Document, Language
from cbtone.scorers.base import DOC_CHAR_CAP, Scorer, ToneScore

SCORER_ID = "ft-xlmr"
BASE_MODEL = "FacebookAI/xlm-roberta-base"
LABELS: tuple[str, ...] = ("hawkish", "dovish", "neutral")
FORBIDDEN_SOURCE = "fomc_communication"
DEFAULT_SEED = 20261014
WEIGHTS_FILE = "model.safetensors"
META_FILE = "ft_meta.json"
REPORT_FILE = "train_report.json"
_LANGS = frozenset({"en", "id", "ms", "th", "zh"})
_BATCH = 16  # inference batch size
_EVIDENCE = 3


class LicenseError(ValueError):
    """Raised when the training data contains a source that must never be trained on."""


class TrainReport(BaseModel):
    """What :func:`train` did. ``loss_log`` rows: ``(step, mean loss since last log, seconds)``."""

    scorer_id: str = SCORER_ID
    base_model: str
    seed: int
    device: str
    n_train: int
    n_val: int
    val_macro_f1: float
    steps: int
    planned_steps: int
    epochs_completed: float
    wall_seconds: float
    train_seconds: float
    seconds_per_step: float
    stopped_on_time_budget: bool
    max_minutes: float
    batch_size: int
    max_length: int
    lr: float
    freeze_embeddings: bool
    peft_used: bool = False
    model_digest: str
    loss_log: list[tuple[int, float, float]] = Field(default_factory=list)


def _pick_device(device: str | None = None) -> str:
    import torch

    if device:
        return device
    return "mps" if torch.backends.mps.is_available() else "cpu"


def file_sha256(path: Path) -> str:
    """Streaming sha256 of a file (the ``model_digest`` of the saved weights)."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_frame(df: pl.DataFrame) -> pl.DataFrame:
    missing = {"text", "lang", "label"} - set(df.columns)
    if missing:
        raise ValueError(f"training frame is missing columns: {sorted(missing)}")
    if "source" in df.columns:
        bad = df.filter(pl.col("source").cast(pl.Utf8).str.contains(FORBIDDEN_SOURCE, literal=True))
        if bad.height:
            raise LicenseError(
                f"{bad.height} row(s) come from {FORBIDDEN_SOURCE!r} (CC-BY-NC-4.0): "
                "evaluation only, never for training (docs/sources/LICENSES.md)"
            )
    if any(df[c].null_count() for c in ("text", "lang", "label")):
        raise ValueError("text, lang and label must not contain nulls")
    labels = set(df["label"].unique().to_list())
    if not labels <= set(LABELS):
        raise ValueError(f"unknown labels {sorted(labels - set(LABELS))}; expected {LABELS}")
    langs = set(df["lang"].unique().to_list())
    if not langs <= _LANGS:
        raise ValueError(f"unsupported languages {sorted(langs - _LANGS)}")
    return df


def stratified_split(
    labels: Sequence[str], seed: int, frac: float = 0.1
) -> tuple[list[int], list[int]]:
    """Seeded stratified split: ``max(1, round(frac * n))`` validation rows per class (n >= 2)."""
    rng = random.Random(seed)
    train_idx: list[int] = []
    val_idx: list[int] = []
    for lab in LABELS:
        idx = [i for i, x in enumerate(labels) if x == lab]
        rng.shuffle(idx)
        k = max(1, round(frac * len(idx))) if len(idx) >= 2 else 0
        val_idx.extend(idx[:k])
        train_idx.extend(idx[k:])
    return sorted(train_idx), sorted(val_idx)


def macro_f1(gold: Sequence[int], pred: Sequence[int]) -> float:
    """Macro-averaged F1 over the classes present in ``gold`` or ``pred`` (sklearn's default)."""
    scores = []
    for c in sorted(set(gold) | set(pred)):
        tp = sum(g == c and p == c for g, p in zip(gold, pred, strict=True))
        fp = sum(g != c and p == c for g, p in zip(gold, pred, strict=True))
        fn = sum(g == c and p != c for g, p in zip(gold, pred, strict=True))
        scores.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def _predict_probs(model: Any, tok: Any, texts: Sequence[str], max_length: int, device: str) -> Any:
    """Softmax probabilities (n, 3) in ``LABELS`` order, batched, no grad, eval mode."""
    import torch

    order = [int(model.config.label2id[lab]) for lab in LABELS]
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(texts), _BATCH):
            enc = tok(
                list(texts[i : i + _BATCH]),
                truncation=True,
                max_length=max_length,
                padding=True,
                return_tensors="pt",
            ).to(device)
            logits = model(**enc).logits.float()
            out.append(torch.softmax(logits, dim=-1)[:, order].cpu())
    return torch.cat(out) if out else torch.zeros((0, len(LABELS)))


def train(
    df: pl.DataFrame,
    out_dir: Path | str,
    seed: int = DEFAULT_SEED,
    max_minutes: float = 30,
    *,
    base_model: str = BASE_MODEL,
    epochs: int = 3,
    batch_size: int = 16,
    max_length: int = 128,
    lr: float = 2e-5,
    max_steps: int | None = None,
    freeze_embeddings: bool = True,
    device: str | None = None,
    log_every: int = 10,
) -> TrainReport:
    """Fine-tune ``base_model`` on ``df`` (columns ``text, lang, label``; optional ``source``).

    Full fine-tune of XLM-R (Conneau et al. 2020) with AdamW (Loshchilov & Hutter 2019), linear
    warm-up (6 %) and decay, gradient clipping at 1.0. Deterministic given the seed on a fixed
    device. A stratified 10 % validation split is held out; macro-F1 on it goes in the report.
    Stops early (after finishing the current step) once ``max_minutes`` of wall time, counted
    from the call, are used. Raises :class:`LicenseError` if any ``source`` contains
    ``fomc_communication``. Saves weights, tokenizer, ``ft_meta.json`` and ``train_report.json``
    into ``out_dir`` (conventionally ``data/models/ft-xlmr/``, git-ignored).
    """
    t0 = time.perf_counter()
    df = _check_frame(df)
    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    out = Path(out_dir)
    texts: list[str] = df["text"].to_list()
    labels: list[str] = df["label"].to_list()
    tr_idx, va_idx = stratified_split(labels, seed)
    if not va_idx or not tr_idx:
        raise ValueError("need at least 2 rows in some class to hold out a validation set")

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    dev = _pick_device(device)
    tok = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        num_labels=len(LABELS),
        id2label=dict(enumerate(LABELS)),
        label2id={lab: i for i, lab in enumerate(LABELS)},
    )
    if freeze_embeddings:
        for p in model.base_model.embeddings.parameters():
            p.requires_grad = False
    model.to(dev)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=0.01)

    steps_per_epoch = -(-len(tr_idx) // batch_size)
    planned = steps_per_epoch * epochs
    if max_steps is not None:
        planned = min(planned, max_steps)
    warm = max(1, int(0.06 * planned))

    def lr_at(step: int) -> float:
        if step < warm:
            return (step + 1) / warm
        return max(0.0, (planned - step) / max(1, planned - warm))

    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_at)
    gen = torch.Generator().manual_seed(seed)
    y = torch.tensor([LABELS.index(x) for x in labels])
    budget = max_minutes * 60.0
    step = 0
    stopped = False
    loss_log: list[tuple[int, float, float]] = []
    running: list[float] = []
    t_loop = time.perf_counter()
    model.train()
    for _ in range(epochs):
        perm = torch.randperm(len(tr_idx), generator=gen).tolist()
        for b in range(0, len(perm), batch_size):
            ids = [tr_idx[j] for j in perm[b : b + batch_size]]
            enc = tok(
                [texts[i] for i in ids],
                truncation=True,
                max_length=max_length,
                padding=True,
                return_tensors="pt",
            ).to(dev)
            loss = model(**enc, labels=y[ids].to(dev)).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
            sched.step()
            opt.zero_grad(set_to_none=True)
            step += 1
            running.append(float(loss.item()))
            if step % log_every == 0 or step == planned:
                loss_log.append((step, sum(running) / len(running), time.perf_counter() - t_loop))
                running = []
            if step >= planned:
                break
            if time.perf_counter() - t0 >= budget:
                stopped = True
                break
        if stopped or step >= planned:
            break
    if running:
        loss_log.append((step, sum(running) / len(running), time.perf_counter() - t_loop))
    train_seconds = time.perf_counter() - t_loop

    probs = _predict_probs(model, tok, [texts[i] for i in va_idx], max_length, dev)
    pred = probs.argmax(dim=1).tolist()
    gold = [LABELS.index(labels[i]) for i in va_idx]
    f1 = macro_f1(gold, pred)

    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out, safe_serialization=True)
    tok.save_pretrained(out)
    digest = file_sha256(out / WEIGHTS_FILE)
    (out / META_FILE).write_text(
        json.dumps({"labels": list(LABELS), "max_length": max_length, "base_model": base_model})
    )
    report = TrainReport(
        base_model=base_model,
        seed=seed,
        device=dev,
        n_train=len(tr_idx),
        n_val=len(va_idx),
        val_macro_f1=f1,
        steps=step,
        planned_steps=planned,
        epochs_completed=step / steps_per_epoch,
        wall_seconds=time.perf_counter() - t0,
        train_seconds=train_seconds,
        seconds_per_step=train_seconds / max(1, step),
        stopped_on_time_budget=stopped,
        max_minutes=max_minutes,
        batch_size=batch_size,
        max_length=max_length,
        lr=lr,
        freeze_embeddings=freeze_embeddings,
        model_digest=digest,
        loss_log=loss_log,
    )
    (out / REPORT_FILE).write_text(report.model_dump_json(indent=2))
    return report


class FineTunedScorer(Scorer):
    """Scorer wrapping a model saved by :func:`train` (XLM-R, Conneau et al. 2020).

    ``score_text`` scores one unit (truncated to the trained ``max_length``). Document mode
    follows the transformer scorer: split ``policy_text`` (RESEARCH_QUESTIONS.md §0.5) into
    sentences, score each, average the probabilities; evidence is the 3 most extreme sentences.
    """

    scorer_id = SCORER_ID
    languages = _LANGS

    def __init__(
        self,
        model: Any,
        tokenizer: Any,
        digest: str,
        max_length: int,
        device: str,
        *,
        scorer_id: str = SCORER_ID,
        languages: frozenset[str] = _LANGS,
    ) -> None:
        self._model = model
        self._tok = tokenizer
        self.model_digest = digest
        self.max_length = max_length
        self.device = device
        self.scorer_id = scorer_id
        self.languages = languages

    @classmethod
    def load(cls, out_dir: Path | str, device: str | None = None) -> FineTunedScorer:
        """Load a model saved by :func:`train`; ``model_digest`` = sha256 of its weights file.

        ``ft_meta.json`` may set ``scorer_id`` and ``languages`` (e.g. the local FOMC-RoBERTa
        replication, ``experiments/train_fomc_roberta.py``); the defaults are ``ft-xlmr``'s.
        """
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        out = Path(out_dir)
        weights = out / WEIGHTS_FILE
        if not weights.exists():
            raise FileNotFoundError(f"no {WEIGHTS_FILE} in {out}; run train() first")
        meta = json.loads((out / META_FILE).read_text())
        dev = _pick_device(device)
        model = AutoModelForSequenceClassification.from_pretrained(out).to(dev)
        tok = AutoTokenizer.from_pretrained(out)
        return cls(
            model,
            tok,
            file_sha256(weights),
            int(meta["max_length"]),
            dev,
            scorer_id=str(meta.get("scorer_id", SCORER_ID)),
            languages=frozenset(meta.get("languages", _LANGS)),
        )

    def _scores(self, texts: Sequence[str]) -> list[ToneScore]:
        probs = _predict_probs(self._model, self._tok, texts, self.max_length, self.device)
        return [
            ToneScore.from_probs(
                float(p[0]),
                float(p[1]),
                float(p[2]),
                scorer_id=self.scorer_id,
                model_digest=self.model_digest,
            )
            for p in probs
        ]

    def score_text(self, text: str, lang: Language = "en") -> ToneScore:
        return self._scores([text])[0]

    def score_sentences(self, sentences: Sequence[str], lang: Language = "en") -> list[ToneScore]:
        return self._scores(list(sentences))

    def score_document(self, doc: Document, cap: int = DOC_CHAR_CAP) -> ToneScore:
        """Mean of sentence probabilities over ``policy_text(doc)`` (Shah et al. 2023 style)."""
        from cbtone.text.paragraphs import policy_text
        from cbtone.text.split import split_sentences

        sents = split_sentences(policy_text(doc, cap=cap), doc.language)
        if not sents:
            return ToneScore.from_probs(
                0, 0, 1, scorer_id=self.scorer_id, model_digest=self.model_digest
            )
        scores = self._scores(sents)
        n = len(scores)
        extreme = sorted(range(n), key=lambda i: -abs(scores[i].index))[:_EVIDENCE]
        return ToneScore.from_probs(
            sum(s.hawkish_p for s in scores) / n,
            sum(s.dovish_p for s in scores) / n,
            sum(s.neutral_p for s in scores) / n,
            scorer_id=self.scorer_id,
            evidence_spans=[sents[i] for i in extreme],
            model_digest=self.model_digest,
        )
