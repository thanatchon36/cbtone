# Spec: scorers (`src/cbtone/scorers/`)

Read first: `src/cbtone/scorers/base.py` (`ToneScore`, `Scorer`, `ScoreCache`, `DOC_CHAR_CAP`),
`src/cbtone/text/paragraphs.py` (`policy_text`), `docs/RESEARCH_QUESTIONS.md` §0.5 and RQ4/RQ5,
`docs/DECISIONS.md` D17, `docs/sources/LICENSES.md`.
**Do not change `base.py` or `paragraphs.py`.** They are the pre-registered contract. If you need a change, report it.

## Common rules
- Each scorer is a `Scorer` subclass with a stable `scorer_id`. It sets `languages` honestly: a scorer
  that cannot read a language must not pretend it can. Callers check `supports(lang)`, and RQ3 reports
  unsupported cells as *not applicable*.
- `score_text` returns `ToneScore.from_probs(...)`. Never build the index by hand.
- Deterministic: same input gives the same output. Any randomness is seeded.
- Heavy dependencies (torch, transformers, peft) are imported lazily inside the class, so `import cbtone`
  works without the `[transformers]` extra. Tests that need them use `pytest.importorskip`.
- No network in unit tests. Model downloads happen only at run time, never in tests.
- Every public function's docstring cites the literature it implements.
- Coverage of each scorer module is ≥ 85 % (the heavy-model paths may be covered with fakes or mocks).
- Run `uv run pytest <your tests> -q --cov=<module>`, then `uv run ruff check` and `uv run ruff format` on
  your files, then `uv run mypy`. Don't run `uv add`; ask the main thread. Don't commit.

## DictionaryScorer (`dictionary.py`, `scorer_id="dict-v1"`)
- **Lexicon:** `src/cbtone/data/lexicon/hawkdove_v1.csv` (packaged data) with columns
  `term, polarity (hawkish|dovish), weight, source_key, note`. Every term cites a `refs.bib` key from
  `docs/literature/` (e.g. Apel & Blix Grimaldi 2012; Bennani & Neuenkirch; Loughran & McDonald for the
  negation and uncertainty words). Only cite sources present in `refs.bib`.
  - Use bigrams in the Apel & Blix Grimaldi style (a modifier like *increase/higher/strong* combined with
    a noun like *inflation/rates/growth*) as well as unigrams.
- **Loughran–McDonald master dictionary:** check its licence. If redistribution isn't allowed, don't
  ship it. Download at run time into `data/cache/` (like `cbtone.eval.anchors`), use only its
  Negative/Positive/Uncertainty lists as optional features, and document this in `LICENSES.md`
  (append a row under the anchor-data table).
- **Negation:** a hawkish or dovish hit preceded within 3 tokens by `not, no, never, without, neither, nor, less`
  flips polarity.
- **Probabilities:** `h` = weighted hawkish hits, `d` = dovish, `n` = 1 + 0.5·(sentence count). Then
  `from_probs(h, d, n)`. Document the constant. `evidence_spans` = the matched phrases (≤ 10).
- **Languages:** `{"en"}` only.

## TransformerScorer (`transformer.py`)
- Two registered ids:
  - `fomc-roberta`: `gtfintechlab/FOMC-RoBERTa`, labels per its model card (LABEL_0 dovish, 1 hawkish, 2 neutral).
    **Verify the mapping from the card**, not from memory.
  - `cb-roberta`: `Moritz-Pfeifer/CentralBankRoBERTa-sentiment-classifier`. Map its labels to
    hawkish/dovish/neutral from its card. If it's a positive/negative *sentiment* model rather than a stance model,
    say so in the docstring and in `docs/sources/LICENSES.md`, and map positive→hawkish and negative→dovish only if
    the card supports that reading. Otherwise mark it unsuitable and leave it out of the registry.
- Device: `mps` if available, else CPU. Batched (batch size 16), max length 256 tokens.
- **Document score:** split `policy_text` into sentences (`cbtone.text.split.split_sentences`), score each, and
  aggregate by mean probabilities. Evidence = the 3 most extreme sentences.
- Cache through `ScoreCache` keyed with the model's revision hash (`model_digest` = the HF commit sha).
- **Languages:** `{"en"}`. The FOMC-RoBERTa licence is CC-BY-NC: evaluation and scoring only, never
  redistributed (already in LICENSES).

## LLMScorer (`llm.py`, `scorer_id="llm"`)
- **Backend:** Ollama HTTP API (`/api/chat`, `stream: false`, `think: false`).
  - Structured output: `format` = a JSON schema with required numbers `hawkish, dovish, neutral`, plus an
    optional `evidence` string array (≤ 3 items) for document mode.
  - Options: `temperature` (default 0), `num_predict` (64 sentence, 160 document), `num_ctx` 8192, `seed` 20261014.
  - `model_digest` = the digest from `/api/tags` for the model tag. Fail clearly if Ollama is down or the tag is missing.
- **Prompts:** 5 registered variants, `P1` (headline) to `P5`, in `src/cbtone/data/prompts/P1.txt`…
  - Each variant asks for the hawkish/dovish/neutral probabilities of the text about **future monetary policy
    stance**. They differ in wording, order of definitions, and whether a one-line definition of each class
    is given (paraphrases, not different tasks).
  - P1 must not mention any bank by name.
  - Write prompts in English; they must handle non-English text ("the text may be in Indonesian, Malay,
    Thai or Chinese").
  - `prompt_id` = `P1@<sha256[:8] of the prompt file>`.
- **Modes:**
  - `score_text`: one call on the text.
  - `score_sentences`: one call per sentence (no batching into one prompt; the RQ4a design).
  - `score_document(doc)`: the default document mode calls `score_text(policy_text(doc))`.
  - `aggregate(sentence_scores, strategy)` with strategies `mean`, `decision_weighted` (sentences from paragraphs
    tagged `decision` get weight 2, via `cbtone.text.paragraphs.tag_paragraph`), and `max_abs` (the sentence
    with max |index|). All three are used in RQ4a.
- **Masked variant:** `LLMScorer(..., masked=True)` applies `cbtone.text.mask.mask_entities(text, lang)` before
  the call. The cache `variant` includes `masked` and the temperature.
- **Robustness:** retry up to 3 times on HTTP 5xx, timeout or invalid JSON. Probabilities that don't sum to 1 are
  normalised by `from_probs`. After 3 failures, raise `LLMError` (the caller records the doc as failed; no
  silent default).
- **Cache:** every call goes through `ScoreCache`, so a re-run never re-calls. Expose `calls_made` and `cache_hits`
  counters for budget logging.
- **`[api]` extra (optional):** an `AnthropicBackend` behind the same interface. Import it lazily, and never
  require it for any test or `make reproduce`.
- **Languages:** `{"en","id","ms","th","zh"}`.
- **Tests:** a fake HTTP transport (`httpx.MockTransport`), no real Ollama. One optional `@pytest.mark.network`
  smoke test against a real local Ollama, deselected by default.

## FineTunedScorer (`finetuned.py`, `scorer_id="ft-xlmr"`)
- **Base:** `FacebookAI/xlm-roberta-base` (multilingual, so RQ3 can use it). Full fine-tune or LoRA, on CPU/MPS,
  ≤ 30 min on an M4.
- **Training data:** silver sentence labels produced by the LLM (supplied later as a parquet `text, lang, label`).
  **Never** the FOMC CC-BY-NC data (LICENSES). The trainer must refuse a dataset whose `source` column
  contains `fomc_communication`.
- **API:**
  - `train(df, out_dir, seed=20261014, max_minutes=30) -> TrainReport` (stops early at the time budget; logs
    loss and wall time);
  - `FineTunedScorer.load(out_dir)`;
  - `score_text`, document mode = mean over sentences, like the transformer.
- Weights go under `data/models/ft-xlmr/` (git-ignored). Release is decided later, depending on licences.
- **Tests:** a tiny random-init config (`hf-internal-testing/tiny-random-xlm-roberta` if it can be loaded offline;
  otherwise build a `XLMRobertaConfig` with 2 layers) trained for a few steps on 20 rows. Skip if torch is missing.
- **Languages:** `{"en","id","ms","th","zh"}`.

## Registry (`__init__.py`)
`get_scorer(name: str, **kw) -> Scorer` with names `dict`, `fomc-roberta`, `cb-roberta` (if suitable), `llm`, `ft`.
