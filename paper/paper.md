---
title: "Reading the Room: Do LLM Tone Scores of Central-Bank Communication Carry Policy Signal? Evidence from Seven Central Banks in Three Languages"
author: "Thanatchon Chongmankhong"
date: "October 2026"
bibliography: docs/literature/refs.bib
link-citations: true
mainfont: "Libertinus Serif"
fontsize: 10pt
papersize: a4
margin:
  x: 2.2cm
  y: 2.4cm
---

> **Disclaimer.** This is an independent open-source project. It uses only documents published on
> central banks' public websites (or public mirrors of them), represents the views of no institution,
> and is not investment advice. The author is employed by a central bank; nothing here draws on
> non-public information, and the text makes no comment on any bank's policy choices, only on
> measurable properties of published text and on statistical results. The Bank of Thailand adapter
> is opt-in and excluded from all headline results.

# Abstract

We ask whether hawkish/dovish tone scores produced by a small local large language model (LLM), `qwen3:4b`
run through Ollama, carry measurable policy signal in the published decision documents of seven central banks
(Fed, ECB, Bank of England, RBA, MAS, Bank Indonesia, Bank Negara Malaysia) in English, Indonesian and Malay.
The study was pre-registered before any scorer touched the full corpus; every LLM result is re-estimated on
masked text and on a post-training-cutoff split. **Every testable hypothesis is refuted at the
pre-registered thresholds.** LLM tone does not improve out-of-sample prediction of the next rate decision over a
persistence baseline at any of {{rq1.verdict.n_powered}} adequately powered banks (closest: ECB, ΔLL
{{rq1.rows[bank=ecb,scorer=llm].dll_vs_pers|.3f}}, Holm *p* {{rq1.rows[bank=ecb,scorer=llm].p_vs_pers_holm|.2f}}). It explains the
announcement-window market move in {{rq2.verdict.h2a.n_success}} of {{rq2.verdict.h2a.n_powered}} bank–market
cells and beats a cited dictionary in none. Native-language and English versions of the same statement agree only
moderately (Spearman ρ {{rq3.rows[bank=bi,scorer=llm].spearman|.2f}} for BI and {{rq3.rows[bank=bnm,scorer=llm].spearman|.2f}} for BNM, against a
pre-registered 0.70), although they almost never point in opposite directions. Scores move with the prompt
wording (Krippendorff's α {{rq4.rq4a.docs.prompts.alpha|.2f}} at document level), and on the human-labelled FOMC test
split the LLM reaches a macro-F1 of {{rq4.rq4b.rows[scorer=llm].macro_f1|.2f}}, above the dictionary ({{rq4.rq4b.rows[scorer=dict].macro_f1|.2f}}) but below
the pre-registered 0.50. The transfer hypothesis is untestable because a gated reference model could not be run. We
release the corpus pipeline, scorers and evaluation harness as the Python package `cbtone`.

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
risk paragraphs of a document (rule-based tagger), capped at 6,000 characters. The *dictionary* uses a
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

**Compute.** All LLM scores come from one backend: the same `qwen3:4b` weights (digest `359d7dd4`) served by
Ollama on a desktop RTX 4070 Ti, where the full pre-registered workload fits the 2-hour LLM budget without any
step of the pre-registered compute ladder. On the MacBook Air M4 named as the project's compute target, the
same model processes about 220 prompt tokens/s (≈ 3.5 s per document at a 3,000-character cap), so a laptop run
needs the ladder (Section 9).

# 5. Results

## 5.1 RQ1: does tone predict the next decision?

**H1 is refuted.** {{rq1.verdict.n_powered}} banks meet the pre-registered power rule (≥ 40 out-of-sample predictions with
≥ 8 hikes and ≥ 8 cuts): Fed, ECB, RBA and BI. The LLM succeeds at none of them (Table 1, Figure 1).

| Bank | OOS *n* | ΔLL vs persistence [95% CI] | Holm *p* | ΔLL vs dictionary | Beats placebos |
|---|---|---|---|---|---|
| Fed | {{rq1.rows[bank=fed,scorer=llm].n_oos|d}} | {{rq1.rows[bank=fed,scorer=llm].dll_vs_pers|.3f}} [{{rq1.rows[bank=fed,scorer=llm].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=fed,scorer=llm].dll_vs_pers_hi|.3f}}] | {{rq1.rows[bank=fed,scorer=llm].p_vs_pers_holm|.2f}} | {{rq1.rows[bank=fed,scorer=llm].dll_vs_dict|.3f}} | {{rq1.rows[bank=fed,scorer=llm].passes_placebo|yn}} |
| ECB | {{rq1.rows[bank=ecb,scorer=llm].n_oos|d}} | {{rq1.rows[bank=ecb,scorer=llm].dll_vs_pers|.3f}} [{{rq1.rows[bank=ecb,scorer=llm].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=ecb,scorer=llm].dll_vs_pers_hi|.3f}}] | {{rq1.rows[bank=ecb,scorer=llm].p_vs_pers_holm|.2f}} | {{rq1.rows[bank=ecb,scorer=llm].dll_vs_dict|.3f}} | {{rq1.rows[bank=ecb,scorer=llm].passes_placebo|yn}} |
| RBA | {{rq1.rows[bank=rba,scorer=llm].n_oos|d}} | {{rq1.rows[bank=rba,scorer=llm].dll_vs_pers|.3f}} [{{rq1.rows[bank=rba,scorer=llm].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=rba,scorer=llm].dll_vs_pers_hi|.3f}}] | {{rq1.rows[bank=rba,scorer=llm].p_vs_pers_holm|.2f}} | {{rq1.rows[bank=rba,scorer=llm].dll_vs_dict|.3f}} | {{rq1.rows[bank=rba,scorer=llm].passes_placebo|yn}} |
| BI | {{rq1.rows[bank=bi,scorer=llm].n_oos|d}} | {{rq1.rows[bank=bi,scorer=llm].dll_vs_pers|.3f}} [{{rq1.rows[bank=bi,scorer=llm].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=bi,scorer=llm].dll_vs_pers_hi|.3f}}] | {{rq1.rows[bank=bi,scorer=llm].p_vs_pers_holm|.2f}} | {{rq1.rows[bank=bi,scorer=llm].dll_vs_dict|.3f}} | {{rq1.rows[bank=bi,scorer=llm].passes_placebo|yn}} |

: Table 1. RQ1, LLM tone, adequately powered banks. ΔLL = LL(reference) − LL(model), multiclass log-loss per
decision; positive is better. Holm correction across the four banks.

The ECB is the only bank where the LLM's gain over persistence has a bootstrap interval above zero and exceeds both
placebo distributions (95th percentiles {{rq1.rows[bank=ecb,scorer=llm].placebo_tone_p95|.3f}} for shuffled tone and
{{rq1.rows[bank=ecb,scorer=llm].placebo_labels_p95|.3f}} for permuted labels); it does not survive the Holm correction. At the RBA the
dictionary, not the LLM, has an interval above zero (ΔLL {{rq1.rows[bank=rba,scorer=dict].dll_vs_pers|.3f}} [{{rq1.rows[bank=rba,scorer=dict].dll_vs_pers_lo|.3f}},
{{rq1.rows[bank=rba,scorer=dict].dll_vs_pers_hi|.3f}}]). BoE (only {{rq1.rows[bank=boe,scorer=llm].n_oos_hike|d}} out-of-sample hikes), MAS
({{rq1.rows[bank=mas,scorer=llm].n_oos|d}} predictions) and BNM ({{rq1.rows[bank=bnm,scorer=llm].n_oos_hike|d}} hikes) are underpowered: they are marked in
Figure 1 but excluded from the test. Ranking metrics are high for every scorer, including persistence (Fed persistence AUROC
{{rq1.rows[bank=fed,scorer=persistence].auroc|.2f}}), because most of the information about the next move is already in the
last one. The masked LLM gives nearly the same ECB estimate ({{rq1.rows[bank=ecb,scorer=llm_masked].dll_vs_pers|.3f}}); BI's masked AUROC of
exactly 1.00 rests on 20 hike/cut cases and is discussed in `ANOMALIES.md` (A9).

![Figure 1. RQ1: gain in next-decision log-loss over persistence, by bank and scorer. * = underpowered.](results/figures/fig_rq1_dll.png)

## 5.2 RQ2: does the tone surprise explain the market reaction?

**H2a and H2b are refuted.** Of {{rq2.verdict.h2a.n_powered}} adequately powered bank–market cells, the LLM tone surprise
explains the release-window move beyond its placebo in {{rq2.verdict.h2a.n_success}} (Table 2), and its R² beats the
dictionary's, after Holm correction, in {{rq2.verdict.h2b.n_success}}.

| Bank | Series | *n* | β | R² | Placebo R² p95 | Holm *p* (β) | ΔR² vs dictionary |
|---|---|---|---|---|---|---|---|
| Fed | USD index | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} |
| Fed | US 2Y | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].beta|.2f}} | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].dr2_vs_dict|.3f}} |
| ECB | EUR/USD | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} |
| ECB | EA 2Y | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].beta|.2f}} | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].dr2_vs_dict|.3f}} |
| BoE | GBP/USD | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} |
| BoE | UK 2Y | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].beta|.2f}} | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].dr2_vs_dict|.3f}} |
| RBA | AUD/USD | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} |
| RBA | AU 2Y | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].beta|.2f}} | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].dr2_vs_dict|.3f}} |
| MAS | USD/SGD | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} |
| BI | USD/IDR | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} |
| BNM | USD/MYR | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} |

: Table 2. RQ2, LLM tone surprise, all powered cells. FX β is the signed two-day log move (positive = domestic
appreciation) per unit surprise; yield β is in basis points per unit surprise. Newey–West standard errors.

The single success is the RBA two-year yield: a one-unit hawkish surprise goes with a {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].beta|.1f}} bp
rise (R² {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].r2|.2f}}, placebo p95 {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].placebo_r2_p95|.3f}}). Its R² gain over the
dictionary has a bootstrap interval above zero ([{{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].dr2_lo|.3f}}, {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].dr2_hi|.3f}}]) but a
Holm-adjusted *p* of {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].p_dr2_holm|.2f}}. For BI the LLM coefficient is significant with the opposite
sign to the hypothesis (β {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].beta|.4f}}, unadjusted *p* {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].p_value|.3f}}): more
hawkish surprises coincide with rupiah depreciation over the day-level window. The one-sided test does not count it,
and the design cannot separate reverse timing from any other explanation (A10). Pooled across banks with bank fixed
effects, the FX coefficient is {{rq2.rq4c.pooled_fx_beta.beta|.4f}} [{{rq2.rq4c.pooled_fx_beta.lo|.4f}},
{{rq2.rq4c.pooled_fx_beta.hi|.4f}}] (*n* = {{rq2.rq4c.pooled_fx_beta.n}}).

![Figure 2. RQ2: FX response to the tone surprise, by bank and scorer (HAC 95% CIs).](results/figures/fig_rq2_fx_beta.png)

## 5.3 RQ3: do native-language and English versions agree?

**H3 is refuted.** On parallel statements the LLM's native-language and English scores have Spearman
ρ = {{rq3.rows[bank=bi,scorer=llm].spearman|.2f}} for BI (Indonesian, *n* = {{rq3.rows[bank=bi,scorer=llm].n_pairs|d}}) and {{rq3.rows[bank=bnm,scorer=llm].spearman|.2f}} for
BNM (Malay, *n* = {{rq3.rows[bank=bnm,scorer=llm].n_pairs|d}}), below the pre-registered 0.70. Disagreement is about intensity, not
direction: the stance flips in {{rq3.rows[bank=bi,scorer=llm].flip_rate|pct1}} and {{rq3.rows[bank=bnm,scorer=llm].flip_rate|pct1}} of pairs, well
under the 10 % ceiling, while the mean absolute gap is {{rq3.rows[bank=bi,scorer=llm].mean_abs_diff|.2f}} and
{{rq3.rows[bank=bnm,scorer=llm].mean_abs_diff|.2f}} on a [−1, 1] scale (Figure 3). The fine-tuned multilingual model is no more consistent
(ρ {{rq3.rows[bank=bi,scorer=ft].spearman|.2f}} and {{rq3.rows[bank=bnm,scorer=ft].spearman|.2f}}). The dictionary is English-only and therefore not applicable;
PBoC has {{rq3.rows[bank=pboc,scorer=llm].n_pairs|d}} parallel pairs and is exploratory.

![Figure 3. RQ3: LLM tone of the native-language version against the English version of the same statement.](results/figures/fig_rq3_crosslingual.png)

# 6. Contamination and reliability

## 6.1 Stability (H4a: refuted)

Across the five registered prompt paraphrases, document scores reach Krippendorff's α {{rq4.rq4a.docs.prompts.alpha|.2f}}
and ICC(2,1) {{rq4.rq4a.docs.prompts.icc_2_1|.2f}} on {{rq4.rq4a.docs.prompts.n_units}} documents, short of the pre-registered
0.667 and 0.75; on {{rq4.rq4a.sentences.prompts.n_units}} sentences α is {{rq4.rq4a.sentences.prompts.alpha|.2f}}. Temperature
matters much less (α {{rq4.rq4a.docs.temperature.alpha|.2f}} for documents, {{rq4.rq4a.sentences.temperature.alpha|.2f}} for
sentences, at 0 vs 0.7). Swapping the model tag for `qwen2.5:3b` changes scores most: α {{rq4.rq4a.docs.model_tag.alpha|.2f}}
for documents and {{rq4.rq4a.sentences.model_tag.alpha|.2f}} for sentences, i.e. no better than chance agreement at sentence
level. Aggregating sentence scores into a document score gives indices that correlate with the direct document
score at ρ {{rq4.rq4a.aggregation.spearman.agg_max_abs~document|.2f}}–{{rq4.rq4a.aggregation.spearman.agg_decision_weighted~document|.2f}},
so not every pair of strategies clears 0.70. A tone index from a small local model is therefore partly a property of
the prompt and the model version, which any user of such scores should report.

## 6.2 Agreement with human labels (H4b: refuted)

On the {{rq4.rq4b.n}}-sentence FOMC test split the LLM's three-class macro-F1 is {{rq4.rq4b.rows[scorer=llm].macro_f1|.2f}}
[{{rq4.rq4b.rows[scorer=llm].f1_lo|.2f}}, {{rq4.rq4b.rows[scorer=llm].f1_hi|.2f}}]. It exceeds the dictionary by {{rq4.rq4b.rows[scorer=llm].df1_vs_ref|.2f}} (CI
[{{rq4.rq4b.rows[scorer=llm].df1_lo|.2f}}, {{rq4.rq4b.rows[scorer=llm].df1_hi|.2f}}]) but misses the pre-registered floor of 0.50, so H4b is refuted. The fine-tuned
XLM-R, trained only on the LLM's labels for corpus sentences (no FOMC data), reaches {{rq4.rq4b.rows[scorer=ft].macro_f1|.2f}}. Our dictionary
scores {{rq4.rq4b.rows[scorer=dict].macro_f1|.2f}}, well below the ≈ 0.50 reported for a rule-based baseline by @shah2023trillion; the two
rule sets differ, and ours returns neutral whenever hawkish and dovish matches balance or none appear, which is the
case for almost every FOMC test sentence. The LLM also over-predicts the neutral class relative to the human labels.
FOMC-RoBERTa, the in-distribution reference (≈ 0.72), could not be run (gated model).

![Figure 4. RQ4b: macro-F1 on the FOMC test split, with published reference values (dotted).](results/figures/fig_rq4b_fomc_f1.png)

## 6.3 Contamination (H4c)

No RQ1 or RQ2 finding is robust. Pooled across powered banks, the LLM's log-loss gain over the dictionary is
{{rq1.rq4c.pooled_dll_llm_vs_dict.dll|.3f}} [{{rq1.rq4c.pooled_dll_llm_vs_dict.lo|.3f}}, {{rq1.rq4c.pooled_dll_llm_vs_dict.hi|.3f}}]
on original text and {{rq1.rq4c.masked_pooled_dll_vs_dict.dll|.3f}} [{{rq1.rq4c.masked_pooled_dll_vs_dict.lo|.3f}},
{{rq1.rq4c.masked_pooled_dll_vs_dict.hi|.3f}}] on masked text: there is no effect to preserve, so the masked check
cannot pass. The post-cutoff window (after {{rq1.rq4c.cutoff}}) holds {{rq1.rq4c.post_cutoff.n}} decisions and
{{rq2.rq4c.post_cutoff_pooled_fx_beta.n}} FX events; its estimates overlap the full-sample intervals but are too wide
to be informative. Masking leaves the ECB point estimate nearly unchanged, which is consistent with, but does not
prove, the absence of outcome memorisation for that series.

# 7. Transfer to Southeast Asia

**H5 is untestable as pre-registered.** It requires FOMC-RoBERTa, which could not be run, and the BI-en and BNM-en
silver subsets have {{rq5.dict.bi_en_n}} sentences each, under the minimum of 50. Descriptively, on the 60 MAS silver
sentences the dictionary's macro-F1 is {{rq5.rows[group=mas-en,scorer=dict].silver_macro_f1|.2f}} against {{rq5.rows[group=mas-en,scorer=dict].fomc_macro_f1|.2f}} on
FOMC sentences, so it does not lose performance on MAS (drop {{rq5.rows[group=mas-en,scorer=dict].drop|.2f}}). The LLM and the fine-tuned model
score higher on silver than on FOMC labels ({{rq5.rows[group=mas-en,scorer=llm].silver_macro_f1|.2f}} and {{rq5.rows[group=mas-en,scorer=ft].silver_macro_f1|.2f}} on
MAS), but the silver labels come from the same model family, so these numbers measure self-agreement rather than
accuracy and support no claim. The two silver passes agree on {{rq5.label_agreement.pass_a_eq_b|pct}} of sentences.
In a multilingual sentence-embedding space, MAS sentences are the farthest from Fed sentences (mean cosine distance
{{rq5.distance[group=mas-en].mean_cosine_distance_to_fed|.2f}} vs {{rq5.distance[group=ecb-en].mean_cosine_distance_to_fed|.2f}}
for the ECB), consistent with MAS's exchange-rate framing.

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
  on local hardware, not to frontier models. The headline run used a desktop GPU; a laptop gives the same model
  and settings, more slowly.

# 9. Reproducibility statement

All code is Apache-2.0 at <https://github.com/thanatchon36/cbtone>. `make reproduce` rebuilds every table
and figure from the committed corpus snapshot (scores are cached by content hash, so a re-run repeats only the few LLM
calls that failed the first time; the fine-tuned model is retrained, which on Apple MPS is not bit-for-bit
deterministic; `ANOMALIES.md` A13). The pre-registration is the git tag `prereg-v1`; every later deviation is listed in
`docs/DECISIONS.md` (D17–D20) and every data anomaly in `docs/ANOMALIES.md`. LLM scores were computed on a desktop RTX 4070 Ti
(D20); the fine-tuned model was trained on an Apple M4 laptop (16 GB, MPS) in 6 minutes (`results/hardware.json`,
`results/ft_train_report.json`); per-stage wall time is in `results/timing.json`.

# 10. Conclusion

A small LLM run on a consumer desktop GPU (or, more slowly, a laptop) produces tone indices that look plausible over time (Figure 5) and agree
with human FOMC labels better than a simple dictionary, yet on every pre-registered test of *policy signal* (next-decision
prediction, market reaction, cross-lingual consistency, prompt stability) the evidence is negative or underpowered.
Three lessons follow for practitioners. First, persistence is a strong baseline for decision prediction, and gains from
text are small and bank-specific. Second, LLM tone depends on the prompt and the model version, so a single-prompt
index should not be treated as a measurement without a stability check. Third, for Southeast Asian banks the binding
constraint is sample size: BI's text begins in 2016, BNM rarely moves, and MAS met only twice a year until 2024, so
BNM and MAS are underpowered for decision prediction and the silver evaluation sets are small. The library, the masked and post-cutoff checks, and every number in this paper
can be regenerated with `make reproduce`.

![Figure 5. LLM tone index of each bank's primary decision document.](results/figures/fig_tone_timeseries.png)

# References
