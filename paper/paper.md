---
title: "Reading the Room: Do LLM Tone Scores of Central-Bank Communication Carry Policy Signal? Evidence from Seven Central Banks in Three Languages"
author: "Thanatchon Chongmankhong"
date: "October 2026"
bibliography: docs/literature/refs.bib
link-citations: true
---

> **Disclaimer.** This is an independent open-source project. It uses only documents published on
> central banks' public websites (or public mirrors of them), represents the views of no institution,
> and is not investment advice. The author is employed by a central bank; nothing here draws on
> non-public information, and the text makes no comment on any bank's policy choices, only on
> measurable properties of published text and on statistical results. The Bank of Thailand adapter
> is opt-in and excluded from all headline results.

# Abstract

<!-- RESULTS:ABSTRACT -->

# 1. Introduction

Central banks publish a decision statement, and often minutes and a press conference, after every
policy meeting. Turning that text into a number, a *tone* from dovish to hawkish, is now routine in
research and in markets. The measurement literature, however, is overwhelmingly about the Federal
Reserve and the ECB, almost entirely in English, and rarely asks whether the newest tool, a large
language model (LLM) prompted to read the text, has *seen the outcomes it is asked to predict*
during training.

This paper does three things. First, it releases `cbtone`, a Python library that fetches public
central-bank communications politely, versions them as a hashed corpus, and scores them with four
scorer families (a cited hawkish/dovish dictionary, a finance-tuned transformer, a local ≤ 4B LLM via
Ollama, and a small fine-tuned multilingual model) behind one interface. Second, it runs a
**pre-registered** study (tag `prereg-v1`, frozen before any scorer touched the full corpus) on seven
headline central banks, the Fed, ECB, Bank of England, Reserve Bank of Australia, Monetary Authority
of Singapore (MAS), Bank Indonesia (BI) and Bank Negara Malaysia (BNM), in English, Indonesian and
Malay. Third, it treats training-data contamination as a first-class threat: every LLM result is
re-estimated on **masked** text (bank, committee and instrument names, countries, dates and rate
levels replaced by placeholders) and on a **post-cutoff** split, and a finding is called *robust* only
if it survives both.

The five research questions ask whether tone predicts the next decision (RQ1), explains the market
reaction to the announcement (RQ2), is consistent between the native-language and English versions of
the same statement (RQ3), is stable across prompts, temperatures and model tags and agrees with human
labels (RQ4), and transfers from the Fed to Southeast Asia (RQ5). Every threshold was fixed in advance;
results that contradict a hypothesis are reported as refuted.

# 2. Related work

Measurement moved from counting words to classifying them, mostly for the Fed. Dictionary approaches
count hawkish and dovish terms [@apel2014informative; @lucca2009measuring] or adapt finance lexicons
[@loughran2011liability; @picault2017words]. Topic models of deliberation [@hansen2018transparency;
@hansen2016shocking] and voice-tone measures [@gorodnichenko2023voice] widen the lens. Supervised
transformers came next: FOMC-RoBERTa, trained on 2,480 hand-labelled FOMC sentences, reaches a weighted
F1 of 0.72 against about 0.50 for a rule-based baseline and 0.59 for zero-shot ChatGPT-3.5
[@shah2023trillion]; CentralBankRoBERTa [@pfeifer2023centralbankroberta] classifies economic sentiment
rather than policy stance. Zero-shot LLM reading of FOMC stance is modest [@hansen2023fedspeak]; a
multi-bank study finds a fine-tuned multilingual encoder far ahead of GPT-4o [@silva2025text]; and prompt
format alone can move accuracy by tens of points [@sclar2024quantifying].

Contamination is measurable: LLMs recall macro outcomes almost perfectly before their training cutoff
and near chance after it [@lopezlira2025memorization]; masking entity names changes LLM sentiment
signals [@glasserman2024lookahead]; formal look-ahead tests exist [@sarkar2024lookahead]. No study we
found combines masking and a post-cutoff split on central-bank text.

The event-study template is standard [@kuttner2001monetary; @gurkaynak2005actions;
@bernanke2005explains; @blinder2008central]. Text-based measures explain far less of daily moves than
rate surprises; changes in statement wording reach pseudo-R² up to 0.12 [@ehrmann2020starting]. Evidence
for Southeast Asia is thin: a Malaysian yield-curve event study [@ho2021effects], regional transparency
surveys [@filardo2008transparency], and a description of Singapore's exchange-rate regime
[@parrado2004singapore]; we found no study linking MAS statement text to the Singapore dollar, and none
comparing tone between native-language and English versions of the same central-bank document.

# 3. Data

**Corpus.** Adapters fetch each bank's public pages under robots.txt, a ≥ 2 s per-host rate limit, and a
descriptive User-Agent, caching every response with its SHA-256. MAS serves a bot page to automated
clients and pbc.gov.cn disallows crawlers; with the author's approval, both are read from Internet
Archive copies, never from the banks' own sites. The snapshot used here
(`{{corpus_version}}`) holds 2,935 documents. Each bank's primary decision series is fixed in the
pre-registration: FOMC statements, ECB decision press releases, BoE MPC minutes (its 2000–2006 releases
are a single sentence), RBA statements from December 2007 (earlier releases exist only when the rate
changed), MAS Monetary Policy Statements, and BI and BNM statements (English primary; Indonesian and Malay
twins for RQ3). Text is committed only where the source's terms allow redistribution (Fed, ECB decision
releases, RBA); for the other banks the repository holds URLs and hashes, and `make fetch` rebuilds the
text locally.

**Decisions.** Rate decisions come from the BIS central-bank policy-rate series, matched to meeting dates
from the corpus; holds are meetings without a change. MAS sets an exchange-rate band, not a rate, so its
decisions (tighten / maintain / ease) come from MAS's own published decision table.

**Markets.** Daily FX closes (Yahoo Finance; bad ticks filtered by a pre-specified rule) and 2-year
government yields where a free daily official source exists (US, euro area, UK, Australia). Moves are
taken over [*t*−1, *t*+1] closes around the release; a document without a release time is timed at 00:00
local on its release date, so the window always contains it.

**Labels.** Human labels exist only for the Fed: the FOMC hawkish/dovish test split
[@shah2023trillion], used for evaluation only under its CC-BY-NC licence. For Southeast Asia, 200
sentences (MAS 60; BI 35 en + 35 id; BNM 35 en + 35 ms) carry **silver** labels from two LLM passes with
different prompts and a tie-break; they are never called gold.

# 4. Method

**Scorers.** All scorers return probabilities over {hawkish, dovish, neutral} and an index
*hawkish − dovish* ∈ [−1, 1], computed on the same input: the decision, forward-guidance, outlook and
risk paragraphs of a document (rule-based tagger), capped at 3,000 characters. The *dictionary* uses a
167-term cited lexicon with negation handling (English only). The *LLM* is `qwen3:4b` run locally through
Ollama at temperature 0 with a registered prompt (P1) and structured JSON output; all calls are cached by
content hash. The *fine-tuned* model is XLM-R base trained for ≤ 30 minutes on the LLM's own sentence
labels (never on FOMC data). FOMC-RoBERTa is implemented but is a gated model whose access was pending at
the time of the run; it is reported as not run.

**RQ1.** Per bank, an ordered logit (cut < hold < hike) on (tone, Δtone, last direction) is refit at every
decision on an expanding window (initial 40 %, at least 30) and predicts the next decision. The baseline is
persistence (smoothed P(next | last)). The gain ΔLL = LL(reference) − LL(model) in multiclass log-loss is
tested with a moving-block bootstrap (block 4); Holm correction across adequately powered banks; and the
real gain must beat shuffled-date and permuted-label placebos (1,000 permutations each).

**RQ2.** The tone surprise is tone minus its AR(1) forecast fitted on earlier documents only. Signed FX
(positive = domestic appreciation) and 2-year-yield moves are regressed on it with Newey–West errors;
the R² must beat a non-announcement-day placebo, and the LLM's R² is compared with the dictionary's by
paired block bootstrap.

**RQ3–RQ5.** Cross-lingual consistency uses Spearman ρ and the stance-flip rate on parallel documents.
Stability uses Krippendorff's α and ICC(2,1) across five prompt paraphrases, two temperatures, two model
tags and three aggregation strategies. Agreement with human labels is macro-F1 on the FOMC test split.
Transfer compares each Fed-calibrated scorer's FOMC macro-F1 with its silver-set macro-F1 per bank.

**Power and multiplicity.** Each (bank, RQ) cell has a pre-set minimum sample; underpowered cells are
reported in the appendix and excluded from Holm families and majority counts, and a majority needs at
least three powered banks.

**Budget.** The pre-registered compute ladder was applied from timing alone before any outcome was seen:
input cap 6,000 → 3,000 characters, the RQ4a sentence sample 1,000 → 250, the masked variant on the headline
primary series only. The LLM stage still exceeded its 2-hour budget (Section 8).

# 5. Results

<!-- RESULTS:RQ1 -->

<!-- RESULTS:RQ2 -->

<!-- RESULTS:RQ3 -->

# 6. Contamination and reliability

<!-- RESULTS:RQ4 -->

# 7. Transfer to Southeast Asia

<!-- RESULTS:RQ5 -->

# 8. Threats to validity

- **Small samples for Southeast Asian banks.** BI text starts in April 2016 (the bank's index lists nothing
  older) and BNM changes its rate rarely, so several cells fall below the pre-registered minimum and are
  reported as underpowered rather than tested.
- **Silver labels.** The Southeast Asian evaluation set is labelled by the same model family as the LLM
  scorer; the LLM's own silver score is therefore reported but not used for any hypothesis.
- **Model cutoff.** The post-cutoff window (after the model's public release date, 29 April 2025) is short,
  so the post-cutoff check is often inconclusive; an inconclusive check means a finding is *not established
  as robust*.
- **Document selection.** One primary series per bank; BoE uses minutes because its early releases carry
  no text; RBA starts in December 2007.
- **Timing.** MAS and BI publish no release time; their event windows span the whole release day.
- **MAS decisions.** Taken from MAS's own table; the rule-based extractor's accuracy is development
  accuracy only and is used for two 2026 statements, which are excluded from tests.
- **Gated scorer.** FOMC-RoBERTa could not be run, which makes the transfer hypothesis (H5) untestable as
  pre-registered.
- **Compute.** The local 4B model is far smaller than hosted LLMs; results speak to what an analyst can run
  on a laptop, not to frontier models.

# 9. Reproducibility statement

All code is Apache-2.0 at <https://github.com/thanatchon36/cbtone>. `make reproduce` rebuilds every table
and figure from the committed corpus snapshot (scores are cached by content hash, so a re-run makes no new
LLM calls). The pre-registration is the git tag `prereg-v1`; every later deviation is listed in
`docs/DECISIONS.md` (D17–D19) and every data anomaly in `docs/ANOMALIES.md`. Hardware: Apple M4, 16 GB,
no CUDA (`results/hardware.json`); per-stage wall time is in `results/timing.json`.

# 10. Conclusion

<!-- RESULTS:CONCLUSION -->

# References
