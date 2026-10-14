"""TransformerScorer with a fake tokenizer/model (no downloads, no network)."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from typing import Any

import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")

from cbtone.schema import Document  # noqa: E402
from cbtone.scorers import transformer as tr  # noqa: E402
from cbtone.scorers.base import ScoreCache  # noqa: E402
from cbtone.scorers.transformer import TransformerScorer  # noqa: E402

# FOMC-RoBERTa logit order: 0 dovish, 1 hawkish, 2 neutral
_COLS = {"dovish": 0, "hawkish": 1, "neutral": 2}


class FakeTokenizer:
    """Encodes each text as one id: the stance column it should be classified as."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, texts: list[str], **kw: Any) -> dict[str, Any]:
        self.calls.append({"n": len(texts), **kw})
        ids = []
        for t in texts:
            low = t.lower()
            if "raise" in low or "tighten" in low:
                ids.append(_COLS["hawkish"])
            elif "lower" in low or "weak" in low:
                ids.append(_COLS["dovish"])
            else:
                ids.append(_COLS["neutral"])
        return {"input_ids": torch.tensor(ids).unsqueeze(1)}


class FakeModel:
    def __init__(self) -> None:
        self.forwards = 0

    def __call__(self, input_ids: Any) -> Any:
        self.forwards += 1
        logits = torch.zeros(input_ids.shape[0], 3)
        for row, col in enumerate(input_ids[:, 0].tolist()):
            logits[row, col] = 4.0
        return SimpleNamespace(logits=logits)


def make(**kw: Any) -> tuple[TransformerScorer, FakeTokenizer, FakeModel]:
    tok, model = FakeTokenizer(), FakeModel()
    scorer = TransformerScorer(model=model, tokenizer=tok, device="cpu", **kw)
    return scorer, tok, model


def test_sentence_probs_use_label_map() -> None:
    scorer, _, _ = make()
    hawk, dove, neut = scorer.score_sentences(
        [
            "The Committee decided to raise rates.",
            "The economy weakened.",
            "Inflation is 2 percent.",
        ]
    )
    assert hawk.label == "hawkish" and hawk.index > 0.9
    assert dove.label == "dovish" and dove.index < -0.9
    assert neut.label == "neutral" and abs(neut.index) < 1e-6
    assert hawk.scorer_id == "fomc-roberta"
    assert hawk.model_digest == "aa3bc4281fb1fe73c8872e09ad5c64b898f90d83"
    assert hawk.evidence_spans == []


def test_languages_and_unsupported() -> None:
    scorer, _, _ = make()
    assert scorer.supports("en") and not scorer.supports("th")
    with pytest.raises(ValueError, match="English only"):
        scorer.score_text("ข้อความ", "th")
    with pytest.raises(ValueError, match="English only"):
        scorer.score_sentences(["x"], "zh")


def test_document_mean_and_evidence() -> None:
    scorer, _, _ = make()
    text = (
        "The Committee decided to raise the target range. "
        "Inflation is 2 percent. The economy looks fine. Participants judged that tightening "
        "may be appropriate. Growth was weak."
    )
    s = scorer.score_text(text)
    parts = scorer.score_sentences(
        [
            "The Committee decided to raise the target range.",
            "Inflation is 2 percent.",
            "The economy looks fine.",
            "Participants judged that tightening may be appropriate.",
            "Growth was weak.",
        ]
    )
    assert s.hawkish_p == pytest.approx(sum(p.hawkish_p for p in parts) / 5, abs=1e-6)
    assert s.dovish_p == pytest.approx(sum(p.dovish_p for p in parts) / 5, abs=1e-6)
    assert len(s.evidence_spans) == 3
    assert s.evidence_spans[0] == "The Committee decided to raise the target range."  # ties: order
    assert "Inflation is 2 percent." not in s.evidence_spans
    assert s.model_digest == scorer.model_digest


def test_empty_text_is_neutral() -> None:
    scorer, tok, _ = make()
    s = scorer.score_text("   ")
    assert s.neutral_p == 1.0 and s.index == 0.0
    assert tok.calls == []


def test_batching_order_and_truncation_args() -> None:
    scorer, tok, model = make(batch_size=2, max_length=64)
    sents = [
        "A very long neutral sentence about nothing in particular at all.",
        "Raise.",
        "Weak.",
        "Plain.",
        "Tighten now.",
    ]
    out = scorer.score_sentences(sents)
    assert [o.label for o in out] == ["neutral", "hawkish", "dovish", "neutral", "hawkish"]
    assert [c["n"] for c in tok.calls] == [2, 2, 1]
    assert model.forwards == 3
    assert all(c["truncation"] is True and c["max_length"] == 64 for c in tok.calls)


def test_cache_hits_skip_model(tmp_path: Any) -> None:
    cache = ScoreCache(tmp_path / "s.sqlite")
    scorer, tok, model = make(cache=cache)
    first = scorer.score_sentences(["Raise rates.", "Raise rates.", "Growth was weak."])
    assert len(cache) == 2  # duplicates scored once
    assert first[0] == first[1]
    n_calls = len(tok.calls)
    again = scorer.score_sentences(["Growth was weak.", "Raise rates."])
    assert len(tok.calls) == n_calls and model.forwards == n_calls
    assert [a.index for a in again] == [first[2].index, first[0].index]
    # a different revision or max_length must not share cache entries
    other, tok2, _ = make(cache=cache, max_length=32)
    other.score_sentences(["Raise rates."])
    assert len(tok2.calls) == 1
    cache.close()


def test_score_document_uses_policy_text() -> None:
    scorer, _, _ = make()
    doc = Document(
        bank="fed",
        doc_type="statement",
        language="en",
        date=datetime.date(2024, 1, 31),
        title="t",
        text="The Committee decided to raise the target range.\n\nThe press conference will begin.",
        url="https://example.org/x",
        sha256="0" * 64,
        fetched_at=datetime.datetime(2026, 10, 14, tzinfo=datetime.UTC),
    )
    s = scorer.score_document(doc)
    assert s.hawkish_p > 0.9
    assert s.evidence_spans == ["The Committee decided to raise the target range."]


def test_registry_and_unsuitable_cb_roberta() -> None:
    assert tr.get_spec("fomc-roberta").id2stance == {0: "dovish", 1: "hawkish", 2: "neutral"}
    with pytest.raises(ValueError, match=r"sentiment model.*not a hawkish/dovish"):
        TransformerScorer("cb-roberta")
    with pytest.raises(ValueError, match="unknown transformer scorer"):
        TransformerScorer("nope")


def test_check_labels() -> None:
    spec = tr.get_spec("fomc-roberta")
    tr._check_labels(spec, {0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"})
    tr._check_labels(spec, {0: "dovish", 1: "hawkish", 2: "neutral"})
    with pytest.raises(ValueError, match="expected 3"):
        tr._check_labels(spec, {0: "negative", 1: "positive"})
    with pytest.raises(ValueError, match="contradicts"):
        tr._check_labels(spec, {0: "hawkish", 1: "dovish", 2: "neutral"})


class _LoadedModel(FakeModel):
    def __init__(self, id2label: dict[int, str]) -> None:
        super().__init__()
        self.config = SimpleNamespace(id2label=id2label)
        self.moved: str | None = None
        self.evaluated = False

    def to(self, device: str) -> None:
        self.moved = device

    def eval(self) -> None:
        self.evaluated = True


def test_lazy_load_pins_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str | None]] = []
    model = _LoadedModel({0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"})

    def tok_from(repo: str, revision: str | None = None) -> FakeTokenizer:
        seen.append((repo, revision))
        return FakeTokenizer()

    def model_from(repo: str, revision: str | None = None) -> _LoadedModel:
        seen.append((repo, revision))
        return model

    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", tok_from)
    monkeypatch.setattr(
        transformers.AutoModelForSequenceClassification, "from_pretrained", model_from
    )
    scorer = TransformerScorer(device="cpu")
    assert scorer.score_text("Raise rates.").label == "hawkish"
    scorer.score_text("Weak growth.")  # second call must not reload
    assert seen == [("gtfintechlab/FOMC-RoBERTa", "aa3bc4281fb1fe73c8872e09ad5c64b898f90d83")] * 2
    assert model.moved == "cpu" and model.evaluated


def test_lazy_load_rejects_wrong_head(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        transformers.AutoTokenizer, "from_pretrained", lambda *a, **k: FakeTokenizer()
    )
    monkeypatch.setattr(
        transformers.AutoModelForSequenceClassification,
        "from_pretrained",
        lambda *a, **k: _LoadedModel({0: "negative", 1: "positive"}),
    )
    with pytest.raises(ValueError, match="expected 3"):
        TransformerScorer(device="cpu").score_text("Raise rates.")


def test_gated_repo_gives_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: Any, **k: Any) -> None:
        raise OSError("401 gated")

    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", boom)
    with pytest.raises(RuntimeError, match="hf auth login"):
        TransformerScorer(device="cpu").score_text("Raise rates.")


def test_device_autodetect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    assert TransformerScorer().device == "mps"
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    assert TransformerScorer().device == "cpu"


def test_resolve_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    import huggingface_hub

    class FakeApi:
        def model_info(self, repo: str) -> Any:
            return SimpleNamespace(sha=None if repo == "none" else "abc123")

    monkeypatch.setattr(huggingface_hub, "HfApi", FakeApi)
    assert tr.resolve_revision("x/y") == "abc123"
    with pytest.raises(RuntimeError, match="no sha"):
        tr.resolve_revision("none")
