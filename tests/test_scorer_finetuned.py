"""FineTunedScorer: tiny random-init XLM-R + whitespace tokenizer, fully offline."""

# ruff: noqa: SIM905
from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("tokenizers")

from cbtone.schema import Document, Section
from cbtone.scorers.base import Scorer
from cbtone.scorers.finetuned import (
    LABELS,
    FineTunedScorer,
    LicenseError,
    TrainReport,
    file_sha256,
    macro_f1,
    stratified_split,
    train,
)

WORDS = {
    "hawkish": "raise tighten inflation hike higher".split(),
    "dovish": "cut ease weak lower slowdown".split(),
    "neutral": "hold steady meeting unchanged data".split(),
}


@pytest.fixture(scope="module")
def tiny_base(tmp_path_factory: pytest.TempPathFactory) -> str:
    """A saved random-init 2-layer XLM-R with a word-level tokenizer; no network."""
    from tokenizers import Tokenizer, models, pre_tokenizers
    from transformers import (
        PreTrainedTokenizerFast,
        XLMRobertaConfig,
        XLMRobertaModel,
    )

    specials = ["<s>", "<pad>", "</s>", "<unk>"]  # pad id 1, like XLM-R
    words = sorted({w for ws in WORDS.values() for w in ws} | {"the", "committee", "will"})
    vocab = {w: i for i, w in enumerate(specials + words)}
    tk = Tokenizer(models.WordLevel(vocab, unk_token="<unk>"))
    tk.pre_tokenizer = pre_tokenizers.Whitespace()
    fast = PreTrainedTokenizerFast(
        tokenizer_object=tk, bos_token="<s>", eos_token="</s>", pad_token="<pad>", unk_token="<unk>"
    )
    cfg = XLMRobertaConfig(
        vocab_size=len(vocab), hidden_size=32, num_hidden_layers=2, num_attention_heads=2,
        intermediate_size=64, max_position_embeddings=64, pad_token_id=1, type_vocab_size=1,
    )  # fmt: skip
    path = tmp_path_factory.mktemp("tiny-base")
    XLMRobertaModel(cfg).save_pretrained(path)  # encoder only, like the real base
    fast.save_pretrained(path)
    return str(path)


def synth(n: int = 20, source: str | None = None) -> pl.DataFrame:
    rows = []
    for i in range(n):
        lab = LABELS[i % 3]
        w = WORDS[lab]
        rows.append(
            {
                "text": f"the committee will {w[i % 5]} {w[(i + 1) % 5]} {w[(i + 2) % 5]}",
                "lang": "en",
                "label": lab,
                "source": source or "silver_llm",
            }
        )
    return pl.DataFrame(rows)


def kw(base: str) -> dict:
    return {"base_model": base, "device": "cpu", "max_length": 16, "batch_size": 4, "lr": 5e-3}


def make_doc(text: str, sections: list[str] | None = None) -> Document:
    return Document(
        bank="fed", date=date(2020, 1, 1), doc_type="statement", language="en", title="t",
        text=text, sections=[Section(text=s) for s in sections or []],
        url="https://x", sha256="0" * 64, fetched_at=datetime(2020, 1, 1, tzinfo=UTC),
    )  # fmt: skip


@pytest.fixture(scope="module")
def trained(tiny_base: str, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, TrainReport]:
    out = tmp_path_factory.mktemp("ft") / "ft-xlmr"
    rep = train(synth(), out, seed=1, epochs=4, log_every=2, **kw(tiny_base))
    return out, rep


def test_train_report_and_files(trained: tuple[Path, TrainReport]) -> None:
    out, rep = trained
    assert rep.n_train + rep.n_val == 20
    assert rep.n_val == 3  # classes of 7/7/6 rows: max(1, round(0.1 * n)) = 1 each
    assert 0.0 <= rep.val_macro_f1 <= 1.0
    assert rep.steps == rep.planned_steps > 0
    assert not rep.stopped_on_time_budget
    assert not rep.peft_used
    assert rep.wall_seconds >= rep.train_seconds > 0
    assert rep.loss_log and rep.loss_log[-1][0] == rep.steps
    assert (out / "model.safetensors").exists()
    assert rep.model_digest == hashlib.sha256((out / "model.safetensors").read_bytes()).hexdigest()
    assert TrainReport.model_validate_json((out / "train_report.json").read_text()) == rep
    assert json.loads((out / "ft_meta.json").read_text())["labels"] == list(LABELS)


def test_stratified_split_is_seeded_and_stratified() -> None:
    labels = [LABELS[i % 3] for i in range(30)]
    a = stratified_split(labels, 7)
    assert a == stratified_split(labels, 7)
    assert a != stratified_split(labels, 8)
    tr, va = a
    assert sorted(tr + va) == list(range(30)) and len(va) == 3
    assert {labels[i] for i in va} == set(LABELS)
    # singleton classes stay in train
    tr1, va1 = stratified_split(["hawkish", "dovish", "dovish"], 0)
    assert 0 in tr1 and len(va1) == 1


def test_load_score_text_and_digest(trained: tuple[Path, TrainReport]) -> None:
    out, rep = trained
    sc = FineTunedScorer.load(out, device="cpu")
    assert isinstance(sc, Scorer)
    assert sc.scorer_id == "ft-xlmr"
    assert sc.model_digest == rep.model_digest == file_sha256(out / "model.safetensors")
    assert sc.supports("th") and sc.supports("zh") and not sc.supports("fr")
    s = sc.score_text("the committee will raise inflation")
    assert s.scorer_id == "ft-xlmr" and s.model_digest == rep.model_digest
    assert abs(s.hawkish_p + s.dovish_p + s.neutral_p - 1) < 1e-6
    assert s == sc.score_text("the committee will raise inflation")  # deterministic
    batch = sc.score_sentences(["the committee will cut", "the committee will hold"])
    assert len(batch) == 2
    assert batch[0].index == pytest.approx(sc.score_text("the committee will cut").index, abs=1e-5)


def test_training_is_deterministic(tiny_base: str, tmp_path: Path) -> None:
    a = train(synth(), tmp_path / "a", seed=3, epochs=2, **kw(tiny_base))
    b = train(synth(), tmp_path / "b", seed=3, epochs=2, **kw(tiny_base))
    assert a.model_digest == b.model_digest
    assert [x[:2] for x in a.loss_log] == [x[:2] for x in b.loss_log]


def test_document_mode_is_mean_over_policy_sentences(trained: tuple[Path, TrainReport]) -> None:
    sc = FineTunedScorer.load(trained[0], device="cpu")
    paras = [
        "The Committee decided to raise the policy rate. It will cut nothing.",
        "Inflation is higher. Growth is weak.",
    ]
    doc = make_doc("\n\n".join(paras), paras)
    got = sc.score_document(doc)
    from cbtone.text.paragraphs import policy_text
    from cbtone.text.split import split_sentences

    sents = split_sentences(policy_text(doc), "en")
    assert len(sents) == 4
    each = sc.score_sentences(sents)
    assert got.hawkish_p == pytest.approx(sum(s.hawkish_p for s in each) / 4, abs=1e-6)
    assert got.dovish_p == pytest.approx(sum(s.dovish_p for s in each) / 4, abs=1e-6)
    assert len(got.evidence_spans) == 3 and set(got.evidence_spans) <= set(sents)
    top = max(each, key=lambda s: abs(s.index))
    assert got.evidence_spans[0] == sents[each.index(top)]


def test_empty_document_is_neutral(trained: tuple[Path, TrainReport]) -> None:
    sc = FineTunedScorer.load(trained[0], device="cpu")
    s = sc.score_document(make_doc(" "))
    assert s.neutral_p == 1.0 and s.evidence_spans == []


def test_refuses_fomc_source(tiny_base: str, tmp_path: Path) -> None:
    df = synth(20)
    df = df.with_columns(
        pl.when(pl.int_range(pl.len()) == 5)
        .then(pl.lit("gtfintechlab/fomc_communication:train"))
        .otherwise(pl.col("source"))
        .alias("source")
    )
    with pytest.raises(LicenseError, match="fomc_communication"):
        train(df, tmp_path / "x", **kw(tiny_base))
    assert not (tmp_path / "x").exists()
    with pytest.raises(LicenseError):
        train(synth(20, source="fomc_communication"), tmp_path / "y", **kw(tiny_base))


def test_input_validation(tiny_base: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing columns"):
        train(synth().drop("label"), tmp_path, **kw(tiny_base))
    with pytest.raises(ValueError, match="unknown labels"):
        train(synth().with_columns(label=pl.lit("bullish")), tmp_path, **kw(tiny_base))
    with pytest.raises(ValueError, match="unsupported languages"):
        train(synth().with_columns(lang=pl.lit("fr")), tmp_path, **kw(tiny_base))
    with pytest.raises(ValueError, match="nulls"):
        train(synth().with_columns(text=pl.lit(None, dtype=pl.Utf8)), tmp_path, **kw(tiny_base))
    one_each = pl.DataFrame({"text": list("abc"), "lang": ["en"] * 3, "label": list(LABELS)})
    with pytest.raises(ValueError, match="validation"):
        train(one_each, tmp_path, **kw(tiny_base))


def test_source_column_is_optional_and_time_budget_stops(tiny_base: str, tmp_path: Path) -> None:
    rep = train(
        synth().drop("source"), tmp_path / "m", epochs=50, max_minutes=1e-9, **kw(tiny_base)
    )
    assert rep.stopped_on_time_budget and rep.steps == 1 and rep.planned_steps > 1


def test_max_steps_and_frozen_embeddings_off(tiny_base: str, tmp_path: Path) -> None:
    rep = train(synth(), tmp_path / "m", max_steps=2, freeze_embeddings=False, **kw(tiny_base))
    assert rep.steps == 2 == rep.planned_steps and not rep.stopped_on_time_budget


def test_macro_f1() -> None:
    assert macro_f1([0, 1, 2], [0, 1, 2]) == 1.0
    assert macro_f1([0, 0, 1, 1], [0, 0, 0, 0]) == pytest.approx((2 / 3 + 0.0) / 2)
    assert macro_f1([], []) == 0.0


def test_load_default_device(trained: tuple[Path, TrainReport]) -> None:
    sc = FineTunedScorer.load(trained[0])  # mps if available, else cpu
    assert sc.device in {"mps", "cpu"} and sc.score_text("the committee will hold").label


def test_load_missing_weights(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        FineTunedScorer.load(tmp_path)
