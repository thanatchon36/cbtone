# Literature review

33 sources, each verified to exist against a publisher, repository, Crossref or Hugging Face page
(BibTeX: [`refs.bib`](refs.bib)). The source-by-source notes are in three cluster files:

- [Cluster A: measuring central-bank tone](cluster_a.md) (10): dictionaries, word counts,
  topic models, supervised transformers.
- [Cluster B: LLMs for macro/finance text; reliability; contamination](cluster_b.md) (12).
- [Cluster C: announcement event studies; MAS; emerging-market communication](cluster_c.md) (12, one
  shared with B).

## 1. Synthesis

**Measurement has moved from counting words to classifying them, and so far almost only for the Fed.**
The first generation counts hawkish and dovish terms (Apel & Blix Grimaldi 2014; Lucca & Trebbi 2009)
or uses generic finance dictionaries (Loughran & McDonald 2011), sometimes adapted to a single bank
(Picault & Renault 2017 for the ECB). Topic models use deliberation transcripts to study how
transparency changes what members say (Hansen, McMahon & Prat 2018) and separate new information from
forward guidance (Hansen & McMahon 2016). Supervised transformers came next: FOMC-RoBERTa (Shah,
Paturi & Chava 2023) is trained on 2,480 hand-labelled FOMC sentences and reaches a weighted F1 of
0.72, against about 0.50 for a rule-based baseline and 0.59 for zero-shot ChatGPT-3.5.
CentralBankRoBERTa (Pfeifer & Marohl 2023) reports 0.88 on sentiment, but that figure comes from its
model card and has not been checked against the paper. The Fed is also the only bank with a public
human-labelled hawkish/dovish set, so outside the Fed there is no direct check against human
judgement for any scorer.

**Asking an LLM to score the text works, but how well depends on the setup.** Zero-shot GPT-3 reads
FOMC stance only modestly (Hansen & Kazinnik: accuracy 0.37, κ 0.18; fine-tuned 0.61, κ 0.46). The one
study covering many banks and languages (Silva, Moriya & Veyrune 2025, IMF; 169 banks, 87% English)
finds that a fine-tuned multilingual encoder beats GPT-4o on stance by a wide margin (macro F1 0.92 vs
0.57). It also finds that forward-looking policy sentiment predicts the next rate change. Prompt
format alone can move accuracy by up to 76 points (Sclar et al. 2024), which motivates RQ4a's prompt
perturbations. LLM annotation can beat crowd workers on cost and agreement (Gilardi et al. 2023).

**Contamination is a real threat, and it is measurable.** Lopez-Lira, Tang & Zhu show LLMs recall
macro outcomes almost perfectly before their training cutoff (> 96 % threshold accuracy) and at near
chance afterwards (29–53 %). Glasserman & Lin find that masking entity names changes GPT-sentiment
trading returns by a few bp/day in-sample, and that the difference is not significant out of sample.
Sarkar & Vafa propose formal tests for look-ahead bias. No study yet combines masking and a
post-cutoff split on central-bank text; cbtone's RQ4c does both.

**Market reactions to announcements are well measured; the role of tone in them less so.** Kuttner (2001)
and Gürkaynak, Sack & Swanson (2005) set the event-study template. A 1 pp target surprise moves 2y
yields by about 49 bp, and a separate "path" factor captures what the statement says (intraday R²
up to 0.80 for T-bills, 0.36 for equities). Bernanke & Kuttner (2005) put a 25 bp surprise cut at
about +1 % on equities. Blinder et al. (2008) survey why communication moves markets. Text-based
surprise measures tend to explain much less than rate surprises on daily data; Ehrmann & Talmi
(2020) report pseudo-R² up to 0.12 for how changes in statement wording relate to policy. **cbtone
therefore expects small daily R² values from tone surprises, and pre-registers them as small.**

**Southeast Asia and exchange-rate regimes are thinly covered.** For Malaysia there is a yield-curve
event study (Ho & Karagedikli 2021; the first factor explains about 71 % of the 1y move), plus
regional transparency surveys (Filardo & Guinigundo 2008) and EM evidence from Brazil (Montes &
Nicolay 2016) and on Fed spillovers (Hayo, Kutan & Neuenkirch 2012). For MAS we found **no** study
linking MPS text to S$NEER or USD/SGD reactions; Parrado (2004) only describes how the regime works.
No study compares tone scores between native-language and English versions of the same central-bank
document.

## 2. Benchmarks used by the "> 2× off literature" sanity check

| Quantity | Literature value | Source |
|---|---|---|
| FOMC sentence stance, fine-tuned RoBERTa-large, weighted F1 | 0.717 (press conf. 0.55) | Shah et al. 2023 |
| Same, zero-shot ChatGPT-3.5 | 0.587 | Shah et al. 2023 |
| Same, rule-based dictionary | ≈ 0.50 | Shah et al. 2023 |
| Inter-annotator agreement, FOMC set | 89–95 % | Shah et al. 2023 |
| FOMC 5-class stance, zero-shot GPT-3 accuracy / κ | 0.37 / 0.18 | Hansen & Kazinnik 2023 |
| Multi-bank stance macro-F1, fine-tuned encoder / GPT-4o | 0.917 / 0.570 | Silva et al. 2025 |
| LLM vs lexicon tone correlation (speeches) | 0.49 | Xu & Vilán 2026 |
| 2y yield response to 1 pp target surprise | +49 bp | Gürkaynak et al. 2005 |
| Tone/wording change → policy, pseudo-R² | ≤ 0.12 | Ehrmann & Talmi 2020 |
| Prompt-format accuracy spread | up to 76 pts | Sclar et al. 2024 |

Items flagged in the cluster files as "abstract only" or "not read directly" (Kuttner 2001 and Hayo
et al. 2012 coefficients, Apel & Blix Grimaldi fit statistics, the CentralBankRoBERTa model-card F1)
are **not** used as hard thresholds.

## 3. Gap table

Which (bank × language × scorer × evaluation) cells have a published test? ✓ = at least one study;
~ = partial (e.g. translation consistency only, or a regime description without text measurement);
— = none found. "cbtone" marks the cells this project fills.

| Bank / language | Dictionary vs human labels | Transformer vs human | LLM vs human | Next-decision prediction | Market event study with tone | Cross-lingual consistency | Contamination check (mask + post-cutoff) |
|---|---|---|---|---|---|---|---|
| Fed / en | ✓ | ✓ | ✓ | ✓ | ✓ | n/a | — → **cbtone** |
| ECB / en | ~ (Picault–Renault, no human labels) | — | — | ✓ | ✓ | n/a | — → **cbtone** |
| BoE / en | — | — | — | ~ | ~ | n/a | — → **cbtone** |
| RBA / en | — | — | — | ~ (Silva et al. pooled) | — | n/a | — → **cbtone** |
| MAS / en (FX-band regime) | — | — | — | — | — | n/a | — → **cbtone** |
| BI / id + en | — | — | — | ~ (pooled) | — | ~ (Silva: translation check, other languages) | — → **cbtone** |
| BNM / ms + en | — | — | — | ~ | ~ (Ho–Karagedikli, rate surprises not tone) | — | — → **cbtone** |
| PBoC / zh + en | — | — | — | ~ | — | — | — → **cbtone** |

Takeaways for the research questions:

- Every non-Fed row lacks human-label agreement for every scorer. This is why RQ5 uses Fed-calibrated
  scorers on SEA text, scored against silver labels, explicitly marked as silver.
- The contamination column is empty for every bank (RQ4c).
- Cross-lingual consistency on parallel official translations is untested for SEA banks (RQ3).
- A market event study using MAS text against S$NEER/USD-SGD does not exist (RQ2, RQ5).
