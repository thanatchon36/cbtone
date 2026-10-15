"""Local replication of FOMC-RoBERTa (Shah, Paturi & Chava 2023), scorer id ``fomc-roberta-repl``.

The authors' checkpoint (``gtfintechlab/FOMC-RoBERTa``) is gated and access was never granted
(DECISIONS D21), so the reference scorer is rebuilt from the same recipe: RoBERTa-large
(Liu et al. 2019) fine-tuned on the train split of ``gtfintechlab/fomc_communication`` with a
stratified 20 % validation split, a learning rate of 1e-5 and early stopping on validation
macro-F1 (Shah et al. §4: grid over learning rate and batch size, up to 100 epochs, early stopping,
three seeds). Three seeds are trained. The scorer is the seed with the best *validation*
macro-F1; the test split is scored only after selection, and the three-seed mean is reported.

Licence (docs/sources/LICENSES.md): the FOMC data are CC-BY-NC-4.0. This is the local-only
comparison variant the licence table allows: weights go to ``data/models/fomc-roberta-repl/``
(git-ignored) and are never published. ``cbtone.scorers.finetuned.train`` still refuses FOMC
rows, so the released ``ft-xlmr`` weights cannot be trained on them.

Writes results/fomc_roberta_train_report.json, replaces the ``fomc_roberta`` rows of
results/scores/fomc_test.parquet and writes results/scores/silver_fomc_roberta.parquet
(English silver sentences only: RoBERTa-large reads English).
"""

from __future__ import annotations

import gc
import json
import random
import sys
import time
from pathlib import Path

import polars as pl
from _common import RESULTS, SCORES

from cbtone.eval.anchors import FOMC_REPO, FOMC_REVISION, load_fomc_anchor
from cbtone.scorers.finetuned import (
    LABELS,
    META_FILE,
    WEIGHTS_FILE,
    FineTunedScorer,
    _predict_probs,
    file_sha256,
    macro_f1,
    stratified_split,
)

SCORER_ID = "fomc-roberta-repl"
LABEL = "fomc_roberta"  # table label: the pre-registered FOMC-RoBERTa slot
BASE_MODEL = "FacebookAI/roberta-large"
MODEL_DIR = Path("data/models/fomc-roberta-repl")
SEEDS = (20261014, 20261015, 20261016)
VAL_FRAC = 0.2
LR = 1e-5
BATCH = 16
MICRO = 4  # micro-batch for gradient accumulation (BATCH / MICRO steps per update)
MAX_LENGTH = 256  # covers every FOMC sentence (longest: 253 tokens)
MAX_EPOCHS = 10
PATIENCE = 3
WARMUP_FRAC = 0.06
MAX_SKIP_FRAC = 0.01  # abort a seed if more than 1 % of its planned steps are non-finite


def free_memory() -> None:
    import torch

    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()


def base_revision() -> str:
    from huggingface_hub import HfApi

    return str(HfApi().model_info(BASE_MODEL).sha)


def train_seed(train: pl.DataFrame, seed: int, revision: str) -> dict[str, object]:
    """Fine-tune one seed; returns its report and the best-epoch state dict (on CPU)."""
    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    texts = train["sentence"].to_list()
    labels = train["label"].to_list()
    tr_idx, va_idx = stratified_split(labels, seed, frac=VAL_FRAC)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(BASE_MODEL, revision=revision)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        revision=revision,
        num_labels=len(LABELS),
        id2label=dict(enumerate(LABELS)),
        label2id={lab: i for i, lab in enumerate(LABELS)},
    ).to(dev)
    model.gradient_checkpointing_enable()  # activations recomputed in backward: less GPU memory
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    steps_per_epoch = -(-len(tr_idx) // BATCH)
    planned = steps_per_epoch * MAX_EPOCHS
    warm = max(1, int(WARMUP_FRAC * planned))
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt,
        lambda s: (s + 1) / warm if s < warm else max(0.0, (planned - s) / (planned - warm)),
    )
    gen = torch.Generator().manual_seed(seed)
    y = torch.tensor([LABELS.index(x) for x in labels])
    val_texts = [texts[i] for i in va_idx]
    val_gold = [LABELS.index(labels[i]) for i in va_idx]
    best_f1, best_epoch, best_state, since_best = -1.0, 0, None, 0
    skipped = 0
    epochs: list[dict[str, float]] = []
    t0 = time.perf_counter()
    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        perm = torch.randperm(len(tr_idx), generator=gen).tolist()
        losses = []
        for b in range(0, len(perm), BATCH):
            ids = [tr_idx[j] for j in perm[b : b + BATCH]]
            enc = tok(
                [texts[i] for i in ids],
                truncation=True,
                max_length=MAX_LENGTH,
                padding=True,
                return_tensors="pt",
            ).to(dev)
            # gradient accumulation over micro-batches: same effective batch, less GPU memory
            # (a full batch of 16 overflowed the M4's unified memory, D21)
            loss = torch.zeros((), device=dev)
            for m in range(0, len(ids), MICRO):
                part = {k: v[m : m + MICRO] for k, v in enc.items()}
                lp = model(**part, labels=y[ids[m : m + MICRO]].to(dev)).loss
                lp = lp * (len(ids[m : m + MICRO]) / len(ids))
                lp.backward()
                loss = loss + lp.detach()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            if not (torch.isfinite(loss) and torch.isfinite(norm)):
                # transient non-finite values on MPS (seen under memory pressure, not reproducible
                # in isolation): skip the update, as AMP's GradScaler does, and count it
                skipped += 1
                opt.zero_grad(set_to_none=True)
                sched.step()
                if skipped > MAX_SKIP_FRAC * planned:
                    raise FloatingPointError(f"seed {seed}: {skipped} non-finite steps")
                print(f"  skipped non-finite step (epoch {epoch}, batch {b // BATCH})", flush=True)
                continue
            opt.step()
            sched.step()
            opt.zero_grad(set_to_none=True)
            losses.append(float(loss.item()))
            if len(losses) % 20 == 0:
                print(f"  step {len(losses)} loss {sum(losses[-20:]) / 20:.4f}", flush=True)
        probs = _predict_probs(model, tok, val_texts, MAX_LENGTH, dev)
        f1 = macro_f1(val_gold, probs.argmax(dim=1).tolist())
        epochs.append(
            {
                "epoch": epoch,
                "train_loss": sum(losses) / len(losses),
                "val_macro_f1": f1,
                "seconds": time.perf_counter() - t0,
            }
        )
        print(f"seed {seed} epoch {epoch}: loss {epochs[-1]['train_loss']:.4f} val F1 {f1:.4f}")
        if f1 > best_f1:
            best_f1, best_epoch, since_best = f1, epoch, 0
            best_state = {k: v.detach().to("cpu").clone() for k, v in model.state_dict().items()}
        else:
            since_best += 1
            if since_best >= PATIENCE:
                break
    model.load_state_dict(best_state)
    return {
        "seed": seed,
        "device": dev,
        "n_train": len(tr_idx),
        "n_val": len(va_idx),
        "best_epoch": best_epoch,
        "skipped_steps": skipped,
        "val_macro_f1": best_f1,
        "epochs": epochs,
        "train_seconds": time.perf_counter() - t0,
        "_model": model,
        "_tok": tok,
    }


def save(run: dict[str, object], revision: str) -> str:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    run["_model"].save_pretrained(MODEL_DIR, safe_serialization=True)
    run["_tok"].save_pretrained(MODEL_DIR)
    meta = {
        "labels": list(LABELS),
        "max_length": MAX_LENGTH,
        "base_model": BASE_MODEL,
        "base_revision": revision,
        "scorer_id": SCORER_ID,
        "languages": ["en"],
        "training_data": f"{FOMC_REPO}@{FOMC_REVISION} train split (CC-BY-NC-4.0, local only)",
    }
    (MODEL_DIR / META_FILE).write_text(json.dumps(meta, indent=2))
    return file_sha256(MODEL_DIR / WEIGHTS_FILE)


def test_f1(model: object, tok: object, test: pl.DataFrame, dev: str) -> float:
    probs = _predict_probs(model, tok, test["sentence"].to_list(), MAX_LENGTH, dev)
    gold = [LABELS.index(x) for x in test["label"].to_list()]
    return macro_f1(gold, probs.argmax(dim=1).tolist())


def score_fomc(ft: FineTunedScorer, test: pl.DataFrame) -> None:
    """Replace the fomc_roberta rows of results/scores/fomc_test.parquet."""
    fomc = pl.read_parquet(SCORES / "fomc_test.parquet").filter(pl.col("config") != LABEL)
    scores = ft.score_sentences(test["sentence"].to_list(), "en")
    add = [
        {
            "unit": sid,
            "config": LABEL,
            "hawkish_p": s.hawkish_p,
            "dovish_p": s.dovish_p,
            "neutral_p": s.neutral_p,
            "index": s.index,
            "label": s.label,
            "prompt_id": None,
            "model_digest": s.model_digest,
            "gold": gold,
        }
        for (sid, gold), s in zip(
            test.select("sentence_id", "label").iter_rows(), scores, strict=True
        )
    ]
    pl.concat([fomc, pl.DataFrame(add)], how="diagonal_relaxed").write_parquet(
        SCORES / "fomc_test.parquet"
    )


def score_silver(ft: FineTunedScorer) -> None:
    labels = pl.read_parquet(SCORES / "silver_labels.parquet").filter(pl.col("lang") == "en")
    sents = (
        pl.concat(
            [
                pl.read_parquet("data/corpus/sentences.parquet"),
                pl.read_parquet("data/corpus/private/sentences.parquet"),
            ]
        )
        .filter(pl.col("text").is_not_null())
        .unique(["doc_id", "para_idx", "sent_idx"])
    )
    sil = labels.join(sents, on=["doc_id", "para_idx", "sent_idx"])
    scores = ft.score_sentences(sil["text"].to_list(), "en")
    pl.DataFrame(
        {
            "unit": sil["sample_id"],
            "config": [LABEL] * sil.height,
            "index": [s.index for s in scores],
            "label": [s.label for s in scores],
        }
    ).write_parquet(SCORES / "silver_fomc_roberta.parquet")


def main() -> None:
    anchor = load_fomc_anchor(splits=("train", "test"))
    train = anchor.filter(pl.col("split") == "train")
    test = anchor.filter(pl.col("split") == "test")
    if "--score-only" in sys.argv:
        ft = FineTunedScorer.load(MODEL_DIR)
        score_fomc(ft, test)
        score_silver(ft)
        return
    revision = base_revision()
    runs = []
    best = None
    for seed in SEEDS:
        run = train_seed(train, seed, revision)
        # test F1 of every seed, for the three-seed mean only; selection uses validation F1
        run["test_macro_f1"] = test_f1(run["_model"], run["_tok"], test, run["device"])
        if best is None or run["val_macro_f1"] > best["val_macro_f1"]:
            if best is not None:
                best["_model"] = best["_tok"] = None
            best = run
        else:
            run["_model"] = run["_tok"] = None
        runs.append(run)
        free_memory()
    digest = save(best, revision)
    del best["_model"], best["_tok"]
    free_memory()
    ft = FineTunedScorer.load(MODEL_DIR)
    score_fomc(ft, test)
    score_silver(ft)
    seed_f1 = [r["test_macro_f1"] for r in runs]
    mean = sum(seed_f1) / len(seed_f1)
    sd = (sum((f - mean) ** 2 for f in seed_f1) / (len(seed_f1) - 1)) ** 0.5
    report = {
        "scorer_id": SCORER_ID,
        "base_model": BASE_MODEL,
        "base_revision": revision,
        "training_data": f"{FOMC_REPO}@{FOMC_REVISION} train split",
        "lr": LR,
        "batch_size": BATCH,
        "micro_batch": MICRO,
        "gradient_checkpointing": True,
        "max_length": MAX_LENGTH,
        "max_epochs": MAX_EPOCHS,
        "patience": PATIENCE,
        "warmup_frac": WARMUP_FRAC,
        "val_frac": VAL_FRAC,
        "selected_seed": best["seed"],
        "model_digest": digest,
        "test_macro_f1_seed_mean": mean,
        "test_macro_f1_seed_sd": sd,
        "runs": [{k: v for k, v in r.items() if not k.startswith("_")} for r in runs],
    }
    (RESULTS / "fomc_roberta_train_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "runs"}, indent=2))
    print("seed test F1:", [round(f, 4) for f in seed_f1])


if __name__ == "__main__":
    main()
