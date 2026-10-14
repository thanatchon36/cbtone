# Research questions — pre-registration (`prereg-v1`)

Frozen at tag `prereg-v1`, before any scorer runs on the full corpus (MISSION §0). Nothing in this
file changes after the tag. Results that contradict it are reported as **refuted**, not re-framed.
Deviations forced by facts discovered later (e.g. a model that will not run) are recorded in
`docs/DECISIONS.md` as dated deviations, with the reason, and the paper lists every one of them.

Corpus: snapshot `2026-10-14+ed5a49c2…` (`data/corpus/VERSION`). Decisions: `data/corpus/decisions.parquet`.

---

## 0. Common definitions

### 0.1 Banks and their roles
| Role | Banks | Used in |
|---|---|---|
| Headline | Fed, ECB, BoE, RBA, MAS, BI, BNM | all hypothesis tests, majority rules, Holm families |
| Opt-in | BoT (`include_bot: false`) | appendix only, when opted in; never in headline counts |
| Exploratory | PBoC (D15: 53 % zh coverage, 2016–2022 gap) | descriptive appendix only; no hypothesis test |

### 0.2 Primary document per bank (one tone value per decision)
| Bank | Primary series | Release / event time |
|---|---|---|
| Fed | FOMC statement (en) | `published_at_utc` |
| ECB | monetary policy decision press release (en) | `published_at_utc` |
| BoE | MPC **minutes** for every meeting (A6: 2000–2006 releases are one sentence) | minutes release: 09:30 London before 6 Aug 2015, 12:00 after |
| RBA | decision statement (en), **from Dec 2007 only** (A1: earlier releases exist only for rate changes, so the sample would be selected on the outcome) | `published_at_utc` (14:30 Sydney) |
| MAS | Monetary Policy Statement (en) | day-level (§0.4) |
| BI | press release, **en** primary; id used in RQ3 | day-level (§0.4) |
| BNM | MPS, **en** primary; ms used in RQ3 | `published_at_utc` (embargo line) |

Secondary series (robustness only): Fed minutes and press conferences, ECB press conferences,
BoE statements from 2013, RBA minutes.

A decision document at meeting *t* is used to predict decision *t+1* only if it was released
before *t+1* (it always is for the series above; the BoE minutes lag of ~13 days is shorter than
the inter-meeting gap, and the RQ1 code asserts this per row).

### 0.3 Decisions and directions
- `direction ∈ {hike, hold, cut}` from `decisions.parquet` (BIS rates plus meeting dates; MAS from its own
  decision table, D14). For MAS, tighten = hike, ease = cut.
- Rows with `source = "mas_text"` (2 MAS rows in 2026) are excluded from the hypothesis tests and
  reported in a footnote, because the extractor's accuracy is development accuracy only (D14).

### 0.4 Release-date rule for documents without a release time
1. If `published_at_utc` is set, the event timestamp is that instant.
2. Otherwise, the **release date** is determined first:
   - The release date is the document `date`, except where the bank releases after the meeting date.
   - RBA releases before Dec 2007 are on `date + 1` (A1).
   - PBoC uses the page's stated time (D15).
   - Any adapter that knows a lag must emit it. A document whose release date is unknown is excluded
     from event studies and counted in a table.
3. With a release date *D* and no time, the event timestamp is **00:00 local time on D** (the bank's IANA zone).
   - With the event day *t* = the first close strictly after the timestamp (D9), the window
     [*t*−1 close, *t*+1 close] then spans all of day *D*. The release is inside the window wherever
     in *D* it happened.
   - The cost is a wider window, so more noise and less power, never look-ahead.
4. Every event carries `timing ∈ {exact, day}`. Results are reported for all events and, as
   robustness, for `exact` only.

Day-level banks: MAS, BI, RBA before 2008, BoE special March 2020 meetings, PBoC where no time is stated.

### 0.5 Tone
- `ToneScore.index = hawkish_p − dovish_p ∈ [−1, 1]`.
- **Document-level LLM input:** paragraphs tagged `decision`, `forward_guidance`, `outlook`, `risks`
  (priority order, kept in document order), up to **6,000 characters**. If the tagger finds none, the
  first 6,000 characters are used instead. The same input goes to every scorer, so they are compared on the same text.
- **Headline LLM:** `qwen3:4b` via Ollama, prompt `P1`, temperature 0, thinking disabled.
  - **Model fallback:** if `qwen3:4b` cannot score the primary corpus within the budget (§0.8), use
    `qwen2.5:3b`. This choice is made from timing alone, before any outcome is looked at, and recorded in DECISIONS.
  - The exact tag, quantisation and digest go into every result.
- **Training cutoff** for the post-cutoff split: the model's documented cutoff, or if none is
  documented, its **public release date** (qwen3: 2025-04-29; qwen2.5: 2024-09-19).

### 0.6 Statistics
- Bootstrap: moving-block bootstrap over each bank's decision sequence, block length 4, 2,000 replicates,
  seed 20261014. 95 % percentile CIs.
- Multiple comparisons: **Holm** across the adequately powered headline banks within each RQ, family-wise α = 0.05.
  Captions say so.
- HAC (Newey–West, lag 1) standard errors for event regressions.
- Placebos are reported next to every real result:
  - **shuffled-date tone:** tone permuted across decisions within bank, 1,000 permutations;
  - **permuted labels:** next-direction permuted, 1,000 permutations;
  - **non-announcement days:** 1,000 random business days per bank, at least 5 days away from any decision.

  A real result is credible only if it exceeds the placebo's 95th percentile.

### 0.7 Power rule (all RQs)
A (bank, RQ) cell is **adequately powered** only if it meets the minimum in its RQ section. Underpowered
cells are:
- reported in an appendix table with their point estimate and CI, labelled *underpowered*;
- **excluded** from Holm families and from every majority count;
- pooled where stated, with the pooled estimate reported as secondary.

A majority rule needs at least 3 powered headline banks; otherwise the RQ is reported as **untestable**,
not as supported or refuted.

### 0.8 Budget ladder (from timing alone, before any outcome)
The full LLM budget is ≤ 2 h. If the measured throughput on a 60-document sample predicts that it will be exceeded, apply in order and
record each step:
1. shrink the RQ4a sentence sample (1,000 → 500 → 250);
2. reduce the document input cap (6,000 → 3,000 characters), for all scorers alike;
3. run the masked variant only on the primary series of the headline banks.

### 0.9 Sanity rules (MISSION §0)
A headline metric exactly 0, 1 or 100 %, a correlation > 0.95, or a value more than 2× outside the
`REVIEW.md` §2 range fails the build until explained in `docs/ANOMALIES.md`. Ranges used:
- FOMC sentence macro/weighted F1: dictionary ≈ 0.50, zero-shot LLM ≈ 0.59, fine-tuned ≈ 0.72;
- tone → policy pseudo-R² ≤ 0.12 (a value > 0.24 is flagged);
- LLM–lexicon correlation ≈ 0.49 (> 0.98 or < 0.25 is flagged).

---

## RQ1 — Policy signal

**H1.** Document tone at decision *t* improves out-of-sample prediction of the direction of decision
*t+1* beyond a persistence baseline, and the LLM scorer does so better than the dictionary scorer.

- **Model:** ordered logit (cut < hold < hike) on `(tone_t, Δtone_t, last_direction_t)` per bank, one fit per scorer.
  - **Persistence baseline:** the predictive distribution = the empirical frequency of `next_direction` given
    `last_direction` in the training window (Laplace-smoothed).
- **Evaluation:** rolling origin, expanding window. The initial training window is the first 40 % of a bank's decisions (at least 30),
  refit at every step, predicting one step ahead.
- **Metrics:**
  - **primary:** multiclass log-loss;
  - **secondary:** AUROC hike-vs-cut on out-of-sample (OOS) rows whose actual next is hike or cut, with score P(hike)/(P(hike)+P(cut)).
- **Comparisons**, each as ΔLL = LL(reference) − LL(model) with a block-bootstrap CI:
  - (a) LLM vs persistence;
  - (b) LLM vs dictionary.
- **Threshold:** H1 is **supported** if (b) has a CI excluding zero in favour of the LLM in a **strict
  majority of the adequately powered headline banks**, and (a) does too in the same majority. It is **refuted** if
  the majority fails. Transformer and fine-tuned scorers are reported with the same comparisons, as
  descriptive results, not part of H1.
- **Refuting experiment:** the same pipeline with shuffled-date tone and permuted labels. If the real ΔLL
  is not above the placebo's 95th percentile, the bank counts as a failure for H1.
- **Minimum sample:** ≥ 40 OOS predictions **and** ≥ 8 hikes **and** ≥ 8 cuts among the OOS actual next directions.
- **If underpowered:** appendix row. MAS, BI and BNM are also pooled (bank fixed effects, common slopes) as a
  secondary "SEA pooled" estimate.
- **Expected:** effects are small (pseudo-R² ≤ 0.12, Ehrmann & Talmi 2020). With BNM at 14 hikes / 10 cuts
  in total, BNM is expected to be underpowered. That expectation is written here so the outcome cannot be framed after the fact.

## RQ2 — Market reaction

**H2.** The tone surprise explains 1-day FX and 2-year-yield moves around announcements, and the LLM explains
more than the dictionary and transformer scorers.

- **Tone surprise** = tone_t − E[tone_t | tone_{t−1}] from an AR(1) fitted per bank on prior documents only
  (expanding window, ≥ 8 prior documents; earlier events are dropped).
- **Market move:** close-to-close change over [*t*−1, *t*+1] (§0.4).
  - FX: log return, signed so that **positive = domestic-currency appreciation**.
  - Yields: change in bp.
  - Series: Fed→DXY and DGS2; ECB→EURUSD and EA2Y; BoE→GBPUSD and GB2Y; RBA→AUDUSD and AU2Y (2013→);
    MAS→USDSGD; BI→USDIDR; BNM→USDMYR. The yield leg covers only Fed/ECB/BoE/RBA (D9).
- **Regression:** move = α + β·surprise + ε, HAC SE.
- **Metrics:** R², β with HAC t-stat, sign agreement (share of events where sign(surprise) = sign(move); binomial test vs 0.5).
- **"More" (pre-set):** ΔR² = R²(LLM) − R²(dictionary) has a block-bootstrap 95 % CI excluding zero.
  - H2a (signal): β > 0 with Holm-adjusted p < 0.05 in a strict majority of powered (bank, series) cells,
    and above the non-announcement placebo's 95th percentile.
  - H2b (LLM better): "more" holds in a strict majority of powered cells. The same comparison against the transformer is reported.
- **Expected:** R² is small, single digits in %. An R² > 0.24 is flagged by the sanity rules.
- **Minimum sample:** ≥ 30 events with market data per (bank, series). FX starts Dec 2003 for most pairs (A7).
- **If underpowered:** appendix row, and an SEA pooled FX regression.

## RQ3 — Cross-lingual consistency

**H3.** On parallel documents, a multilingual scorer gives consistent tone across the native and English versions.

- **Pairs (headline):** BI id/en (128 meetings), BNM ms/en (139). Appendix: BoT th/en (if opted in),
  PBoC zh/en (9 pairs, exploratory).
- **Metrics:** Spearman ρ between native and English index, mean |Δindex|, stance-flip rate (share of pairs
  where sign(index) differs and both |index| > 0.1).
- **Threshold:** a scorer is **consistent** on a language pair if ρ ≥ 0.70 **and** flip rate ≤ 10 %. H3 is supported for
  the LLM if it is consistent on both id/en and ms/en.
- **Applicability:** scorers that cannot read a language (the English dictionary, FOMC-RoBERTa) are reported as
  *not applicable* for the native side. That limitation is itself a finding, carried into RQ5.
- **Secondary (descriptive):** is the native-language surprise closer to the FX reaction (higher R²) than the English one?
- **Minimum sample:** ≥ 30 pairs. PBoC (9) is underpowered by construction.

## RQ4 — Reliability and contamination

**H4a (stability).** LLM document scores are stable across the 5 registered prompts: Krippendorff's α (interval)
≥ 0.667 and ICC(2,1) ≥ 0.75. The following are reported against the same thresholds:
- temperature 0 vs 0.7;
- the two model tags (qwen3:4b, qwen2.5:3b);
- sentence- vs document-level aggregation (mean, decision-weighted, max-|index|; Spearman ρ ≥ 0.70 between strategies).

Run on the stratified sentence sample (§0.8; stratified by bank × language × doc type) and on 120
primary documents (stratified by bank).

**H4b (agreement with human labels).** On the FOMC test split (496 sentences, Shah et al. 2023, CC-BY-NC, evaluation
only), the LLM's 3-class macro-F1 is ≥ 0.50 and exceeds the dictionary's, with a bootstrap CI (sentence
resampling) excluding zero.
- Expected: dictionary ≈ 0.50, zero-shot LLM ≈ 0.59, FOMC-RoBERTa ≈ 0.72.
- FOMC-RoBERTa was trained on this dataset's train split, so its score is in-distribution and is reported with that caveat.

**H4c (contamination).** A finding from RQ1 or RQ2 is called **robust** only if it survives both checks:
- **masked:** the same analysis on masked text (bank names, countries, dates, rate levels → placeholders) gives the
  same sign, a CI excluding zero, and ≥ 50 % of the unmasked effect;
- **post-cutoff:** on documents dated after the training cutoff (§0.5), pooled across headline banks with bank
  fixed effects, the estimate has the same sign and its CI overlaps the full-sample CI.
  - The post-cutoff period is short (~1.5 years), so a pooled post-cutoff N < 30 decisions makes the check
    **inconclusive**. An inconclusive check means the finding is reported as *not established as robust*, never as robust.

## RQ5 — Transfer to Southeast Asia

**H5.** Scorers calibrated on Fed text (dictionary weights, FOMC-RoBERTa, an LLM prompt written against Fed
examples) lose performance on BI, BNM and MAS, and MAS's exchange-rate framing hurts rate-centric scorers most.

- **Metrics:**
  - 3-class macro-F1 on the SEA silver set (200 sentences: MAS 60, BI 35 + 35, BNM 35 + 35; labels from two LLM passes
    with different prompts plus a tie-break, always called *silver*), compared with each scorer's FOMC-test macro-F1;
  - the RQ1 OOS log-loss gain per bank.
- **Threshold:** a scorer **transfers poorly** to a bank if its silver macro-F1 is ≥ 0.10 below its FOMC macro-F1.
  H5 is supported if FOMC-RoBERTa and the dictionary transfer poorly to MAS **and** the drop on MAS is larger than
  on BI-en and BNM-en.
  - Silver labels are produced by the same model family as the LLM scorer, so the LLM's silver macro-F1
    is reported but **not** used for H5. The circularity is stated.
- **"Least Fed-like" language (descriptive, no threshold):** mean cosine distance between each bank's sentence
  embeddings and the Fed centroid (multilingual sentence-embedding model, recorded in DECISIONS),
  set beside the performance drop.
- **Minimum sample:** ≥ 50 silver sentences per bank (MAS 60, BI 70, BNM 70: all meet it).

---

## Data gaps and their treatment (see `docs/ANOMALIES.md`)

| Gap | Treatment in the analysis |
|---|---|
| BI text from Apr 2016 only (A5) | BI sample starts 2016-04; N stated in every BI table |
| BoT text from 2021 only (A4) | BoT is opt-in and appendix only, so it is underpowered by design |
| PBoC 53 % zh coverage, 2016–2022 missing (D15) | exploratory appendix; no hypothesis test |
| BoE 2000–2006 releases are one sentence (A6) | BoE primary series = minutes; statements from 2013 as robustness |
| BoE release times assumed for 2000–2012 (A3) | BoE event study re-run on 2013→ as robustness |
| RBA before Dec 2007: releases only on changes (A1) | excluded from RQ1/RQ2 primary samples |
| MAS 27 Jul 2026 missing (maintenance captures), 14 Oct 2026 not archived | MAS series ends Apr 2026; the post-table extractor rows are excluded (§0.3) |
| MAS statements 2001–2003 have no FX window (A7) | RQ2 MAS sample starts Dec 2003 |
| FX bad ticks (A7) | filtered by `clean_fx` before any event window |
| Day-level timing (MAS, BI, RBA < 2008, BoE specials) | §0.4 rule; `exact`-only robustness |
