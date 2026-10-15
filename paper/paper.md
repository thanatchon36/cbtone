---
title: "Reading the Room: Do Local-LLM Tone Scores of Central-Bank Communication Carry Policy Signal? Pre-registered Evidence from Seven Central Banks in Three Languages"
author: "Thanatchon Chongmankhong"
date: "October 2026"
bibliography: docs/literature/refs.bib
csl: paper/csl/ieee.csl
link-citations: true
numbersections: true
section-numbering: "1.1"
mainfont: "Libertinus Serif"
fontsize: 10pt
papersize: a4
margin:
  x: 2.2cm
  y: 2.4cm
abstract: |
  Hawkish/dovish tone indices distilled from central-bank text are now routinely produced with large language
  models (LLMs), yet it is rarely asked whether such indices carry information that a trivial forecast does not,
  whether they survive a change of prompt, or whether the model has already seen the outcomes it is asked to
  anticipate. We address these questions with a pre-registered study of seven central banks (the Federal Reserve,
  the European Central Bank, the Bank of England, the Reserve Bank of Australia, the Monetary Authority of
  Singapore, Bank Indonesia and Bank Negara Malaysia) in English, Indonesian and Malay, scored by a four-billion-parameter
  model (`qwen3:4b`) running on consumer hardware. Hypotheses, thresholds, samples and multiple-testing
  families were frozen in a public pre-registration before any scorer read the full corpus, and every LLM result
  is re-estimated on entity-masked text and on a post-training-cutoff window. **Every testable hypothesis is
  refuted at its pre-registered threshold.** Relative to a persistence forecast, LLM tone improves the
  out-of-sample log-loss of the next policy decision at none of the {{rq1.verdict.n_powered}} adequately powered
  banks (the nearest miss is the ECB: ΔLL {{rq1.rows[bank=ecb,scorer=llm].dll_vs_pers|.3f}}, Holm-adjusted
  *p* = {{rq1.rows[bank=ecb,scorer=llm].p_vs_pers_holm|.2f}}). The tone surprise explains the announcement-window
  market move beyond a non-announcement placebo in {{rq2.verdict.h2a.n_success}} of {{rq2.verdict.h2a.n_powered}}
  bank–market cells and never beats a cited dictionary after correction. Native-language and English versions of
  the same statement agree only moderately in intensity (Spearman ρ = {{rq3.rows[bank=bi,scorer=llm].spearman|.2f}}
  for Indonesian, {{rq3.rows[bank=bnm,scorer=llm].spearman|.2f}} for Malay, against a pre-registered 0.70), while
  rarely disagreeing in direction. Scores move materially with the prompt wording (Krippendorff's α =
  {{rq4.rq4a.docs.prompts.alpha|.2f}} across five paraphrases at document level) and still more with the model
  version. On the human-labelled FOMC test split the LLM reaches a macro-F1 of
  {{rq4.rq4b.rows[scorer=llm].macro_f1|.2f}}, above the dictionary ({{rq4.rq4b.rows[scorer=dict].macro_f1|.2f}})
  but below the pre-registered floor of 0.50, while our replication of the supervised FOMC-RoBERTa reaches
  {{rq4.rq4b.rows[scorer=fomc_roberta].macro_f1|.2f}}. That better-calibrated instrument fares no better on the
  policy-signal tests: it improves on persistence at none of the {{rq1.transformer.n_powered|d}} powered
  banks, and its announcement-window R² is indistinguishable from the LLM's in every powered cell, which
  places the negative result in the signal rather than in the instrument. We release the corpus pipeline, the scorers and the evaluation
  harness as the open-source Python package `cbtone`, together with every number in this paper.
header-includes:
  - |
    ```{=typst}
    #set par(justify: true)
    #show heading.where(level: 1): set text(size: 12pt)
    #show heading.where(level: 2): set text(size: 10.5pt)
    #show heading: set block(above: 1.4em, below: 0.7em)
    #show figure.caption: set text(size: 8.5pt)
    #show figure.caption: it => block(width: 100%, align(left, it))
    #show figure.where(kind: table): set text(size: 8pt)
    #show figure.where(kind: image): set figure(placement: auto)
    #show table.cell.where(y: 0): set text(weight: "semibold")
    #set table(
      inset: (x: 5pt, y: 3.5pt),
      stroke: (x, y) => if y == 0 { (bottom: 0.5pt + black) } else { none },
    )
    #show table: it => block(stroke: (top: 0.8pt + black, bottom: 0.8pt + black), inset: 0pt, it)
    #show link: set text(fill: rgb("#1f4e8c"))
    ```
---

**Keywords:** central-bank communication; monetary policy; large language models; text as data;
pre-registration; training-data contamination; Southeast Asia.
**JEL:** E52, E58, C45, C55, G14.

> **Disclaimer.** This is an independent open-source project. It uses only documents published on
> central banks' public websites (or public mirrors of them), represents the views of no institution,
> and is not investment advice. The author is employed by a central bank; nothing here draws on
> non-public information, and the text makes no comment on any bank's policy choices, only on
> measurable properties of published text and on statistical results. The Bank of Thailand adapter
> is opt-in and excluded from all headline results.

# Introduction

After every policy meeting a central bank publishes a decision statement and, in most cases, minutes
and a press conference. Reducing that text to a scalar, a *tone* running from dovish to hawkish, has
become a standard operation in academic research and in market practice. The first generation of
measures counted words [@lucca2009measuring; @apel2014informative]; the second trained supervised
classifiers on hand-labelled sentences [@shah2023trillion]; the third, now spreading rapidly, simply
asks a large language model (LLM) to read the document and report a stance [@hansen2023fedspeak;
@silva2025text]. The third generation is attractive because it needs no labelled data, no lexicon and
no language-specific engineering, and because models small enough to run on a desktop now read
economic prose fluently. It also raises three questions that the literature, overwhelmingly concerned
with the Federal Reserve and the ECB and almost entirely with English, has not answered together.

The first question is whether the measurement carries *policy signal*: does knowing the tone of
today's statement improve a forecast of the next decision beyond what the last decision already
implies, and does the unexpected component of tone explain the market's reaction on the day? The
second is whether the measurement is *stable*: a tone index is only a measurement if a harmless
rephrasing of the prompt, or a point release of the model, leaves it substantially unchanged. The
third is whether the measurement is *contaminated*: a model whose training data extend to 2025 has
read commentary on the very decisions a historical test asks it to predict, so an apparently
predictive score may be recall rather than reading [@lopezlira2025memorization; @sarkar2024lookahead].

This paper answers all three for seven central banks in three languages, with a design that was fixed
before the data were examined. The headline set comprises the Federal Reserve (Fed), the European
Central Bank (ECB), the Bank of England (BoE), the Reserve Bank of Australia (RBA), the Monetary
Authority of Singapore (MAS), Bank Indonesia (BI) and Bank Negara Malaysia (BNM). Three of the seven
publish parallel native-language and English versions of their statements, which affords a direct test of
cross-lingual consistency that, to our knowledge, has not been attempted for central-bank text. The
scorer at the centre of the study is deliberately modest: `qwen3:4b`, a four-billion-parameter open-weight
model served locally through Ollama, chosen because it is what an analyst at an institution without a cloud
budget, or with a prohibition on sending documents to an external service, can actually run.

We make three contributions. First, we release `cbtone`, an Apache-licensed Python library that fetches
public central-bank communications politely, versions them as a content-hashed corpus, and scores them
with four scorer families (a cited hawkish/dovish dictionary, a finance-tuned transformer, a local LLM and a
small fine-tuned multilingual encoder) behind a single interface, so that the comparisons below can be
repeated or extended to other banks in a few lines of configuration. Second, we report a pre-registered
study (git tag `prereg-v1`) in which the five research questions, their hypotheses and thresholds, the
minimum sample per cell, the multiple-testing families and the placebo designs were frozen before any
scorer read the full corpus; a result that fails its threshold is reported as refuted, not re-specified.
Third, we treat training-data contamination as a first-class threat: every LLM result is re-estimated on
*masked* text, in which bank, committee and instrument names, countries, dates and rate levels are replaced by
placeholders, and on a *post-cutoff* window of documents released after the model's public release date, and a
finding is called robust only if it survives both.

The results are uniformly negative, and we think that is the paper's value. LLM tone does not improve
out-of-sample prediction of the next decision over a persistence baseline at any of the four adequately
powered banks; the tone surprise explains the announcement-window move beyond its placebo in a single
bank–market cell and never beats the dictionary after correction; native-language and English versions of
the same statement correlate only moderately; and five paraphrases of the same prompt produce indices
whose agreement falls short of the pre-registered reliability floor. The negative findings are sharpened
rather than weakened by the contamination protocol, because masking leaves the point estimates almost
unchanged: there is no memorised signal to remove. Nor is the failure one of the instrument: a supervised
encoder replicated from the FOMC literature, which reads human-labelled Fed sentences far more accurately
than the LLM, does no better on the same tests. What the local LLM does do is read individual FOMC
sentences better than a dictionary, which is consistent with the published literature and is precisely the
kind of claim that does not generalise to policy signal without the tests reported here.

The remainder of the paper is organised as follows. Section 2 situates the study in the literature on
tone measurement, LLM annotation and announcement effects. Section 3 describes the corpus, the decision
and market data, and the labels. Section 4 sets out the pre-registered design. Sections 5 to 7 report the
results on policy signal, on reliability and contamination, and on transfer to Southeast Asia. Section 8
discusses the findings, Section 9 the threats to validity, and Section 10 the reproducibility of every
number; Section 11 concludes.

# Related literature

## Measuring the tone of central-bank text

The measurement of central-bank tone has moved from counting words to classifying them, and so far almost
exclusively for the Federal Reserve. Lucca and Trebbi [@lucca2009measuring] and Apel and Blix Grimaldi
[@apel2014informative] count hawkish and dovish terms in FOMC statements and Riksbank minutes respectively;
Loughran and McDonald [@loughran2011liability] show why generic sentiment lexicons mislead on financial
text, and Picault and Renault [@picault2017words] build a field-specific lexicon for the ECB. Tone
dictionaries have also been applied to speeches to study the home bias of European central bankers
[@bennani2017home]. Topic models exploit deliberation transcripts to separate information from forward
guidance [@hansen2016shocking] and to study how transparency changes what committee members say
[@hansen2018transparency], while voice-tone measures extend the lens beyond the written record
[@gorodnichenko2023voice]. Supervised transformers came next: FOMC-RoBERTa, trained on 2,480 hand-labelled
FOMC sentences, reaches a weighted F1 of 0.72 on the held-out split against about 0.50 for a rule-based
baseline and 0.59 for zero-shot ChatGPT-3.5 [@shah2023trillion], and CentralBankRoBERTa classifies economic
sentiment rather than policy stance [@pfeifer2023centralbankroberta]. The Fed is also the only bank with a
public human-labelled hawkish/dovish set, so outside the Fed no scorer has been checked against human
judgement.

## LLMs as annotators, and the contamination problem

Asking an LLM to annotate text works, but how well depends on the setting. LLM annotation can match or beat
crowd workers on cost and agreement for political text [@gilardi2023chatgpt]; zero-shot reading of FOMC
stance by an early GPT model is modest [@hansen2023fedspeak]; and the one study spanning many banks and
languages finds a fine-tuned multilingual encoder far ahead of GPT-4o on stance classification
[@silva2025text]. Models can also be probed for the expectations they hold [@bybee2023surveying] and used to
forecast returns from headlines [@lopezlira2023chatgpt]. Two reliability concerns follow directly. Prompt
format alone can move accuracy by tens of points [@sclar2024quantifying], and a recent application at the
Reserve Bank of Australia stresses that "reasoning" about central-bank text must be made trustworthy before
it is operationalised [@jones2025ornithologist]. Ludwig, Mullainathan and Rambachan
[@ludwig2025llm] give the econometric framing we adopt: an LLM output used as a regressor is a noisy,
possibly non-classical measurement whose error structure must be characterised before downstream
inference is interpreted.

Contamination is both real and measurable. LLMs recall macroeconomic outcomes almost perfectly before their
training cutoff and at near-chance rates after it [@lopezlira2025memorization]; masking entity names changes
GPT-based sentiment signals in-sample [@glasserman2024lookahead]; and formal tests of look-ahead bias in
pretrained models are available [@sarkar2024lookahead]. We found no study that combines entity masking with a
post-cutoff split on central-bank text, which is what our RQ4c does.

## Announcement effects and the Southeast Asian evidence

The event-study template is well established. Kuttner [@kuttner2001monetary] identifies the policy surprise
from federal funds futures; Gürkaynak, Sack and Swanson [@gurkaynak2005actions] separate a target factor
from a "path" factor that captures what the statement says; Bernanke and Kuttner [@bernanke2005explains]
quantify the equity response; and Blinder et al. [@blinder2008central] survey why communication moves
markets. Text-based surprise measures explain much less of daily moves than rate surprises do; changes in
statement wording reach a pseudo-R² of at most 0.12 [@ehrmann2020starting]. We therefore pre-registered small
R² values as the relevant benchmark rather than as a disappointment. A recent Federal Reserve note comparing
LLM and lexicon tone across many banks reports only moderate agreement between the two [@xu2026assessing],
which anticipates our RQ4 results.

Evidence for Southeast Asia is thin. For Malaysia there is a yield-curve event study of rate surprises
[@ho2021effects]; for the region there are transparency surveys [@filardo2008transparency]; and the
emerging-market communication literature more broadly covers Fed spillovers to emerging equity markets
[@hayo2012federal], the link between transparency and market expectations [@neuenkirch2013transparency],
and expectation formation in Brazil [@montes2016communication]. Singapore's exchange-rate-centred regime is
described by Parrado [@parrado2004singapore], but we found no study linking MAS statement text to the
Singapore dollar, and none comparing tone between native-language and English versions of the same
central-bank document.

# Data

## Corpus

Adapters fetch each bank's public pages under its robots.txt, with a rate limit of at least two seconds per
host and a descriptive User-Agent, caching every response with its SHA-256 digest. MAS serves a bot
interstitial to automated clients and pbc.gov.cn disallows crawlers; with the author's approval both are read
from Internet Archive copies and never from the banks' own sites. The snapshot used here (`{{corpus_version}}`)
holds 2,935 documents. Each bank's primary decision series was fixed in the pre-registration: FOMC statements;
ECB monetary-policy decision press releases; BoE Monetary Policy Committee minutes (the Bank's 2000–2006
decision releases are a single sentence and carry no tone); RBA statements from December 2007 (earlier
releases exist only when the cash rate changed); MAS Monetary Policy Statements; and BI and BNM statements
(English primary, with Indonesian and Malay twins used for RQ3). Text is committed to the repository only
where the source's terms permit redistribution (Fed, ECB decision releases, RBA); for the other banks the
repository holds URLs and hashes, and `make fetch` rebuilds the text locally.

## Policy decisions

Rate decisions are taken from the BIS central-bank policy-rate series and matched to meeting dates from
the corpus; a meeting at which the rate is unchanged is a hold. MAS sets a path for the trade-weighted
exchange rate rather than an interest rate, so its decisions (tighten, maintain, ease) are taken from the
Authority's own published decision table; a rule-based extractor exists for statements not yet in that
table, but its accuracy is development accuracy only and it is used for two 2026 statements that are
excluded from every test.

## Market data

Daily exchange-rate closes come from Yahoo Finance, with bad ticks removed by a rule fixed before any test
was run, and two-year government-bond yields from a free official daily source where one exists (United
States, euro area, United Kingdom, Australia). Moves are measured between the closes of *t* − 1 and *t* + 1
around the release; a document without a published release time is timed at 00:00 local time on its release
date, so that the window always contains the event. Exchange rates for Singapore, Indonesia and Malaysia
are USD crosses, signed so that a positive move is a domestic appreciation.

## Human and silver labels

Human labels exist only for the Fed: the hawkish/dovish test split of Shah, Paturi and Chava
[@shah2023trillion], which is used for evaluation only under its non-commercial licence and never for
training. For Southeast Asia, 200 sentences (MAS 60; BI 35 English and 35 Indonesian; BNM 35 English and 35
Malay) carry *silver* labels produced by two LLM passes with different prompts and a tie-break; they are
reported as silver throughout and are never treated as ground truth. Table 1 summarises the sample behind
every test.

| Bank | Primary document | Decisions | OOS | Hikes | Cuts | Powered (RQ1) | FX events | 2Y events |
|:-----|:-----------------|--------:|------:|------:|------:|:------:|------:|------:|
| Fed | FOMC statement | {{rq1.rows[bank=fed,scorer=llm].n_decisions|d}} | {{rq1.rows[bank=fed,scorer=llm].n_oos|d}} | {{rq1.rows[bank=fed,scorer=llm].n_oos_hike|d}} | {{rq1.rows[bank=fed,scorer=llm].n_oos_cut|d}} | {{rq1.rows[bank=fed,scorer=llm].powered|yn}} | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].n_events|d}} |
| ECB | Decision press release | {{rq1.rows[bank=ecb,scorer=llm].n_decisions|d}} | {{rq1.rows[bank=ecb,scorer=llm].n_oos|d}} | {{rq1.rows[bank=ecb,scorer=llm].n_oos_hike|d}} | {{rq1.rows[bank=ecb,scorer=llm].n_oos_cut|d}} | {{rq1.rows[bank=ecb,scorer=llm].powered|yn}} | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].n_events|d}} |
| BoE | MPC minutes | {{rq1.rows[bank=boe,scorer=llm].n_decisions|d}} | {{rq1.rows[bank=boe,scorer=llm].n_oos|d}} | {{rq1.rows[bank=boe,scorer=llm].n_oos_hike|d}} | {{rq1.rows[bank=boe,scorer=llm].n_oos_cut|d}} | {{rq1.rows[bank=boe,scorer=llm].powered|yn}} | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].n_events|d}} |
| RBA | Decision statement | {{rq1.rows[bank=rba,scorer=llm].n_decisions|d}} | {{rq1.rows[bank=rba,scorer=llm].n_oos|d}} | {{rq1.rows[bank=rba,scorer=llm].n_oos_hike|d}} | {{rq1.rows[bank=rba,scorer=llm].n_oos_cut|d}} | {{rq1.rows[bank=rba,scorer=llm].powered|yn}} | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].n_events|d}} |
| MAS | Monetary Policy Statement | {{rq1.rows[bank=mas,scorer=llm].n_decisions|d}} | {{rq1.rows[bank=mas,scorer=llm].n_oos|d}} | {{rq1.rows[bank=mas,scorer=llm].n_oos_hike|d}} | {{rq1.rows[bank=mas,scorer=llm].n_oos_cut|d}} | {{rq1.rows[bank=mas,scorer=llm].powered|yn}} | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].n_events|d}} | — |
| BI | Decision statement | {{rq1.rows[bank=bi,scorer=llm].n_decisions|d}} | {{rq1.rows[bank=bi,scorer=llm].n_oos|d}} | {{rq1.rows[bank=bi,scorer=llm].n_oos_hike|d}} | {{rq1.rows[bank=bi,scorer=llm].n_oos_cut|d}} | {{rq1.rows[bank=bi,scorer=llm].powered|yn}} | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].n_events|d}} | — |
| BNM | Decision statement | {{rq1.rows[bank=bnm,scorer=llm].n_decisions|d}} | {{rq1.rows[bank=bnm,scorer=llm].n_oos|d}} | {{rq1.rows[bank=bnm,scorer=llm].n_oos_hike|d}} | {{rq1.rows[bank=bnm,scorer=llm].n_oos_cut|d}} | {{rq1.rows[bank=bnm,scorer=llm].powered|yn}} | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].n_events|d}} | — |

: Sample behind each test. Decisions are meetings with a matched policy decision; OOS, hikes and cuts
are the out-of-sample decisions predicted by the expanding-window model in RQ1 and the hikes and cuts
among them (for MAS, tightenings and easings of the exchange-rate path). A bank is powered for RQ1 when it has at least 40 OOS
decisions with at least 8 hikes and 8 cuts. FX and two-year-yield events are announcements with a usable
market window; "—" marks series for which no free daily source exists.

# Empirical design

## Scorers

Every scorer returns a probability vector over {hawkish, dovish, neutral} and an index
$\tau = p_{\text{hawkish}} - p_{\text{dovish}} \in [-1, 1]$, computed on the same input: the decision,
forward-guidance, outlook and risk paragraphs of a document selected by a rule-based tagger and capped at
6,000 characters. The *dictionary* (`dict-v1`) applies a 167-term lexicon assembled from the cited
hawkish/dovish word lists with negation handling; it reads English only. The *LLM* is `qwen3:4b` run
locally through Ollama at temperature 0 with a registered prompt (P1) and schema-constrained JSON output;
every call is cached by content hash, so a re-run repeats no inference. The *fine-tuned* scorer is XLM-R
base trained for at most 30 minutes on the LLM's own sentence labels for corpus sentences, never on the
FOMC data, so that it measures how much of the LLM's reading a small multilingual encoder can absorb.
*FOMC-RoBERTa*, the in-distribution reference, is our replication of the model of Shah, Paturi and Chava
[@shah2023trillion]. The authors' checkpoint is gated and access was not granted. We therefore fine-tuned
RoBERTa-large on the train split of their data with their recipe: a 20 % validation split, learning rate
10⁻⁵ and early stopping on validation macro-F1. Three seeds were trained and the seed with the best
validation score was kept, so the test split played no part in model selection. The weights are released
at <https://huggingface.co/thanatchon36/cbtone-fomc-roberta-repl> under CC-BY-NC-4.0, the licence of the
training data, as a replication that carries none of the authors' weights; readers with access to the
original should prefer it. The replication reads English only and enters every analysis in which the pre-registration names the transformer scorer: the FOMC test split
(H4b), the Southeast Asian silver sets (H5) and, as a descriptive comparison outside the Holm families,
the next-decision and announcement-window analyses (RQ1, RQ2).

## Pre-registration and hypotheses

The pre-registration (`docs/RESEARCH_QUESTIONS.md` at tag `prereg-v1`) fixed the five research questions,
the hypotheses in Table 2, the sample minimum for each (bank, question) cell, the Holm families and the
placebo designs. Deviations made after the tag are logged with their rationale in `docs/DECISIONS.md`
(D17–D21) and concern compute allocation, document selection and the replacement of the gated reference
model by a replication (D21), not thresholds or tests.

| Hypothesis | Statement | Threshold | Verdict |
|:------|:----------------------|:----------------|:--------|
| H1 | LLM tone improves out-of-sample next-decision log-loss over persistence at a majority of powered banks | ΔLL > 0, Holm-adjusted *p* < 0.05, beats both placebos | {{rq1.verdict.verdict}} ({{rq1.verdict.n_success}} of {{rq1.verdict.n_powered}}) |
| H2a | The LLM tone surprise explains the announcement-window move beyond a non-announcement placebo | R² above the placebo 95th percentile, Holm-adjusted *p*(β) < 0.05 | {{rq2.verdict.h2a.verdict}} ({{rq2.verdict.h2a.n_success}} of {{rq2.verdict.h2a.n_powered}}) |
| H2b | The LLM's R² exceeds the dictionary's | ΔR² > 0, Holm-adjusted *p* < 0.05 | {{rq2.verdict.h2b.verdict}} ({{rq2.verdict.h2b.n_success}} of {{rq2.verdict.h2b.n_powered}}) |
| H3 | Native-language and English scores of the same statement agree | Spearman ρ ≥ 0.70 and stance flips ≤ 10 % | {{rq3.verdict}} |
| H4a | Scores are stable across prompt paraphrases, temperatures, model tags and aggregation | α ≥ 0.667, ICC(2,1) ≥ 0.75, all aggregation ρ ≥ 0.70 | prompts pass: {{rq4.rq4a.docs.h4a_prompts_pass|yn}} |
| H4b | The LLM agrees with human FOMC labels better than the dictionary | macro-F1 ≥ 0.50 and above the dictionary | {{rq4.rq4b.verdict}} |
| H4c | Any H1/H2 finding survives entity masking and a post-cutoff split | both re-estimates keep sign and significance | robust finding: {{rq1.rq4c.robust|yn}} |
| H5 | Fed-calibrated scorers transfer poorly to MAS | silver macro-F1 drop ≥ 0.10 vs FOMC, with FOMC-RoBERTa as the reference | {{rq5.verdict}} |

: Pre-registered hypotheses, their thresholds and the verdicts reported in Sections 5–7. Every verdict is
read from `results/summary.json`.

## Next-decision prediction (RQ1)

For each bank $b$ with decisions $y_t \in \{\text{cut}, \text{hold}, \text{hike}\}$ at meetings
$t = 1, \dots, T_b$, an ordered-logit model
$$\Pr(y_{t+1} \le k \mid x_t) = \Lambda(\kappa_k - x_t'\beta), \qquad x_t = (\tau_t,\; \Delta\tau_t,\; d_t),$$
is refitted at every decision on an expanding window (initial 40 % of the sample, at least 30 decisions) and
used to predict the next decision, where $\tau_t$ is the tone of the document released at $t$,
$\Delta\tau_t$ its change from the previous document and $d_t$ the direction of the last decision. The
baseline is persistence, a smoothed estimate of $\Pr(y_{t+1} \mid y_t)$ from the same window. Performance is
the multiclass log-loss per decision, and the quantity of interest is the gain
$$\Delta\mathrm{LL}_b = \mathrm{LL}_b^{\text{reference}} - \mathrm{LL}_b^{\text{model}},$$
positive when the tone model is better. Its sampling distribution is obtained by a moving-block bootstrap
over out-of-sample decisions (block length 4); Holm's correction is applied across the adequately powered
banks; and a success additionally requires the real gain to exceed the 95th percentile of two placebo
distributions, obtained by shuffling the dates of the tone series and by permuting the decision labels
({{rq1.perms|,}} permutations each). The same procedure is run with the dictionary as the reference, so that
the LLM is compared both with a trivial forecast and with a simple text measure.

## Announcement-window regressions (RQ2)

The tone surprise $s_t = \tau_t - \hat{\tau}_{t \mid t-1}$ is the residual from an AR(1) fitted to the tone
series of that bank using documents released before $t$ only. For each bank and market series the
two-day move $r_t$ around the release is regressed on the surprise,
$$r_t = \alpha + \beta s_t + \varepsilon_t,$$
with Newey–West (HAC) standard errors. H2a requires the R² to exceed the 95th percentile of the same
regression run on non-announcement days and a Holm-adjusted one-sided test on $\beta$ in the hypothesised
direction (a hawkish surprise appreciates the currency and raises the two-year yield); H2b compares the
LLM's R² with the dictionary's by paired block bootstrap. Cells with fewer than 30 events are reported but
excluded from the Holm family.

## Cross-lingual consistency (RQ3)

For BI and BNM every statement is published in the national language and in English. The LLM scores both
versions independently, and consistency is measured by the Spearman correlation of the two indices over
parallel pairs and by the *stance-flip rate*, the share of pairs whose argmax labels are hawkish in one
language and dovish in the other. H3 requires ρ ≥ 0.70 and a flip rate of at most 10 %. PBoC, which
publishes Chinese and English, is exploratory because it has too few parallel pairs.

## Reliability (RQ4a, RQ4b)

Stability is measured with Krippendorff's α (interval) and ICC(2,1) across five registered paraphrases of
the prompt, two temperatures (0 and 0.7), two model tags (`qwen3:4b` and `qwen2.5:3b`) and three
strategies for aggregating sentence scores into a document score (mean, decision-weighted, maximum absolute
index), each compared with the direct document score, on {{rq4.rq4a.docs.prompts.n_units}} documents and
{{rq4.rq4a.sentences.prompts.n_units|,}} sentences. Agreement with human labels is the three-class macro-F1 on
the {{rq4.rq4b.n}}-sentence FOMC test split, with a bootstrap interval over sentences and a paired
comparison with the dictionary.

## Contamination (RQ4c)

Every LLM score is recomputed on *masked* text, in which a deterministic rule replaces the names of banks,
committees, instruments and countries, all dates and all rate levels with typed placeholders, and every RQ1
and RQ2 estimate is recomputed on the *post-cutoff* window of documents released after the model's public
release date ({{rq1.rq4c.cutoff}}). A finding from RQ1 or RQ2 is *robust* only if it keeps its sign and
significance under both re-estimations. Because the model cannot have read commentary on post-cutoff
decisions, and because masking removes the handles through which a memorised outcome could be retrieved,
a signal that survives both is unlikely to be recall.

## Transfer to Southeast Asia (RQ5)

Each Fed-calibrated scorer's macro-F1 on the FOMC test split is compared with its macro-F1 on the silver
sets per bank and language; H5 predicts a drop of at least 0.10 for MAS, whose exchange-rate framing is
furthest from the Fed's. The test was pre-registered with FOMC-RoBERTa as the reference scorer and a minimum
of 50 sentences per cell. As a descriptive complement, we report the mean cosine distance between each
bank's sentences and Fed sentences in a multilingual sentence-embedding space
(`{{rq5.embedding_model}}`).

## Power, multiplicity and compute

Each (bank, question) cell has a pre-set minimum sample; underpowered cells are reported with their
estimates but excluded from the Holm families and from majority counts, and a majority verdict requires at
least three powered banks. All LLM scores come from one backend, the same `qwen3:4b` weights (digest
`359d7dd4`) served by Ollama on a desktop RTX 4070 Ti, on which the full pre-registered workload fits the
two-hour LLM budget without invoking the pre-registered compute ladder: scoring the primary documents took
{{timing[stage=score:llm].seconds|min}} minutes, the masked re-scoring {{timing[stage=score:llm:masked].seconds|min}}
minutes and the stability perturbations {{timing[stage=llm:rq4a].seconds|min}} minutes. The fine-tuned encoder
trained in {{timing[stage=ft:train].seconds|min}} minutes on an Apple M4 laptop. On that laptop the LLM
processes about 220 prompt tokens per second, roughly 3.5 seconds per document at a 3,000-character cap, so a
laptop-only replication requires the ladder described in Section 10.

# Results: policy signal

## The tone series

Figure 1 plots the LLM index of each bank's primary document over the sample. The series are visibly
plausible: the 2022–2023 tightening cycle appears as a sustained hawkish plateau at every bank that
publishes a full statement, the 2008–2009 and 2020 easings as dovish troughs, and the exchange-rate-framed
MAS statements as a smoother and more muted series. Two features matter for what follows. First, the ECB's
decision press releases before 2016 are short and formulaic, so the index alternates between neutral and
the extremes rather than evolving gradually; second, for BI the series begins only in 2016, because the
bank's own index lists nothing older. Plausibility of this kind is the weakest test a tone index can pass,
and the sections that follow ask whether anything more is true.

![LLM tone index of each bank's primary decision document, `qwen3:4b` at temperature 0 with the registered prompt. Dotted line: the model's public release date, after which no document can have been in its training data.](results/figures/fig_tone_timeseries.svg){width=100%}

## Does tone predict the next decision? (RQ1)

**H1 is refuted.** {{rq1.verdict.n_powered}} banks meet the pre-registered power rule (Fed, ECB, RBA and BI).
The LLM succeeds at none of them (Table 3, Figure 2).

| Bank | Scorer | OOS *n* | ΔLL vs persistence [95 % CI] | *p* | ΔLL vs dictionary [95 % CI] | Beats both placebos |
|:----|:-----|----:|------------:|-----:|------------:|:------:|
| Fed | LLM | {{rq1.rows[bank=fed,scorer=llm].n_oos|d}} | {{rq1.rows[bank=fed,scorer=llm].dll_vs_pers|.3f}} [{{rq1.rows[bank=fed,scorer=llm].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=fed,scorer=llm].dll_vs_pers_hi|.3f}}] | {{rq1.rows[bank=fed,scorer=llm].p_vs_pers_holm|.2f}} | {{rq1.rows[bank=fed,scorer=llm].dll_vs_dict|.3f}} [{{rq1.rows[bank=fed,scorer=llm].dll_vs_dict_lo|.3f}}, {{rq1.rows[bank=fed,scorer=llm].dll_vs_dict_hi|.3f}}] | {{rq1.rows[bank=fed,scorer=llm].passes_placebo|yn}} |
| ECB | LLM | {{rq1.rows[bank=ecb,scorer=llm].n_oos|d}} | {{rq1.rows[bank=ecb,scorer=llm].dll_vs_pers|.3f}} [{{rq1.rows[bank=ecb,scorer=llm].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=ecb,scorer=llm].dll_vs_pers_hi|.3f}}] | {{rq1.rows[bank=ecb,scorer=llm].p_vs_pers_holm|.2f}} | {{rq1.rows[bank=ecb,scorer=llm].dll_vs_dict|.3f}} [{{rq1.rows[bank=ecb,scorer=llm].dll_vs_dict_lo|.3f}}, {{rq1.rows[bank=ecb,scorer=llm].dll_vs_dict_hi|.3f}}] | {{rq1.rows[bank=ecb,scorer=llm].passes_placebo|yn}} |
| RBA | LLM | {{rq1.rows[bank=rba,scorer=llm].n_oos|d}} | {{rq1.rows[bank=rba,scorer=llm].dll_vs_pers|.3f}} [{{rq1.rows[bank=rba,scorer=llm].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=rba,scorer=llm].dll_vs_pers_hi|.3f}}] | {{rq1.rows[bank=rba,scorer=llm].p_vs_pers_holm|.2f}} | {{rq1.rows[bank=rba,scorer=llm].dll_vs_dict|.3f}} [{{rq1.rows[bank=rba,scorer=llm].dll_vs_dict_lo|.3f}}, {{rq1.rows[bank=rba,scorer=llm].dll_vs_dict_hi|.3f}}] | {{rq1.rows[bank=rba,scorer=llm].passes_placebo|yn}} |
| BI | LLM | {{rq1.rows[bank=bi,scorer=llm].n_oos|d}} | {{rq1.rows[bank=bi,scorer=llm].dll_vs_pers|.3f}} [{{rq1.rows[bank=bi,scorer=llm].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=bi,scorer=llm].dll_vs_pers_hi|.3f}}] | {{rq1.rows[bank=bi,scorer=llm].p_vs_pers_holm|.2f}} | {{rq1.rows[bank=bi,scorer=llm].dll_vs_dict|.3f}} [{{rq1.rows[bank=bi,scorer=llm].dll_vs_dict_lo|.3f}}, {{rq1.rows[bank=bi,scorer=llm].dll_vs_dict_hi|.3f}}] | {{rq1.rows[bank=bi,scorer=llm].passes_placebo|yn}} |
| Fed | FOMC-RoBERTa | {{rq1.rows[bank=fed,scorer=fomc_roberta].n_oos|d}} | {{rq1.rows[bank=fed,scorer=fomc_roberta].dll_vs_pers|.3f}} [{{rq1.rows[bank=fed,scorer=fomc_roberta].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=fed,scorer=fomc_roberta].dll_vs_pers_hi|.3f}}] | {{rq1.rows[bank=fed,scorer=fomc_roberta].p_vs_pers|.2f}} | {{rq1.rows[bank=fed,scorer=fomc_roberta].dll_vs_dict|.3f}} [{{rq1.rows[bank=fed,scorer=fomc_roberta].dll_vs_dict_lo|.3f}}, {{rq1.rows[bank=fed,scorer=fomc_roberta].dll_vs_dict_hi|.3f}}] | — |
| ECB | FOMC-RoBERTa | {{rq1.rows[bank=ecb,scorer=fomc_roberta].n_oos|d}} | {{rq1.rows[bank=ecb,scorer=fomc_roberta].dll_vs_pers|.3f}} [{{rq1.rows[bank=ecb,scorer=fomc_roberta].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=ecb,scorer=fomc_roberta].dll_vs_pers_hi|.3f}}] | {{rq1.rows[bank=ecb,scorer=fomc_roberta].p_vs_pers|.2f}} | {{rq1.rows[bank=ecb,scorer=fomc_roberta].dll_vs_dict|.3f}} [{{rq1.rows[bank=ecb,scorer=fomc_roberta].dll_vs_dict_lo|.3f}}, {{rq1.rows[bank=ecb,scorer=fomc_roberta].dll_vs_dict_hi|.3f}}] | — |
| RBA | FOMC-RoBERTa | {{rq1.rows[bank=rba,scorer=fomc_roberta].n_oos|d}} | {{rq1.rows[bank=rba,scorer=fomc_roberta].dll_vs_pers|.3f}} [{{rq1.rows[bank=rba,scorer=fomc_roberta].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=rba,scorer=fomc_roberta].dll_vs_pers_hi|.3f}}] | {{rq1.rows[bank=rba,scorer=fomc_roberta].p_vs_pers|.2f}} | {{rq1.rows[bank=rba,scorer=fomc_roberta].dll_vs_dict|.3f}} [{{rq1.rows[bank=rba,scorer=fomc_roberta].dll_vs_dict_lo|.3f}}, {{rq1.rows[bank=rba,scorer=fomc_roberta].dll_vs_dict_hi|.3f}}] | — |
| BI | FOMC-RoBERTa | {{rq1.rows[bank=bi,scorer=fomc_roberta].n_oos|d}} | {{rq1.rows[bank=bi,scorer=fomc_roberta].dll_vs_pers|.3f}} [{{rq1.rows[bank=bi,scorer=fomc_roberta].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=bi,scorer=fomc_roberta].dll_vs_pers_hi|.3f}}] | {{rq1.rows[bank=bi,scorer=fomc_roberta].p_vs_pers|.2f}} | {{rq1.rows[bank=bi,scorer=fomc_roberta].dll_vs_dict|.3f}} [{{rq1.rows[bank=bi,scorer=fomc_roberta].dll_vs_dict_lo|.3f}}, {{rq1.rows[bank=bi,scorer=fomc_roberta].dll_vs_dict_hi|.3f}}] | — |

: Next-decision prediction at the adequately powered banks. ΔLL = LL(reference) − LL(model) in
multiclass log-loss per decision; positive favours the scorer. Intervals from a moving-block bootstrap. LLM
rows: *p* is Holm-adjusted across the four banks and the last column reports the pre-registered refuting
experiment. FOMC-RoBERTa (replication) rows are the pre-registered descriptive comparison: *p* is unadjusted
and the placebos were not run.

The ECB is the only bank at which the LLM's gain over persistence has a bootstrap interval that excludes
zero and exceeds both placebo distributions (95th percentiles
{{rq1.rows[bank=ecb,scorer=llm].placebo_tone_p95|.3f}} for shuffled tone and
{{rq1.rows[bank=ecb,scorer=llm].placebo_labels_p95|.3f}} for permuted labels); the unadjusted *p*-value is
{{rq1.rows[bank=ecb,scorer=llm].p_vs_pers|.3f}} and the Holm-adjusted value
{{rq1.rows[bank=ecb,scorer=llm].p_vs_pers_holm|.2f}}, so the finding does not survive the pre-registered
correction. The masked LLM gives an almost identical ECB estimate
({{rq1.rows[bank=ecb,scorer=llm_masked].dll_vs_pers|.3f}}
[{{rq1.rows[bank=ecb,scorer=llm_masked].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=ecb,scorer=llm_masked].dll_vs_pers_hi|.3f}}]),
which is consistent with the gain being a property of the text rather than of memorised outcomes, but
does not rescue it. At the RBA it is the dictionary, not the LLM, whose interval lies above zero (ΔLL
{{rq1.rows[bank=rba,scorer=dict].dll_vs_pers|.3f}} [{{rq1.rows[bank=rba,scorer=dict].dll_vs_pers_lo|.3f}},
{{rq1.rows[bank=rba,scorer=dict].dll_vs_pers_hi|.3f}}]); the dictionary was not a registered hypothesis and
we report it only as a reminder that the ranking of scorers is bank-specific. The BoE (only
{{rq1.rows[bank=boe,scorer=llm].n_oos_hike|d}} out-of-sample hikes), MAS
({{rq1.rows[bank=mas,scorer=llm].n_oos|d}} predictions) and BNM ({{rq1.rows[bank=bnm,scorer=llm].n_oos_hike|d}}
hikes) are underpowered and appear in Figure 2 with hollow markers.

Two further observations qualify the headline. Ranking metrics are high for every scorer, including the
persistence baseline (Fed persistence AUROC {{rq1.rows[bank=fed,scorer=persistence].auroc|.2f}}, ECB
{{rq1.rows[bank=ecb,scorer=persistence].auroc|.2f}}), because most of the information about the next move is
already in the last one: policy rates move in runs, and a model that knows the direction of the last decision
ranks the next correctly most of the time. The LLM raises the ECB AUROC to
{{rq1.rows[bank=ecb,scorer=llm].auroc|.2f}}, which is the same near-miss seen in log-loss. Second, BI's
masked-text AUROC of exactly {{rq1.rows[bank=bi,scorer=llm_masked].auroc|.2f}} rests on
{{rq1.rows[bank=bi,scorer=llm].n_oos_hike|d}} hikes and {{rq1.rows[bank=bi,scorer=llm].n_oos_cut|d}} cuts and is a
small-sample artefact discussed in `ANOMALIES.md` (A9), not evidence of perfect ranking.

The pre-registration also asks that the transformer scorer be reported with the same comparisons, as a
descriptive result. The FOMC-RoBERTa replication reads human-labelled Fed sentences with a macro-F1 of
{{rq4.rq4b.rows[scorer=fomc_roberta].macro_f1|.2f}} against the LLM's {{rq4.rq4b.rows[scorer=llm].macro_f1|.2f}} (Section 6.2), and does not translate that advantage
into prediction (Table 3, Figure 2). At the powered banks its gain over persistence has a bootstrap interval
that excludes zero at {{rq1.transformer.n_ci_above_zero_vs_pers|d}} of {{rq1.transformer.n_powered|d}}. The
closest are the RBA ({{rq1.rows[bank=rba,scorer=fomc_roberta].dll_vs_pers|.3f}}
[{{rq1.rows[bank=rba,scorer=fomc_roberta].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=rba,scorer=fomc_roberta].dll_vs_pers_hi|.3f}}],
unadjusted *p* {{rq1.rows[bank=rba,scorer=fomc_roberta].p_vs_pers|.2f}}) and the ECB
({{rq1.rows[bank=ecb,scorer=fomc_roberta].dll_vs_pers|.3f}}
[{{rq1.rows[bank=ecb,scorer=fomc_roberta].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=ecb,scorer=fomc_roberta].dll_vs_pers_hi|.3f}}],
*p* {{rq1.rows[bank=ecb,scorer=fomc_roberta].p_vs_pers|.2f}}); at the Fed, whose statements supplied its
training sentences, the gain is {{rq1.rows[bank=fed,scorer=fomc_roberta].dll_vs_pers|.3f}}
[{{rq1.rows[bank=fed,scorer=fomc_roberta].dll_vs_pers_lo|.3f}}, {{rq1.rows[bank=fed,scorer=fomc_roberta].dll_vs_pers_hi|.3f}}].
Its gain over the dictionary excludes zero at {{rq1.transformer.n_ci_above_zero_vs_dict|d}} of the four. A
scorer that is far better calibrated to human judgements of individual sentences is therefore no better at
the task the index is meant to serve, which locates the negative result in the information content of a
scalar tone measure rather than in the LLM's reading of it; Section 8 returns to this.

![Gain in next-decision log-loss over persistence by bank and scorer. Positive values favour the text model. Hollow markers: banks below the pre-registered power minimum, reported but outside the Holm family.](results/figures/fig_rq1_dll.svg){width=100%}

## Does the tone surprise explain the market reaction? (RQ2)

**H2a and H2b are refuted.** Of {{rq2.verdict.h2a.n_powered}} adequately powered bank–market cells, the LLM
tone surprise explains the release-window move beyond its placebo in {{rq2.verdict.h2a.n_success}}
(Table 4, Figure 3), and its R² exceeds the dictionary's, after Holm correction, in
{{rq2.verdict.h2b.n_success}}.

| Bank | Series | *n* | β | R² | Placebo R² (p95) | Holm *p* (β) | ΔR² vs dict. | Exceeds placebo |
|:---|:-----|---:|-----:|----:|------:|-----:|------:|:----:|
| Fed | USD index | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} | {{rq2.rows[bank=fed,kind=fx,scorer=llm,subset=all].h2a_success|yn}} |
| Fed | US 2Y | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].beta|.2f}} | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].dr2_vs_dict|.3f}} | {{rq2.rows[bank=fed,kind=y2,scorer=llm,subset=all].h2a_success|yn}} |
| ECB | EUR/USD | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} | {{rq2.rows[bank=ecb,kind=fx,scorer=llm,subset=all].h2a_success|yn}} |
| ECB | EA 2Y | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].beta|.2f}} | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].dr2_vs_dict|.3f}} | {{rq2.rows[bank=ecb,kind=y2,scorer=llm,subset=all].h2a_success|yn}} |
| BoE | GBP/USD | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} | {{rq2.rows[bank=boe,kind=fx,scorer=llm,subset=all].h2a_success|yn}} |
| BoE | UK 2Y | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].beta|.2f}} | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].dr2_vs_dict|.3f}} | {{rq2.rows[bank=boe,kind=y2,scorer=llm,subset=all].h2a_success|yn}} |
| RBA | AUD/USD | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} | {{rq2.rows[bank=rba,kind=fx,scorer=llm,subset=all].h2a_success|yn}} |
| RBA | AU 2Y | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].beta|.2f}} | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].dr2_vs_dict|.3f}} | {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].h2a_success|yn}} |
| MAS | USD/SGD | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} | {{rq2.rows[bank=mas,kind=fx,scorer=llm,subset=all].h2a_success|yn}} |
| BI | USD/IDR | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} | {{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].h2a_success|yn}} |
| BNM | USD/MYR | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].n_events|d}} | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].beta|.4f}} | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].r2|.3f}} | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].placebo_r2_p95|.3f}} | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].p_beta_holm|.2f}} | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].dr2_vs_dict|.3f}} | {{rq2.rows[bank=bnm,kind=fx,scorer=llm,subset=all].h2a_success|yn}} |

: Announcement-window regressions of the market move on the LLM tone surprise, all powered cells. FX β is
the signed two-day log move (positive = domestic appreciation) per unit surprise; yield β is in basis
points per unit surprise. Newey–West standard errors; Holm correction across the eleven cells.

The single success is the Australian two-year yield: a one-unit hawkish surprise is associated with a
{{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].beta|.1f}} basis-point rise (R²
{{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].r2|.2f}} against a placebo 95th percentile of
{{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].placebo_r2_p95|.3f}}). Its R² gain over the dictionary has a
bootstrap interval above zero ([{{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].dr2_lo|.3f}},
{{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].dr2_hi|.3f}}]) but a Holm-adjusted *p* of
{{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].p_dr2_holm|.2f}}, so H2b fails even there. The magnitude is
economically sensible: the R² is of the order reported for wording-based surprises in the literature
[@ehrmann2020starting], and far below what rate surprises achieve [@gurkaynak2005actions]. For BI the LLM
coefficient is statistically distinguishable from zero but carries the sign opposite to the hypothesis (β
{{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].beta|.4f}}, unadjusted *p*
{{rq2.rows[bank=bi,kind=fx,scorer=llm,subset=all].p_value|.3f}}): more hawkish surprises coincide with rupiah
depreciation over the day-level window. The pre-registered one-sided test does not count this as a
success, and because BI publishes no release time the design cannot distinguish a reaction from the
statement from a statement that responds to the day's market move (`ANOMALIES.md`, A10). Pooled across
banks with bank fixed effects, the FX coefficient is {{rq2.rq4c.pooled_fx_beta.beta|.4f}}
[{{rq2.rq4c.pooled_fx_beta.lo|.4f}}, {{rq2.rq4c.pooled_fx_beta.hi|.4f}}] (*n* =
{{rq2.rq4c.pooled_fx_beta.n|,}}), indistinguishable from zero.

The pre-registered comparison of the LLM against the transformer scorer finds no difference. Across the
{{rq2.transformer.n_cells|d}} powered cells, the LLM's R² gain over the FOMC-RoBERTa replication ranges from
{{rq2.transformer.min.dr2|.3f}} ({{rq2.transformer.min.label}}) to {{rq2.transformer.max.dr2|.3f}}
({{rq2.transformer.max.label}}), and its bootstrap interval excludes zero in
{{rq2.transformer.n_ci_excluding_zero|d}} of them. The replication's own announcement-window results mirror
the LLM's: its R² exceeds the non-announcement placebo in {{rq2.transformer.n_transformer_above_placebo|d}} of
{{rq2.transformer.n_transformer_cells|d}} cells, both at the RBA, where the two-year yield responds by
{{rq2.rows[bank=rba,kind=y2,scorer=fomc_roberta,subset=all].beta|.1f}} basis points per unit surprise (R²
{{rq2.rows[bank=rba,kind=y2,scorer=fomc_roberta,subset=all].r2|.2f}}, placebo 95th percentile
{{rq2.rows[bank=rba,kind=y2,scorer=fomc_roberta,subset=all].placebo_r2_p95|.3f}}) and the AUD/USD R² of
{{rq2.rows[bank=rba,kind=fx,scorer=fomc_roberta,subset=all].r2|.3f}} clears its placebo of
{{rq2.rows[bank=rba,kind=fx,scorer=fomc_roberta,subset=all].placebo_r2_p95|.3f}} by a hair. The better-calibrated
instrument finds the same single market, and no more (Figure 3).

![Response of the exchange rate (a) and the two-year government yield (b) to the tone surprise, by bank and scorer, with Newey–West 95 % intervals. The Australian two-year yield (ringed marker) is the only cell in which the LLM's R² exceeds its non-announcement placebo.](results/figures/fig_rq2_beta.svg){width=100%}

## Do native-language and English versions agree? (RQ3)

**H3 is refuted.** On parallel statements the LLM's native-language and English indices have a Spearman
correlation of {{rq3.rows[bank=bi,scorer=llm].spearman|.2f}} for BI (Indonesian, *n* =
{{rq3.rows[bank=bi,scorer=llm].n_pairs|d}}) and {{rq3.rows[bank=bnm,scorer=llm].spearman|.2f}} for BNM
(Malay, *n* = {{rq3.rows[bank=bnm,scorer=llm].n_pairs|d}}), both below the pre-registered 0.70. The
disagreement concerns intensity rather than direction: the stance flips between hawkish and dovish in
only {{rq3.rows[bank=bi,scorer=llm].flip_rate|pct1}} and {{rq3.rows[bank=bnm,scorer=llm].flip_rate|pct1}} of
pairs, well within the 10 % ceiling, whereas the mean absolute gap between the two indices is
{{rq3.rows[bank=bi,scorer=llm].mean_abs_diff|.2f}} and {{rq3.rows[bank=bnm,scorer=llm].mean_abs_diff|.2f}} on
a [−1, 1] scale (Figure 4). The fine-tuned multilingual encoder is no more consistent (ρ
{{rq3.rows[bank=bi,scorer=ft].spearman|.2f}} and {{rq3.rows[bank=bnm,scorer=ft].spearman|.2f}}), which
suggests that the inconsistency is not peculiar to generative decoding. The dictionary and the FOMC-RoBERTa replication are English-only and
therefore not applicable, and PBoC, with {{rq3.rows[bank=pboc,scorer=llm].n_pairs|d}} parallel pairs, is
exploratory. Figure 4 makes the structure of the disagreement visible: both languages place most statements
in a mildly dovish band, but the Indonesian versions are read as more dovish than the English ones in the
lower-left quadrant, and the Malay versions cluster more tightly around neutral.

![LLM tone of the native-language version against the English version of the same statement, for Bank Indonesia (a) and Bank Negara Malaysia (b). Marker area is proportional to the number of statements at each pair of values; the diagonal is perfect agreement.](results/figures/fig_rq3_crosslingual.svg){width=100%}

# Results: reliability and contamination

## Stability across prompts, temperatures, model versions and aggregation (H4a)

**H4a is refuted.** Table 5 and Figure 5 report Krippendorff's α and ICC(2,1) for each perturbation.
Across the five registered prompt paraphrases, document scores reach α =
{{rq4.rq4a.docs.prompts.alpha|.2f}} and ICC(2,1) = {{rq4.rq4a.docs.prompts.icc_2_1|.2f}} on
{{rq4.rq4a.docs.prompts.n_units}} documents, short of the pre-registered 0.667 and 0.75; on
{{rq4.rq4a.sentences.prompts.n_units|,}} sentences α falls to {{rq4.rq4a.sentences.prompts.alpha|.2f}}.
Temperature matters much less (α = {{rq4.rq4a.docs.temperature.alpha|.2f}} for documents and
{{rq4.rq4a.sentences.temperature.alpha|.2f}} for sentences at 0 against 0.7), which indicates that the
instability is not sampling noise but a genuine dependence of the reading on the wording of the
instruction. Replacing the model tag with `qwen2.5:3b` changes scores most of all: α =
{{rq4.rq4a.docs.model_tag.alpha|.2f}} for documents and {{rq4.rq4a.sentences.model_tag.alpha|.2f}} for
sentences, the latter no better than chance agreement. Aggregating sentence scores into a document score
yields indices that correlate with the direct document score at ρ between
{{rq4.rq4a.aggregation.spearman.agg_max_abs~document|.2f}} and
{{rq4.rq4a.aggregation.spearman.agg_decision_weighted~document|.2f}}, so not every pair of strategies clears
0.70; the mean and decision-weighted aggregates are near-identical to each other (ρ =
{{rq4.rq4a.aggregation.spearman.agg_mean~agg_decision_weighted|.2f}}), as they must be by construction
(`ANOMALIES.md`, A11).

| Perturbation | α (documents) | ICC (documents) | α (sentences) | ICC (sentences) |
|:--------------|------:|------:|------:|------:|
| Five prompt paraphrases | {{rq4.rq4a.docs.prompts.alpha|.2f}} | {{rq4.rq4a.docs.prompts.icc_2_1|.2f}} | {{rq4.rq4a.sentences.prompts.alpha|.2f}} | {{rq4.rq4a.sentences.prompts.icc_2_1|.2f}} |
| Temperature 0 vs 0.7 | {{rq4.rq4a.docs.temperature.alpha|.2f}} | {{rq4.rq4a.docs.temperature.icc_2_1|.2f}} | {{rq4.rq4a.sentences.temperature.alpha|.2f}} | {{rq4.rq4a.sentences.temperature.icc_2_1|.2f}} |
| Model tag, `qwen3:4b` vs `qwen2.5:3b` | {{rq4.rq4a.docs.model_tag.alpha|.2f}} | {{rq4.rq4a.docs.model_tag.icc_2_1|.2f}} | {{rq4.rq4a.sentences.model_tag.alpha|.2f}} | {{rq4.rq4a.sentences.model_tag.icc_2_1|.2f}} |

: Agreement between scores of the same text under each perturbation, on {{rq4.rq4a.docs.prompts.n_units}}
documents and {{rq4.rq4a.sentences.prompts.n_units|,}} sentences; α is Krippendorff's interval α and ICC is
ICC(2,1). Pre-registered floors: α ≥ 0.667 and ICC(2,1) ≥ 0.75. {{rq4.rq4a.sentences.prompts.n_complete}} of the {{rq4.rq4a.sentences.prompts.n_units|,}}
sentences have a complete set of prompt scores; the remainder returned malformed JSON in at least one
paraphrase and are treated as missing.

The practical reading is that a tone index from a small local model is, in part, a property of the prompt
and of the model version. Two analysts using different but equally reasonable instructions will obtain
series that agree only moderately, and a series computed before and after a model upgrade is not the same
measurement. The low agreement between LLM and lexicon tone reported across many banks by Xu and Vilán
[@xu2026assessing] is of the same order as our prompt-paraphrase α, which suggests that the choice of
prompt is as consequential as the choice between an LLM and a dictionary.

![Stability of the LLM index. (a) Krippendorff's α between scores of the same text under each perturbation, at document and sentence level. (b) Spearman correlation between the three sentence-aggregation strategies and the direct document score.](results/figures/fig_rq4a_stability.svg){width=100%}

## Agreement with human labels (H4b)

**H4b is refuted.** On the {{rq4.rq4b.n}}-sentence FOMC test split the LLM's three-class macro-F1 is
{{rq4.rq4b.rows[scorer=llm].macro_f1|.2f}} [{{rq4.rq4b.rows[scorer=llm].f1_lo|.2f}},
{{rq4.rq4b.rows[scorer=llm].f1_hi|.2f}}] (Table 6, Figure 6). It exceeds the dictionary's by
{{rq4.rq4b.rows[scorer=llm].df1_vs_ref|.2f}} [{{rq4.rq4b.rows[scorer=llm].df1_lo|.2f}},
{{rq4.rq4b.rows[scorer=llm].df1_hi|.2f}}], a difference whose interval lies well away from zero, but it
misses the pre-registered floor of 0.50, so the hypothesis fails on its first clause. The fine-tuned XLM-R,
trained only on the LLM's labels for corpus sentences and never on FOMC data, reaches
{{rq4.rq4b.rows[scorer=ft].macro_f1|.2f}} [{{rq4.rq4b.rows[scorer=ft].f1_lo|.2f}},
{{rq4.rq4b.rows[scorer=ft].f1_hi|.2f}}], which shows that a 270-million-parameter encoder can absorb most of
the LLM's reading at a fraction of the inference cost.

| Scorer | Macro-F1 [95 % CI] | Δ vs dictionary [95 % CI] |
|:--------|--------:|--------:|
| Dictionary (`dict-v1`) | {{rq4.rq4b.rows[scorer=dict].macro_f1|.2f}} [{{rq4.rq4b.rows[scorer=dict].f1_lo|.2f}}, {{rq4.rq4b.rows[scorer=dict].f1_hi|.2f}}] | — |
| Local LLM (`qwen3:4b`) | {{rq4.rq4b.rows[scorer=llm].macro_f1|.2f}} [{{rq4.rq4b.rows[scorer=llm].f1_lo|.2f}}, {{rq4.rq4b.rows[scorer=llm].f1_hi|.2f}}] | {{rq4.rq4b.rows[scorer=llm].df1_vs_ref|.2f}} [{{rq4.rq4b.rows[scorer=llm].df1_lo|.2f}}, {{rq4.rq4b.rows[scorer=llm].df1_hi|.2f}}] |
| Fine-tuned XLM-R | {{rq4.rq4b.rows[scorer=ft].macro_f1|.2f}} [{{rq4.rq4b.rows[scorer=ft].f1_lo|.2f}}, {{rq4.rq4b.rows[scorer=ft].f1_hi|.2f}}] | {{rq4.rq4b.rows[scorer=ft].df1_vs_ref|.2f}} [{{rq4.rq4b.rows[scorer=ft].df1_lo|.2f}}, {{rq4.rq4b.rows[scorer=ft].df1_hi|.2f}}] |
| FOMC-RoBERTa (replication) ᵃ | {{rq4.rq4b.rows[scorer=fomc_roberta].macro_f1|.2f}} [{{rq4.rq4b.rows[scorer=fomc_roberta].f1_lo|.2f}}, {{rq4.rq4b.rows[scorer=fomc_roberta].f1_hi|.2f}}] | {{rq4.rq4b.rows[scorer=fomc_roberta].df1_vs_ref|.2f}} [{{rq4.rq4b.rows[scorer=fomc_roberta].df1_lo|.2f}}, {{rq4.rq4b.rows[scorer=fomc_roberta].df1_hi|.2f}}] |

: Three-class macro-F1 on the FOMC test split ({{rq4.rq4b.n}} sentences), with bootstrap intervals over
sentences. Pre-registered floor 0.50. ᵃ Trained on the train split of the same data, so in-distribution
(Section 4.1).

Our dictionary scores {{rq4.rq4b.rows[scorer=dict].macro_f1|.2f}}, well below the roughly 0.50 reported for a
rule-based baseline by Shah, Paturi and Chava [@shah2023trillion]. The two rule sets differ, and ours
returns neutral whenever hawkish and dovish matches balance or neither appears, which is the case for almost
every FOMC test sentence; the dictionary is therefore a floor rather than a competitive baseline on
sentence-level data, even though it is competitive on document-level prediction (Section 5.2). The LLM also
over-predicts the neutral class relative to the human labels, which depresses its macro-F1 relative to its
accuracy.

Our FOMC-RoBERTa replication reaches {{rq4.rq4b.rows[scorer=fomc_roberta].macro_f1|.2f}} [{{rq4.rq4b.rows[scorer=fomc_roberta].f1_lo|.2f}}, {{rq4.rq4b.rows[scorer=fomc_roberta].f1_hi|.2f}}], against the
0.72 weighted F1 the authors report [@shah2023trillion]. Across the {{rq4.rq4b.fomc_roberta_train.n_seeds}} training seeds its
test macro-F1 is {{rq4.rq4b.fomc_roberta_train.test_macro_f1_seed_mean|.2f}} ± {{rq4.rq4b.fomc_roberta_train.test_macro_f1_seed_sd|.2f}}, so the selected
seed is typical and not a lucky draw. Removing the {{rq4.rq4b.dedup.n_in_train}} test sentences that also
occur in the train split changes its score only to {{rq4.rq4b.dedup.fomc_roberta|.2f}}. The model is
trained on the same distribution as the test split, so it is a ceiling for this split and not a
competitor. What it shows is the size of the gap: a supervised encoder of 355 million parameters, trained
on about 1,600 labelled sentences, beats the zero-shot four-billion-parameter LLM on Fed
text by a wide margin ({{rq4.rq4b.rows[scorer=fomc_roberta].macro_f1|.2f}} against {{rq4.rq4b.rows[scorer=llm].macro_f1|.2f}}). Section 7 asks
how much of that advantage survives outside the Fed.

![Agreement with human labels on the FOMC test split: three-class macro-F1 with 95 % bootstrap intervals. Shaded region: below the pre-registered floor. Dotted lines: weighted F1 values published for the same split, shown for orientation.](results/figures/fig_rq4b_fomc_f1.svg){width=100%}

## Contamination (H4c)

No RQ1 or RQ2 finding is robust, for the simple reason that none is established in the first place.
Table 7 reports the pooled estimates on original text, on masked text and on the post-cutoff window.
Pooled across the powered banks, the LLM's log-loss gain over the dictionary is
{{rq1.rq4c.pooled_dll_llm_vs_dict.dll|.3f}} [{{rq1.rq4c.pooled_dll_llm_vs_dict.lo|.3f}},
{{rq1.rq4c.pooled_dll_llm_vs_dict.hi|.3f}}] on original text and
{{rq1.rq4c.masked_pooled_dll_vs_dict.dll|.3f}} [{{rq1.rq4c.masked_pooled_dll_vs_dict.lo|.3f}},
{{rq1.rq4c.masked_pooled_dll_vs_dict.hi|.3f}}] on masked text: there is no effect to preserve, so the masked
check cannot pass. The post-cutoff window (after {{rq1.rq4c.cutoff}}) holds {{rq1.rq4c.post_cutoff.n}}
decisions and {{rq2.rq4c.post_cutoff_pooled_fx_beta.n}} FX events; its estimates overlap the full-sample
intervals but are too wide to be informative on their own.

| Quantity | Original text | Masked text | Post-cutoff window |
|:------------|-------:|-------:|-------:|
| RQ1: pooled ΔLL, LLM vs dictionary [95 % CI] (*n* = {{rq1.rq4c.pooled_dll_llm_vs_dict.n}} / {{rq1.rq4c.masked_pooled_dll_vs_dict.n}} / {{rq1.rq4c.post_cutoff.n}}) | {{rq1.rq4c.pooled_dll_llm_vs_dict.dll|.3f}} [{{rq1.rq4c.pooled_dll_llm_vs_dict.lo|.3f}}, {{rq1.rq4c.pooled_dll_llm_vs_dict.hi|.3f}}] | {{rq1.rq4c.masked_pooled_dll_vs_dict.dll|.3f}} [{{rq1.rq4c.masked_pooled_dll_vs_dict.lo|.3f}}, {{rq1.rq4c.masked_pooled_dll_vs_dict.hi|.3f}}] | {{rq1.rq4c.post_cutoff.dll|.3f}} [{{rq1.rq4c.post_cutoff.lo|.3f}}, {{rq1.rq4c.post_cutoff.hi|.3f}}] |
| RQ2: pooled FX β with bank fixed effects [95 % CI] (*n* = {{rq2.rq4c.pooled_fx_beta.n|,}} / {{rq2.rq4c.masked_pooled_fx_beta.n|,}} / {{rq2.rq4c.post_cutoff_pooled_fx_beta.n}}) | {{rq2.rq4c.pooled_fx_beta.beta|.4f}} [{{rq2.rq4c.pooled_fx_beta.lo|.4f}}, {{rq2.rq4c.pooled_fx_beta.hi|.4f}}] | {{rq2.rq4c.masked_pooled_fx_beta.beta|.4f}} [{{rq2.rq4c.masked_pooled_fx_beta.lo|.4f}}, {{rq2.rq4c.masked_pooled_fx_beta.hi|.4f}}] | {{rq2.rq4c.post_cutoff_pooled_fx_beta.beta|.4f}} [{{rq2.rq4c.post_cutoff_pooled_fx_beta.lo|.4f}}, {{rq2.rq4c.post_cutoff_pooled_fx_beta.hi|.4f}}] |

: Contamination protocol. The same pooled quantities re-estimated on entity-masked text and on documents
released after the model's public release date; *n* is given for the original, masked and post-cutoff
estimates in turn.

The informative part of the exercise is what masking does to the point estimates: almost nothing. The ECB
gain is {{rq1.rows[bank=ecb,scorer=llm].dll_vs_pers|.3f}} on original and
{{rq1.rows[bank=ecb,scorer=llm_masked].dll_vs_pers|.3f}} on masked text, and the pooled FX coefficient moves
from {{rq2.rq4c.pooled_fx_beta.beta|.4f}} to {{rq2.rq4c.masked_pooled_fx_beta.beta|.4f}}. Had the LLM been
retrieving memorised outcomes through the names and dates in the text, removing them would have degraded
the original-text estimates; it does not. This is consistent with, though it does not prove, the absence of
outcome memorisation in a four-billion-parameter model reading statements of this kind, and it implies that
the negative results above are not an artefact of contamination either.

# Transfer to Southeast Asia

**H5 is untestable as pre-registered, and could not have been supported.** The BI-English and BNM-English
silver subsets have {{rq5.dict.bi_en_n}} sentences each, below the pre-registered minimum of 50, so the
comparison of MAS with BI and BNM cannot be made. The other clause can be checked on the adequately powered MAS
cell, and it fails: H5 needs both Fed-calibrated scorers to transfer poorly to MAS, and the dictionary does not.

The FOMC-RoBERTa replication does lose accuracy outside the Fed. On the 60 MAS silver sentences its macro-F1
is {{rq5.rows[group=mas-en,scorer=fomc_roberta].silver_macro_f1|.2f}} against {{rq5.rows[group=mas-en,scorer=fomc_roberta].fomc_macro_f1|.2f}} on the FOMC test split, a drop of {{rq5.rows[group=mas-en,scorer=fomc_roberta].drop|.2f}}, beyond the pre-registered 0.10. The two underpowered
English cells point in different directions: the drop is {{rq5.rows[group=bnm-en,scorer=fomc_roberta].drop|.2f}} for BNM and {{rq5.rows[group=bi-en,scorer=fomc_roberta].drop|.2f}} for BI. So the MAS drop is not the
largest, contrary to H5's prediction. Part of each drop is error in the silver labels rather than loss of
transfer. Those labels come from the LLM, which itself reaches only {{rq4.rq4b.rows[scorer=llm].macro_f1|.2f}}
on human FOMC labels, so a scorer can be penalised for disagreeing with a wrong silver label. The numbers are
evidence that the supervised Fed model is less accurate on MAS text. They do not measure how much less.

Table 8 reports the full descriptive comparison. On the 60 MAS
silver sentences the dictionary's macro-F1 is {{rq5.rows[group=mas-en,scorer=dict].silver_macro_f1|.2f}}
against {{rq5.rows[group=mas-en,scorer=dict].fomc_macro_f1|.2f}} on FOMC sentences, so it does not lose
performance on MAS (drop {{rq5.rows[group=mas-en,scorer=dict].drop|.2f}}). The LLM and the fine-tuned
encoder score *higher* on the silver sets than on the human FOMC labels
({{rq5.rows[group=mas-en,scorer=llm].silver_macro_f1|.2f}} and
{{rq5.rows[group=mas-en,scorer=ft].silver_macro_f1|.2f}} on MAS), but the silver labels were produced by the
same model family, so these numbers measure self-agreement rather than accuracy and support no claim about
transfer. The two silver passes agree on {{rq5.label_agreement.pass_a_eq_b|pct}} of sentences, and the
silver distribution is skewed towards dovish and neutral ({{rq5.label_agreement.label_counts.dovish}} dovish,
{{rq5.label_agreement.label_counts.hawkish}} hawkish, {{rq5.label_agreement.label_counts.neutral}} neutral of
{{rq5.label_agreement.n}}).

| Scorer | Set | *n* | Silver macro-F1 | FOMC macro-F1 | Drop | Powered |
|:-----------|:---------|---:|-----:|-----:|----:|:----:|
| Dictionary | MAS, English | {{rq5.rows[group=mas-en,scorer=dict].n|d}} | {{rq5.rows[group=mas-en,scorer=dict].silver_macro_f1|.2f}} | {{rq5.rows[group=mas-en,scorer=dict].fomc_macro_f1|.2f}} | {{rq5.rows[group=mas-en,scorer=dict].drop|.2f}} | {{rq5.rows[group=mas-en,scorer=dict].powered|yn}} |
| Dictionary | BI, English | {{rq5.rows[group=bi-en,scorer=dict].n|d}} | {{rq5.rows[group=bi-en,scorer=dict].silver_macro_f1|.2f}} | {{rq5.rows[group=bi-en,scorer=dict].fomc_macro_f1|.2f}} | {{rq5.rows[group=bi-en,scorer=dict].drop|.2f}} | {{rq5.rows[group=bi-en,scorer=dict].powered|yn}} |
| Dictionary | BNM, English | {{rq5.rows[group=bnm-en,scorer=dict].n|d}} | {{rq5.rows[group=bnm-en,scorer=dict].silver_macro_f1|.2f}} | {{rq5.rows[group=bnm-en,scorer=dict].fomc_macro_f1|.2f}} | {{rq5.rows[group=bnm-en,scorer=dict].drop|.2f}} | {{rq5.rows[group=bnm-en,scorer=dict].powered|yn}} |
| Local LLM | MAS, English | {{rq5.rows[group=mas-en,scorer=llm].n|d}} | {{rq5.rows[group=mas-en,scorer=llm].silver_macro_f1|.2f}} | {{rq5.rows[group=mas-en,scorer=llm].fomc_macro_f1|.2f}} | {{rq5.rows[group=mas-en,scorer=llm].drop|.2f}} | {{rq5.rows[group=mas-en,scorer=llm].powered|yn}} |
| Local LLM | BI, English | {{rq5.rows[group=bi-en,scorer=llm].n|d}} | {{rq5.rows[group=bi-en,scorer=llm].silver_macro_f1|.2f}} | {{rq5.rows[group=bi-en,scorer=llm].fomc_macro_f1|.2f}} | {{rq5.rows[group=bi-en,scorer=llm].drop|.2f}} | {{rq5.rows[group=bi-en,scorer=llm].powered|yn}} |
| Local LLM | BI, Indonesian | {{rq5.rows[group=bi-id,scorer=llm].n|d}} | {{rq5.rows[group=bi-id,scorer=llm].silver_macro_f1|.2f}} | {{rq5.rows[group=bi-id,scorer=llm].fomc_macro_f1|.2f}} | {{rq5.rows[group=bi-id,scorer=llm].drop|.2f}} | {{rq5.rows[group=bi-id,scorer=llm].powered|yn}} |
| Local LLM | BNM, English | {{rq5.rows[group=bnm-en,scorer=llm].n|d}} | {{rq5.rows[group=bnm-en,scorer=llm].silver_macro_f1|.2f}} | {{rq5.rows[group=bnm-en,scorer=llm].fomc_macro_f1|.2f}} | {{rq5.rows[group=bnm-en,scorer=llm].drop|.2f}} | {{rq5.rows[group=bnm-en,scorer=llm].powered|yn}} |
| Local LLM | BNM, Malay | {{rq5.rows[group=bnm-ms,scorer=llm].n|d}} | {{rq5.rows[group=bnm-ms,scorer=llm].silver_macro_f1|.2f}} | {{rq5.rows[group=bnm-ms,scorer=llm].fomc_macro_f1|.2f}} | {{rq5.rows[group=bnm-ms,scorer=llm].drop|.2f}} | {{rq5.rows[group=bnm-ms,scorer=llm].powered|yn}} |
| Fine-tuned XLM-R | MAS, English | {{rq5.rows[group=mas-en,scorer=ft].n|d}} | {{rq5.rows[group=mas-en,scorer=ft].silver_macro_f1|.2f}} | {{rq5.rows[group=mas-en,scorer=ft].fomc_macro_f1|.2f}} | {{rq5.rows[group=mas-en,scorer=ft].drop|.2f}} | {{rq5.rows[group=mas-en,scorer=ft].powered|yn}} |
| Fine-tuned XLM-R | BI, Indonesian | {{rq5.rows[group=bi-id,scorer=ft].n|d}} | {{rq5.rows[group=bi-id,scorer=ft].silver_macro_f1|.2f}} | {{rq5.rows[group=bi-id,scorer=ft].fomc_macro_f1|.2f}} | {{rq5.rows[group=bi-id,scorer=ft].drop|.2f}} | {{rq5.rows[group=bi-id,scorer=ft].powered|yn}} |
| Fine-tuned XLM-R | BNM, Malay | {{rq5.rows[group=bnm-ms,scorer=ft].n|d}} | {{rq5.rows[group=bnm-ms,scorer=ft].silver_macro_f1|.2f}} | {{rq5.rows[group=bnm-ms,scorer=ft].fomc_macro_f1|.2f}} | {{rq5.rows[group=bnm-ms,scorer=ft].drop|.2f}} | {{rq5.rows[group=bnm-ms,scorer=ft].powered|yn}} |
| FOMC-RoBERTa (replication) | MAS, English | {{rq5.rows[group=mas-en,scorer=fomc_roberta].n|d}} | {{rq5.rows[group=mas-en,scorer=fomc_roberta].silver_macro_f1|.2f}} | {{rq5.rows[group=mas-en,scorer=fomc_roberta].fomc_macro_f1|.2f}} | {{rq5.rows[group=mas-en,scorer=fomc_roberta].drop|.2f}} | {{rq5.rows[group=mas-en,scorer=fomc_roberta].powered|yn}} |
| FOMC-RoBERTa (replication) | BI, English | {{rq5.rows[group=bi-en,scorer=fomc_roberta].n|d}} | {{rq5.rows[group=bi-en,scorer=fomc_roberta].silver_macro_f1|.2f}} | {{rq5.rows[group=bi-en,scorer=fomc_roberta].fomc_macro_f1|.2f}} | {{rq5.rows[group=bi-en,scorer=fomc_roberta].drop|.2f}} | {{rq5.rows[group=bi-en,scorer=fomc_roberta].powered|yn}} |
| FOMC-RoBERTa (replication) | BNM, English | {{rq5.rows[group=bnm-en,scorer=fomc_roberta].n|d}} | {{rq5.rows[group=bnm-en,scorer=fomc_roberta].silver_macro_f1|.2f}} | {{rq5.rows[group=bnm-en,scorer=fomc_roberta].fomc_macro_f1|.2f}} | {{rq5.rows[group=bnm-en,scorer=fomc_roberta].drop|.2f}} | {{rq5.rows[group=bnm-en,scorer=fomc_roberta].powered|yn}} |

: Descriptive transfer comparison. Silver macro-F1 is against LLM-produced silver labels and, for the LLM
and the fine-tuned encoder, measures self-agreement rather than accuracy. FOMC-RoBERTa reads English only.
Drop = FOMC macro-F1 − silver
macro-F1; the pre-registered hypothesis predicts a drop of at least 0.10 for MAS.

In the multilingual sentence-embedding space, MAS sentences are the farthest from Fed sentences (mean
cosine distance {{rq5.distance[group=mas-en].mean_cosine_distance_to_fed|.2f}}, against
{{rq5.distance[group=ecb-en].mean_cosine_distance_to_fed|.2f}} for the ECB and
{{rq5.distance[group=fed-en].mean_cosine_distance_to_fed|.2f}} within the Fed's own sentences), consistent with
the distinct vocabulary of an exchange-rate-centred regime [@parrado2004singapore]. The supervised Fed
model loses accuracy on that text, and the dictionary does not. A human-labelled Southeast Asian set of
adequate size is what would turn these descriptive drops into a test.

# Discussion

Five findings deserve interpretation beyond the verdicts.

*Persistence is the baseline to beat, and it is a strong one.* Most of what can be predicted about the next
decision is in the last decision, because policy rates move in runs. The ordered-logit model with tone,
its change and the last direction never beats a smoothed persistence forecast after correction, and the
one near-miss, the ECB, has an unadjusted *p* of {{rq1.rows[bank=ecb,scorer=llm].p_vs_pers|.3f}} across
{{rq1.rows[bank=ecb,scorer=llm].n_oos|d}} out-of-sample decisions. This is not a statement that statements
are uninformative; it is a statement that the information a small LLM extracts from them, compressed to a
scalar, adds little to a trivial forecast of the *direction* of the next move. Text may well inform the
size and timing of moves, or the probability of a change at all, none of which the pre-registered test
measures.

*The announcement-window result is of the expected order.* The Australian two-year yield responds to the
tone surprise by about {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].beta|.0f}} basis points per unit of
surprise, with an R² near {{rq2.rows[bank=rba,kind=y2,scorer=llm,subset=all].r2|.2f}}. That is the magnitude the
wording-based literature leads one to expect [@ehrmann2020starting], an order of magnitude below the
explanatory power of rate surprises [@gurkaynak2005actions]. The pre-registration anticipated small R²
values and set the bar at beating a placebo rather than at a size; one cell in eleven cleared it, which
after correction for eleven tests is what chance would deliver. We do not think the Australian result is
spurious, but we also cannot claim it.

*Cross-lingual disagreement is about intensity, not sign.* The LLM reads the Indonesian and Malay versions
of a statement as pointing the same way as the English version in roughly 98 % of cases, but assigns
different strengths. For an analyst who needs a categorical stance this is reassuring; for one who needs
an index it means that the native-language and English series are not interchangeable, and that the
choice of language is a modelling decision to be reported. The fine-tuned encoder shows the same pattern,
so the disagreement is not an artefact of generative decoding; it is more plausibly a property of how a
small multilingual model represents evaluative language in the two tongues.

*Prompt dependence is the binding reliability constraint.* The agreement between five paraphrases of the
same instruction (α = {{rq4.rq4a.docs.prompts.alpha|.2f}} at document level) is lower than the agreement
between temperatures and comparable to the agreement between an LLM and a lexicon reported elsewhere
[@xu2026assessing]. In the framework of Ludwig, Mullainathan and Rambachan [@ludwig2025llm], the LLM index is
a measurement with substantial and possibly non-classical error, and the magnitude of that error depends on
a design choice that is rarely reported. The implication for practice is direct: a tone series is a
measurement only when the prompt and the model digest are frozen and logged, and a change in either is a
change of instrument.

*The binding constraint is the signal, not the instrument.* A natural reading of the negative results is
that a four-billion-parameter model reads tone too noisily and that a better reader would find the signal.
The FOMC-RoBERTa replication tests that reading. It agrees with human labels on Fed sentences at a macro-F1
of {{rq4.rq4b.rows[scorer=fomc_roberta].macro_f1|.2f}}, against the LLM's {{rq4.rq4b.rows[scorer=llm].macro_f1|.2f}}, yet it improves on persistence at none of the
powered banks, the Fed included, and its announcement-window R² is indistinguishable from the LLM's in every
powered cell (Sections 5.2 and 5.3). Two instruments that differ greatly in how well they read individual
sentences agree closely on how little a scalar tone index adds to a persistence forecast or to a two-day
market move. The limiting factor is what a single hawkish–dovish number can carry about a decision that is
mostly determined by the last one, not the model that produces the number. This does not rule out richer
text measures, such as sentence-level or topic-specific tone, which this design does not test.

What, then, is a local LLM good for? It reads individual sentences better than a dictionary, with a
macro-F1 that is close to the pre-registered floor and above the rule-based figure in the published
literature; it produces series that track the broad policy cycle; and it does so in seconds per document,
on hardware that costs less than a year of a commercial data subscription, with no text leaving the
machine. These are the properties of a monitoring aid. They are not, on this evidence, the properties of
a forecasting or trading signal, and the contamination protocol shows that the absence of signal is not
because the model has been prevented from cheating.

# Threats to validity

- **Small samples for Southeast Asian banks.** BI's text begins in April 2016 because the bank's own index
  lists nothing older; BNM changes its rate rarely; MAS met only twice a year until 2024. Several cells
  therefore fall below the pre-registered minimum and are reported as underpowered rather than tested, and
  the study is correspondingly less informative about the region than about the four large banks.
- **Silver labels.** The Southeast Asian evaluation set is labelled by the same model family as the LLM
  scorer. The LLM's own silver score is reported but is used for no hypothesis, and the fine-tuned
  encoder's silver score inherits the same circularity.
- **A short post-cutoff window.** The model's public release date is late in the sample, so the post-cutoff
  check is wide and often inconclusive; an inconclusive check means a finding is *not established as
  robust*, which is the conservative reading.
- **Document selection.** One primary series per bank; the BoE uses minutes because its early decision
  releases carry no text; the RBA series starts in December 2007. A different choice of document could give
  different tone series, which the library makes easy to test but this paper does not.
- **Timing.** MAS and BI publish no release time, so their event windows span the whole release day and
  cannot separate the market's reaction to the statement from the statement's reaction to the market.
- **MAS decisions.** Taken from the Authority's own table; the rule-based extractor's accuracy is
  development accuracy only and affects two 2026 statements that are excluded from every test.
- **Replicated reference model.** The authors' FOMC-RoBERTa is gated and access was not granted, so the
  reference scorer is our replication of their recipe (D21). It reaches the published level on the FOMC test
  split, but it is not the same set of weights, and it was trained without the authors' grid over learning
  rate and batch size. Readers can check it directly: the weights are released under the data's own
  non-commercial licence. Its RQ1 and RQ2 results are descriptive and outside the Holm families, as
  pre-registered. It was trained on Fed sentences only, so a weaker showing at other banks would be expected;
  that it does not beat persistence at the Fed either is the informative part.
- **Compute and model scale.** The four-billion-parameter model is far smaller than hosted frontier models.
  The results speak to what an analyst can run on local hardware, not to the capabilities of the largest
  models; a frontier model might pass tests this one fails, and might also be more contaminated.

# Reproducibility

All code is released under the Apache-2.0 licence at <https://github.com/thanatchon36/cbtone> and on PyPI
as `cbtone`. `make reproduce` rebuilds every table and figure from the committed corpus snapshot; LLM scores
are cached by content hash, so a re-run repeats only the few calls that failed the first time, while the
fine-tuned encoder is retrained, which on Apple MPS is not bit-for-bit deterministic (`ANOMALIES.md`, A13).
The pre-registration is the git tag `prereg-v1`; every later deviation is listed in `docs/DECISIONS.md`
(D17–D21) and every data anomaly in `docs/ANOMALIES.md`. LLM scores were computed on a desktop RTX 4070 Ti
(D20); the fine-tuned encoder and the FOMC-RoBERTa replication were trained on an Apple M4 laptop (16 GB,
MPS). The replication takes about two hours for three seeds, plus ten minutes to score the English corpus,
and is not part of `make reproduce`; `make fomc-roberta` rebuilds both, and the weights are published
separately (D21).
Per-stage wall time is in
`results/timing.json` and the hardware and software manifest in `results/hardware.json`. Every number in
this paper, including those in the abstract, is injected from `results/summary.json` at build time
(`paper/build.py`); none is typed by hand. A fresh-clone reproduction on 14 October 2026 completed in 23
minutes with no change to any verdict.

# Conclusion

A small open-weight language model running on a consumer graphics card produces hawkish/dovish tone
indices for seven central banks in three languages that look plausible over time and agree with human
FOMC labels better than a dictionary, though far below a supervised encoder trained on those labels. On every pre-registered test of *policy signal*, next-decision
prediction, announcement-window reaction, cross-lingual consistency and prompt stability, the evidence is
negative or underpowered, and the entity-masking and post-cutoff checks show that the negative result is
not an artefact of contamination, while a supervised encoder that reads Fed sentences far more accurately
fails the same tests, so it is not an artefact of a weak instrument either. Three lessons follow for
practitioners. First, persistence is a strong baseline for decision prediction, and gains from text are
small, bank-specific and no larger for a better-calibrated scorer. Second, LLM tone
depends on the prompt and on the model version, so a single-prompt index should not be treated as a
measurement without a stability check, and the prompt and model digest should be reported as part of the
measurement. Third, for Southeast Asian banks the binding constraint is sample size, which no improvement
in the scorer can relax. The library, the masked and post-cutoff checks, and every number in this paper can
be regenerated with a single command; we hope that the design, rather than the particular model, is what
is reused.

# References {.unnumbered}
