import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cbtone.scorers import dictionary as dm
from cbtone.scorers.base import Scorer
from cbtone.scorers.dictionary import DictionaryScorer, LexiconEntry
from cbtone.sources.base import PoliteFetcher, RawResponse

ROOT = Path(__file__).resolve().parents[1]
LM_CSV = (
    "﻿Word,Seq_num,Negative,Positive,Uncertainty\n"
    "LOSS,1,2009,0,0\n"
    "GAIN,2,0,2009,0\n"
    "MAY,3,0,0,2009\n"
    "RATE,4,0,0,0\n"
).encode()


@pytest.fixture(scope="module")
def scorer() -> DictionaryScorer:
    return DictionaryScorer()


def idx(scorer: DictionaryScorer, text: str) -> float:
    return scorer.score_text(text).index


# -- lexicon ----------------------------------------------------------------------------------
def test_lexicon_loads_with_both_polarities_and_valid_sources():
    entries = dm.load_lexicon()
    pols = {e.polarity for e in entries}
    assert pols == {"hawkish", "dovish"}
    assert len(entries) >= 100
    assert any(len(e.stems) >= 2 for e in entries)  # bigrams present
    bib = (ROOT / "docs/literature/refs.bib").read_text()
    keys = set(re.findall(r"^@\w+\{([^,]+),", bib, flags=re.M))
    assert {e.source_key for e in entries} <= keys


def test_lexicon_rejects_bad_rows(tmp_path):
    def write(body: str) -> Path:
        p = tmp_path / "lex.csv"
        p.write_text("term,polarity,weight,source_key,note\n" + body)
        return p

    with pytest.raises(ValueError, match="polarity"):
        dm.load_lexicon(write("raise rate,bullish,1,k,n\n"))
    with pytest.raises(ValueError, match="weight"):
        dm.load_lexicon(write("raise rate,hawkish,0,k,n\n"))
    with pytest.raises(ValueError, match="source_key"):
        dm.load_lexicon(write("raise rate,hawkish,1,,n\n"))
    with pytest.raises(ValueError, match="clashes"):
        dm.load_lexicon(write("raise rate,hawkish,1,k,n\nraises rates,dovish,1,k,n\n"))
    assert len(dm.load_lexicon(write("raise rate,hawkish,1,k,n\n"))) == 1


@pytest.mark.parametrize(
    ("a", "b"),
    [("raise", "raised"), ("rate", "rates"), ("increase", "increasing"), ("cut", "cutting")],
)
def test_stem_conflates_inflections(a, b):
    assert dm.stem(a) == dm.stem(b)


# -- scoring ----------------------------------------------------------------------------------
def test_is_a_scorer_for_english_only(scorer):
    assert isinstance(scorer, Scorer)
    assert scorer.scorer_id == "dict-v1"
    assert scorer.supports("en")
    assert not scorer.supports("th")
    assert scorer.model_digest and len(scorer.model_digest) == 12
    with pytest.raises(ValueError, match="en"):
        scorer.score_text("ขึ้นดอกเบี้ย", "th")


def test_hawkish_dovish_and_neutral_signs(scorer):
    hawk = scorer.score_text("The Committee decided to raise rates to contain inflation pressures.")
    dove = scorer.score_text("The Committee lowered the policy rate as growth weakened.")
    flat = scorer.score_text("Rates were left unchanged.")
    assert hawk.index > 0.4 and hawk.label == "hawkish"
    assert dove.index < -0.4 and dove.label == "dovish"
    assert flat.index == 0.0 and flat.neutral_p == 1.0 and flat.evidence_spans == []
    assert hawk.evidence_spans == ["raise rates", "inflation pressures"]
    assert dove.evidence_spans == ["lowered the policy rate", "growth weakened"]
    assert hawk.scorer_id == "dict-v1"


def test_probability_formula(scorer):
    # One strong hawkish hit, one sentence: h=1, d=0, n=1+0.5*1=1.5.
    s = scorer.score_text("Members saw a rate hike as appropriate.")
    assert s.hawkish_p == pytest.approx(1 / 2.5)
    assert s.dovish_p == 0.0
    assert s.neutral_p == pytest.approx(1.5 / 2.5)
    # A second, empty sentence only adds neutral mass.
    s2 = scorer.score_text("Members saw a rate hike as appropriate. The meeting ended.")
    assert s2.hawkish_p == pytest.approx(1 / 3.0)


def test_empty_text_is_neutral(scorer):
    for t in ("", "   \n "):
        s = scorer.score_text(t)
        assert (s.neutral_p, s.index) == (1.0, 0.0)


def test_negation_flips_within_three_tokens(scorer):
    assert idx(scorer, "The Committee will raise rates.") > 0
    assert idx(scorer, "The Committee will not raise rates.") < 0
    assert idx(scorer, "The Committee will never lower rates.") > 0
    assert idx(scorer, "Policy was eased without any rate hike.") < 0
    s = scorer.score_text("The Committee will not raise rates.")
    assert s.evidence_spans == ["not raise rates"]


def test_negation_window_is_five_tokens(scorer):
    # "not" up to 5 tokens before "tighten" flips; 6 or more does not.
    assert idx(scorer, "It did not need to tighten.") < 0
    assert idx(scorer, "It did not see a need to tighten.") < 0
    assert idx(scorer, "It did not see any real need now to tighten.") > 0


def test_negation_does_not_cross_sentences(scorer):
    assert idx(scorer, "The Committee did not act. Rate hike expected.") > 0
    assert idx(scorer, "No change was made. Rate hike expected.") > 0


def test_filler_gap_and_longest_match():
    s = DictionaryScorer(
        [
            LexiconEntry("raise rate", "hawkish", 1.0, "k", ""),
            LexiconEntry("raise rate sharply", "dovish", 1.0, "k", ""),
        ]
    )
    assert s.find_hits("raise the policy rate")[0].span == "raise the policy rate"
    assert s.find_hits("raise the very large rate") == []  # "very" is not a filler
    assert s.find_hits("raise rates sharply")[0].polarity == "dovish"  # longest wins
    assert len(s.find_hits("raise rate. raise rate")) == 2


def test_tokens_are_not_double_counted(scorer):
    hits = scorer.find_hits("Higher inflation pressures")
    assert len(hits) == 1


def test_evidence_spans_capped_at_ten(scorer):
    s = scorer.score_text(" ".join(["Members saw a rate hike."] * 15))
    assert len(s.evidence_spans) == 10


def test_deterministic(scorer):
    t = "Inflation pressures persist; the Committee will raise rates but growth weakened."
    assert scorer.score_text(t) == scorer.score_text(t)
    assert DictionaryScorer().score_text(t) == scorer.score_text(t)


def test_digest_changes_with_lexicon():
    a = DictionaryScorer([LexiconEntry("raise rate", "hawkish", 1.0, "k", "")])
    b = DictionaryScorer([LexiconEntry("raise rate", "hawkish", 0.5, "k", "")])
    assert a.model_digest != b.model_digest


def test_score_document_uses_policy_text(scorer, monkeypatch):
    from cbtone.schema import Document

    seen = {}

    def fake_policy_text(doc, cap):
        seen["cap"] = cap
        return "The Committee decided to raise rates."

    monkeypatch.setattr("cbtone.text.paragraphs.policy_text", fake_policy_text)
    doc = Document.model_construct(language="en")
    assert scorer.score_document(doc).index > 0
    assert seen["cap"] == 6000


# -- Loughran-McDonald (optional, run-time) ---------------------------------------------------
def test_lm_wordlists_and_features(tmp_path):
    p = tmp_path / "lm.csv"
    p.write_bytes(LM_CSV)
    lm = dm.load_lm_wordlists(p)
    assert lm.negative == {"loss"} and lm.positive == {"gain"} and lm.uncertainty == {"may"}
    s = DictionaryScorer(lm=lm)
    assert s.lm_features("A loss may follow a gain, a loss") == {
        "tokens": 8,
        "negative": 2,
        "positive": 1,
        "uncertainty": 1,
    }
    # LM features never change the index.
    t = "The Committee will raise rates."
    assert s.score_text(t) == DictionaryScorer().score_text(t)


def test_lm_features_need_lists(scorer):
    with pytest.raises(RuntimeError, match="Loughran"):
        scorer.lm_features("loss")


def test_lm_rejects_other_csv(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="master dictionary"):
        dm.load_lm_wordlists(p)


class FakeFetcher(PoliteFetcher):
    def __init__(self, content: bytes) -> None:  # type: ignore[no-untyped-def]
        self.content = content
        self.calls: list[tuple[str, str]] = []

    def get(self, bank: str, url: str) -> RawResponse:
        self.calls.append((bank, url))
        return RawResponse(url, self.content, "text/csv", "00" * 32, datetime.now(UTC), True)


def test_fetch_lm_downloads_once_into_cache(tmp_path):
    f = FakeFetcher(LM_CSV)
    path = dm.fetch_lm_master_dictionary(f, cache_dir=tmp_path / "cache")
    assert path.read_bytes() == LM_CSV
    assert dm.fetch_lm_master_dictionary(f, cache_dir=tmp_path / "cache") == path
    assert len(f.calls) == 1 and f.calls[0][1] == dm.LM_CSV_URL
    assert dm.load_lm_wordlists(path).negative == {"loss"}


def test_fetch_lm_rejects_html_page(tmp_path):
    f = FakeFetcher(b"<html>Google Drive - Virus scan warning</html>")
    with pytest.raises(RuntimeError, match="manually"):
        dm.fetch_lm_master_dictionary(f, cache_dir=tmp_path)
    assert not (tmp_path / dm.LM_CACHE_FILE).exists()
