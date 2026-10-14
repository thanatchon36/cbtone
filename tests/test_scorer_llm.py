"""LLMScorer tests: fake Ollama via httpx.MockTransport, no real server."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import httpx
import pytest

from cbtone.schema import Document
from cbtone.scorers.base import ScoreCache, ToneScore
from cbtone.scorers.llm import PROMPT_IDS, LLMError, LLMScorer, load_prompt

DIGEST = "ab" * 32
TAGS = {"models": [{"name": "qwen3:4b", "model": "qwen3:4b", "digest": DIGEST}]}


def chat_reply(h: float = 0.7, d: float = 0.2, n: float = 0.1, **extra: Any) -> httpx.Response:
    body = {"hawkish": h, "dovish": d, "neutral": n, **extra}
    return httpx.Response(200, json={"message": {"role": "assistant", "content": json.dumps(body)}})


class Fake:
    """Handler that records /api/chat requests and replays scripted responses."""

    def __init__(
        self,
        replies: list[httpx.Response | Exception] | None = None,
        tags: httpx.Response | Exception | None = None,
    ) -> None:
        self.replies = replies
        self.tags = tags if tags is not None else httpx.Response(200, json=TAGS)
        self.chats: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            if isinstance(self.tags, Exception):
                raise self.tags
            return self.tags
        assert request.url.path == "/api/chat"
        self.chats.append(json.loads(request.content))
        if self.replies is None:
            return chat_reply()
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def cache(tmp_path: Path) -> Iterator[ScoreCache]:
    c = ScoreCache(tmp_path / "scores.sqlite")
    yield c
    c.close()


def make(
    fake: Callable[[httpx.Request], httpx.Response], cache: ScoreCache, **kw: Any
) -> LLMScorer:
    kw.setdefault("retry_wait", 0.0)
    return LLMScorer(cache=cache, transport=httpx.MockTransport(fake), **kw)


def make_doc(text: str, language: str = "en") -> Document:
    return Document(
        bank="fed",
        date=date(2024, 3, 20),
        doc_type="statement",
        language=language,  # type: ignore[arg-type]
        title="t",
        text=text,
        url="https://example.org/x",
        sha256="0" * 64,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


# -- prompts -----------------------------------------------------------------------------------


def test_prompts_registered_and_hashed() -> None:
    assert PROMPT_IDS == ("P1", "P2", "P3", "P4", "P5")
    texts = set()
    for pid in PROMPT_IDS:
        prompt_id, text = load_prompt(pid)
        raw = (resources.files("cbtone") / "data" / "prompts" / f"{pid}.txt").read_bytes()
        assert prompt_id == f"{pid}@{hashlib.sha256(raw).hexdigest()[:8]}"
        assert re.fullmatch(r"P[1-5]@[0-9a-f]{8}", prompt_id)
        low = text.lower()
        assert "hawkish" in low and "dovish" in low and "neutral" in low
        assert "indonesian" in low and "thai" in low and "chinese" in low and "malay" in low
        texts.add(text)
    assert len(texts) == 5


def test_p1_is_bank_agnostic() -> None:
    _, text = load_prompt("P1")
    for name in (
        "Fed",
        "Federal",
        "ECB",
        "European",
        "England",
        "Bank of",
        "Bank Indonesia",
        "Reserve",
        "Committee",
        "FOMC",
        "MAS",
    ):
        assert name not in text


def test_unknown_prompt_rejected(cache: ScoreCache) -> None:
    with pytest.raises(ValueError, match="unknown prompt"):
        make(Fake(), cache, prompt="P9")


# -- digest / connection -----------------------------------------------------------------------


def test_digest_and_identity(cache: ScoreCache) -> None:
    s = make(Fake(), cache)
    assert s.model_digest == DIGEST
    assert s.scorer_id == "llm"
    assert s.prompt_id is not None and s.prompt_id.startswith("P1@")
    assert s.supports("th") and s.supports("zh") and s.supports("ms")


def test_digest_latest_suffix(cache: ScoreCache) -> None:
    tags = httpx.Response(200, json={"models": [{"name": "foo:latest", "digest": "dd"}]})
    assert make(Fake(tags=tags), cache, model="foo").model_digest == "dd"


def test_missing_model_tag(cache: ScoreCache) -> None:
    with pytest.raises(LLMError, match="not available"):
        make(Fake(), cache, model="nope:1b")


def test_ollama_down(cache: ScoreCache) -> None:
    with pytest.raises(LLMError, match="not reachable"):
        make(Fake(tags=httpx.ConnectError("refused")), cache)


def test_tags_http_error(cache: ScoreCache) -> None:
    with pytest.raises(LLMError, match="HTTP 503"):
        make(Fake(tags=httpx.Response(503)), cache)


def test_tags_malformed(cache: ScoreCache) -> None:
    with pytest.raises(LLMError, match="unexpected"):
        make(Fake(tags=httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})), cache)


# -- request format ----------------------------------------------------------------------------


def test_request_format_sentence(cache: ScoreCache) -> None:
    fake = Fake()
    s = make(fake, cache)
    score = s.score_text("Rates were left unchanged.")
    req = fake.chats[0]
    assert req["model"] == "qwen3:4b"
    assert req["stream"] is False and req["think"] is False
    assert req["options"] == {
        "temperature": 0.0,
        "num_predict": 64,
        "num_ctx": 8192,
        "seed": 20261014,
    }
    fmt = req["format"]
    assert isinstance(fmt, dict)  # a schema, never the plain string "json"
    assert fmt["required"] == ["hawkish", "dovish", "neutral"]
    assert "evidence" not in fmt["properties"]
    assert req["messages"][0] == {"role": "system", "content": load_prompt("P1")[1]}
    assert req["messages"][1]["role"] == "user"
    assert req["messages"][1]["content"].endswith("Rates were left unchanged.")
    assert score.scorer_id == "llm" and score.model_digest == DIGEST
    assert score.prompt_id == s.prompt_id


def test_request_format_document_and_evidence(cache: ScoreCache) -> None:
    fake = Fake([chat_reply(evidence=["a", " b ", "", 3, "c", "d"])])
    s = make(fake, cache)
    doc = make_doc("The Committee decided to raise the policy rate.")
    score = s.score_document(doc)
    req = fake.chats[0]
    assert req["options"]["num_predict"] == 160
    ev = req["format"]["properties"]["evidence"]
    assert ev["maxItems"] == 3 and ev["type"] == "array"
    assert req["format"]["required"] == ["hawkish", "dovish", "neutral"]
    assert "evidence" in req["messages"][0]["content"]
    assert score.evidence_spans == ["a", "b", "c"]
    assert "The Committee decided" in req["messages"][1]["content"]


def test_probabilities_are_normalised(cache: ScoreCache) -> None:
    s = make(Fake([chat_reply(70, 20, 10)]), cache)
    r = s.score_text("x")
    assert (r.hawkish_p, r.dovish_p, r.neutral_p) == pytest.approx((0.7, 0.2, 0.1))
    assert r.index == pytest.approx(0.5)


def test_empty_text_and_bad_language(cache: ScoreCache) -> None:
    s = make(Fake(), cache)
    with pytest.raises(ValueError, match="empty"):
        s.score_text("   ")
    with pytest.raises(ValueError, match="language"):
        s.score_text("hola", "es")  # type: ignore[arg-type]


# -- cache -------------------------------------------------------------------------------------


def test_cache_prevents_recall(cache: ScoreCache) -> None:
    fake = Fake()
    s = make(fake, cache)
    a = s.score_text("Rates rose.")
    b = s.score_text("Rates rose.")
    assert a == b
    assert (s.calls_made, s.cache_hits) == (1, 1)
    assert len(fake.chats) == 1
    # a fresh scorer sharing the cache (a re-run) also never calls the model
    fake2 = Fake()
    s2 = make(fake2, cache)
    assert s2.score_text("Rates rose.") == a
    assert (s2.calls_made, s2.cache_hits, len(fake2.chats)) == (0, 1, 0)


def test_cache_variants_do_not_collide(cache: ScoreCache) -> None:
    fake = Fake()
    text = "The Fed raised rates in March 2024."
    make(fake, cache).score_text(text)
    make(fake, cache, masked=True).score_text(text)
    make(fake, cache, temperature=0.7).score_text(text)
    make(fake, cache, prompt="P2").score_text(text)
    make(fake, cache).score_document(make_doc(text))
    assert len(fake.chats) == 5
    assert len(cache) == 5


def test_masking_applied_before_call(cache: ScoreCache) -> None:
    fake = Fake()
    make(fake, cache, masked=True).score_text(
        "The Federal Reserve raised rates by 25 basis points."
    )
    sent = fake.chats[0]["messages"][1]["content"]
    assert "Federal Reserve" not in sent and "[BANK]" in sent and "25" not in sent
    assert fake.chats[0]["options"]["temperature"] == 0.0


def test_temperature_and_seed_sent(cache: ScoreCache) -> None:
    fake = Fake()
    make(fake, cache, temperature=0.7, seed=5).score_text("x")
    assert fake.chats[0]["options"]["temperature"] == 0.7
    assert fake.chats[0]["options"]["seed"] == 5


# -- retries -----------------------------------------------------------------------------------


def bad_content(content: str) -> httpx.Response:
    return httpx.Response(200, json={"message": {"content": content}})


def test_retry_on_5xx_then_success(cache: ScoreCache) -> None:
    fake = Fake([httpx.Response(500), httpx.Response(503), chat_reply()])
    s = make(fake, cache)
    s.score_text("x")
    assert s.calls_made == 3


def test_retry_on_timeout_and_transport_error(cache: ScoreCache) -> None:
    fake = Fake([httpx.ReadTimeout("slow"), httpx.ConnectError("reset"), chat_reply()])
    s = make(fake, cache)
    assert s.score_text("x").scorer_id == "llm"
    assert s.calls_made == 3


@pytest.mark.parametrize(
    "reply",
    [
        bad_content("not json at all"),
        bad_content('["a"]'),
        bad_content('{"hawkish": 0.5, "dovish": 0.5}'),
        bad_content('{"hawkish": "high", "dovish": 0.1, "neutral": 0.1}'),
        bad_content('{"hawkish": true, "dovish": 0.1, "neutral": 0.1}'),
        bad_content('{"hawkish": -0.2, "dovish": 0.1, "neutral": 0.1}'),
        bad_content('{"hawkish": NaN, "dovish": 0.1, "neutral": 0.1}'),
        bad_content('{"hawkish": 0, "dovish": 0, "neutral": 0}'),
        httpx.Response(200, text="<html>"),
        httpx.Response(200, json={"error": "x"}),
    ],
)
def test_retry_on_invalid_output(cache: ScoreCache, reply: httpx.Response) -> None:
    s = make(Fake([reply, chat_reply()]), cache)
    assert s.score_text("x").hawkish_p == pytest.approx(0.7)
    assert s.calls_made == 2


def test_three_failures_raise_and_not_cached(cache: ScoreCache) -> None:
    s = make(Fake([bad_content("no")] * 3), cache)
    with pytest.raises(LLMError, match="after 3 attempts"):
        s.score_text("x")
    assert s.calls_made == 3
    assert len(cache) == 0


def test_client_error_not_retried(cache: ScoreCache) -> None:
    s = make(Fake([httpx.Response(404, text="model not found")]), cache)
    with pytest.raises(LLMError, match="HTTP 404"):
        s.score_text("x")
    assert s.calls_made == 1


def test_backoff_sleeps(cache: ScoreCache, monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []
    monkeypatch.setattr("cbtone.scorers.llm.time.sleep", waits.append)
    s = make(Fake([httpx.Response(500), httpx.Response(500), chat_reply()]), cache, retry_wait=1.0)
    s.score_text("x")
    assert waits == [1.0, 2.0]


# -- modes and aggregation ---------------------------------------------------------------------


def test_score_sentences_one_call_each(cache: ScoreCache) -> None:
    fake = Fake([chat_reply(1, 0, 0), chat_reply(0, 1, 0), chat_reply(0, 0, 1)])
    s = make(fake, cache)
    out = s.score_sentences(["a.", "b.", "c."])
    assert [o.label for o in out] == ["hawkish", "dovish", "neutral"]
    assert len(fake.chats) == 3
    for req, sent in zip(fake.chats, "abc", strict=True):
        assert req["messages"][1]["content"] == f"Text:\n{sent}."


def ts(h: float, d: float, n: float) -> ToneScore:
    return ToneScore.from_probs(h, d, n, scorer_id="llm")


def test_aggregate_strategies(cache: ScoreCache) -> None:
    s = make(Fake(), cache)
    scores = [ts(1, 0, 0), ts(0, 0.5, 0.5), ts(0, 1, 0)]
    mean = s.aggregate(scores, "mean")
    assert mean.hawkish_p == pytest.approx(1 / 3) and mean.dovish_p == pytest.approx(0.5)
    assert mean.model_digest == DIGEST and mean.prompt_id == s.prompt_id
    dw = s.aggregate(scores, "decision_weighted", tags=["decision", "other", "decision"])
    assert dw.hawkish_p == pytest.approx(2 / 5)
    assert dw.dovish_p == pytest.approx((0.5 + 2) / 5)
    assert s.aggregate(scores, "max_abs").index == pytest.approx(1.0)  # first of the two ties
    assert s.aggregate([ts(0.2, 0.1, 0.7), ts(0.1, 0.5, 0.4)], "max_abs").index == pytest.approx(
        -0.4
    )


def test_aggregate_errors(cache: ScoreCache) -> None:
    s = make(Fake(), cache)
    with pytest.raises(ValueError, match="unknown strategy"):
        s.aggregate([ts(1, 0, 0)], "median")
    with pytest.raises(ValueError, match="no sentence scores"):
        s.aggregate([], "mean")
    with pytest.raises(ValueError, match="paragraph tag"):
        s.aggregate([ts(1, 0, 0)], "decision_weighted")
    with pytest.raises(ValueError, match="paragraph tag"):
        s.aggregate([ts(1, 0, 0)], "decision_weighted", tags=["a", "b"])


def test_aggregate_collects_evidence(cache: ScoreCache) -> None:
    s = make(Fake(), cache)
    a = ToneScore.from_probs(1, 0, 0, scorer_id="llm", evidence_spans=["q1", "q2"])
    b = ToneScore.from_probs(0, 1, 0, scorer_id="llm", evidence_spans=["q2", "q3", "q4"])
    assert s.aggregate([a, b], "mean").evidence_spans == ["q1", "q2", "q3"]


DOC_TEXT = (
    "The Committee decided to raise the policy rate by 25 basis points. "
    "It will continue to monitor data.\n\n"
    "Call 555-0100 for media enquiries.\n\n"
    "Inflation remains elevated and growth is solid."
)


def test_document_sentences_and_by_sentence_scoring(cache: ScoreCache) -> None:
    doc = make_doc(DOC_TEXT)
    pairs = LLMScorer.document_sentences(doc)
    assert pairs[0] == (
        "The Committee decided to raise the policy rate by 25 basis points.",
        "decision",
    )
    assert all("media enquiries" not in sent for sent, _ in pairs)
    assert {t for _, t in pairs} >= {"decision", "outlook"}
    fake = Fake()
    s = make(fake, cache)
    out = s.score_document_by_sentences(doc, "decision_weighted")
    assert len(fake.chats) == len(pairs)
    assert all(c["options"]["num_predict"] == 64 for c in fake.chats)
    assert out.hawkish_p == pytest.approx(0.7)


def test_document_sentences_fallback_when_untagged(cache: ScoreCache) -> None:
    doc = make_doc("Lorem ipsum dolor sit amet. Consectetur adipiscing elit.")
    pairs = LLMScorer.document_sentences(doc)
    assert [t for _, t in pairs] == ["other", "other"]
    s = make(Fake(), cache)
    assert s.score_document_by_sentences(doc, "mean").scorer_id == "llm"


def test_no_sentences_raises(cache: ScoreCache) -> None:
    s = make(Fake(), cache)
    with pytest.raises(ValueError, match="no sentences"):
        s.score_document_by_sentences(make_doc("   "))


def test_context_manager(cache: ScoreCache) -> None:
    with make(Fake(), cache) as s:
        assert s.score_text("x").scorer_id == "llm"
    assert s._client.is_closed


# -- optional smoke test against a real local Ollama (deselected by default) --------------------


@pytest.mark.network
def test_live_ollama_smoke(cache: ScoreCache) -> None:
    try:
        s = LLMScorer(cache=cache)
    except LLMError:
        pytest.skip("no local Ollama with qwen3:4b")
    r = s.score_text("The Committee decided to raise the policy rate by 25 basis points.")
    assert 0.0 <= r.hawkish_p <= 1.0 and r.model_digest
