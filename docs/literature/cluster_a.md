# Cluster A: Measuring central-bank communication tone

Ten sources, each checked against Crossref and/or publisher, repository, ACL Anthology or Hugging Face pages. Numeric benchmarks marked **[checked]** were read in the primary text; **[unchecked]** figures come only from a secondary page. BibTeX: `refs_a.bib`.

## Key benchmarks for the "> 2x off literature" check

| Quantity | Value | Source |
|---|---|---|
| RoBERTa-large, FOMC hawk/dove/neutral, weighted F1, combined data (MM+PC+SP), 80:20 split, mean of 3 seeds | 0.7171 (sd 0.0164); 0.7113 after sentence splitting **[checked]** | shah2023trillion, Table 5 |
| Same, per document type (before split) | minutes 0.7150, press conferences 0.5517, speeches 0.7169 **[checked]** | shah2023trillion, Table 5 |
| RoBERTa-base, combined | 0.6755 (0.6981 after split) **[checked]** | shah2023trillion |
| Rule-based (dictionary) baseline | about 0.50 F1 (0.4966 combined) **[checked]** | shah2023trillion |
| ChatGPT-3.5-turbo zero-shot, combined | 0.5872 **[checked]** | shah2023trillion |
| Cross-document transfer (train minutes+PC, test speeches) | 0.6625 vs 0.7169 in-domain **[checked]** | shah2023trillion, App. B |
| Human annotator agreement | 89.0% (minutes), 95.0% (press conf.), 91.1% (speeches), 90.7% combined **[checked]** | shah2023trillion, Table 9 |
| FOMC-RoBERTa stance measure vs next CPI / PPI | correlation 0.54 / 0.45 full sample; 0.78 / 0.68 press conferences; 0.81 / 0.71 under Powell **[checked]** | shah2023trillion, Table 6 |
| CentralBankRoBERTa sentiment classifier | accuracy 0.88; F1, precision, recall each 0.88 **[model card; not checked in paper]** | pfeifer2023centralbankroberta |
| Hawkish-dovish dataset size | 2,480 labelled sentences (1,984 train / 496 test on Hugging Face); 1,132 minutes, 322 press conf., 1,026 speeches **[checked]** | shah2023trillion, Table 4 |

Dataset licence: the Hugging Face dataset `gtfintechlab/fomc_communication` lists the licence as `cc-by-nc-4.0` (CC BY-NC 4.0, non-commercial), fetched 2026-10-14. Labels there are 0 = dovish, 1 = hawkish, 2 = neutral. The ACL paper abstract also states CC BY-NC 4.0 for dataset, models and code. (The arXiv listing page shows a CC BY-NC-SA 4.0 badge; that applies to the arXiv paper text.) The model `gtfintechlab/FOMC-RoBERTa` is also tagged `cc-by-nc-4.0`. Implication: any use in cbtone must be non-commercial and attributed. The CentralBankRoBERTa sentiment model card lists MIT.

## Sources

### 1. Hansen & McMahon (2016), `hansen2016shocking`
Journal of International Economics 99: S114-S133. DOI 10.1016/j.jinteco.2015.12.008.
The paper asks whether FOMC statements move markets and the real economy through what they say about current conditions or through forward guidance. It applies computational linguistics to FOMC statements to separate the two content types, then enters them into a FAVAR with market and macro variables. Forward-guidance content matters more for market and real variables than current-conditions content; real effects of both are modest. For cbtone this is the canonical "text as a measured shock" design, and it motivates separating policy-stance language from economic-assessment language. No classification accuracy is reported, so it provides no F1 benchmark. It is English and Fed only, which leaves other banks and languages to us.

### 2. Hansen, McMahon & Prat (2018), `hansen2018transparency`
Quarterly Journal of Economics 133(2): 801-870. DOI 10.1093/qje/qjx045.
The paper asks how greater transparency changes deliberation inside the FOMC. It uses the 1993 disclosure of meeting transcripts as a natural experiment, applies Latent Dirichlet Allocation topic models to FOMC transcripts, and estimates a difference-in-differences design. It finds both a discipline effect and a conformity effect, with the discipline effect the larger on its influence measure. For cbtone the relevance is methodological: unsupervised topic measures are an alternative scorer family to dictionaries and fine-tuned classifiers, and the paper shows text measures can support causal designs. It reports no tone-classification accuracy, so no benchmark. Coverage is the FOMC in English only.

### 3. Apel & Blix Grimaldi (2014), `apel2014informative`
Review of Economics 65(1): 53-76. DOI 10.1515/roe-2014-0104. Earlier: Sveriges Riksbank Working Paper 261 (2012).
The paper asks how informative central-bank minutes are about future policy. It applies automated content analysis to Riksbank minutes, turning qualitative text into a quantitative sentiment/tone index built from hawkish and dovish word and phrase counts. The index helps predict subsequent policy-rate decisions. Picault and Renault (source 4) use the Apel-Blix Grimaldi dictionary as a comparator, which makes it a standard word-count baseline. For cbtone it is the Riksbank-specific lexicon to reproduce and to compare against other scorers; it also covers a non-Fed, non-ECB bank. I did not read the full text, so the exact word-list construction and predictive fit statistics are not recorded here. Verified from the Riksbank working-paper abstract and Crossref.

### 4. Picault & Renault (2017), `picault2017words`
Journal of International Money and Finance 79: 136-156. DOI 10.1016/j.jimonfin.2017.09.005.
The paper builds a field-specific lexicon for ECB press conferences. Weighted words and n-grams rate monetary-policy stance (dovish, neutral, hawkish) and the euro-area economy (negative, neutral, positive). The abstract reports three results: the measure helps explain future ECB decisions in an augmented Taylor rule; stock-market volatility rises the day after a negative euro-area tone and falls after a positive one; and the indicators outperform classifications based on the Loughran-McDonald and Apel-Blix Grimaldi dictionaries and a media-based policy uncertainty measure. For cbtone this is the principal ECB English lexicon to implement and compare. The lexicon is distributed in the R package `sentopics`. Sample period and coefficient sizes were not read.

### 5. Gorodnichenko, Pham & Talavera (2023), `gorodnichenko2023voice`
American Economic Review 113(2): 548-584. DOI 10.1257/aer.20220129. (This is the full AER, not AER: Insights.) NBER WP 28592.
The paper asks whether the vocal tone of Fed Chairs in FOMC press conferences carries information beyond the text. A deep-learning model detects emotion in the audio, and the authors test market responses while controlling for policy actions, Swanson's monetary policy shocks and text sentiment. Positive vocal tone leads to statistically significant and economically large increases in share prices; the bond market responds little. For cbtone this marks the boundary of a text-only approach: audio carries independent signal that our pipeline will not capture. Sample size and coefficients were not extractable from the pages read, so no numeric benchmark is recorded.

### 6. Shah, Paturi & Chava (2023), `shah2023trillion`
ACL 2023 (Long Papers), pp. 6664-6679, Toronto. DOI 10.18653/v1/2023.acl-long.368.
The paper introduces hawkish-dovish-neutral sentence classification for Fed text. Data are FOMC minutes, press conferences and speeches, 1996-2022, with 2,480 annotated sentences (two annotators, agreement 89-95%). It benchmarks rule-based, LSTM, BERT-family, FLANG, RoBERTa and ChatGPT-3.5 models. RoBERTa-large is best (weighted F1 0.717 combined; 0.55 on press conferences), versus about 0.50 for the rule-based baseline and 0.587 for zero-shot ChatGPT. A document-level stance measure correlates 0.54 with next CPI (0.78 on press conferences). For cbtone this is the main supervised benchmark and the source of the "FOMC-RoBERTa" scorer. The dataset and model are CC BY-NC 4.0 (see above). It is English and Fed only.

### 7. Pfeifer & Marohl (2023), `pfeifer2023centralbankroberta`
The Journal of Finance and Data Science 9: 100114. DOI 10.1016/j.jfds.2023.100114.
The paper presents CentralBankRoBERTa, a RoBERTa model fine-tuned on more than 12,000 manually labelled sentences from the Federal Reserve, the ECB and BIS-member central banks (English). It has two classifiers: the economic agent addressed (five agent types) and the positive or negative sentiment toward that agent. Hugging Face model cards report about 0.93 accuracy for the agent classifier and 0.88 accuracy and F1 for the sentiment classifier; I could not confirm these in the article text. The sentiment model is MIT-licensed. For cbtone it is the multi-bank, English, non-hawk/dove scorer: it measures positive/negative sentiment, not stance, so it is not directly comparable with FOMC-RoBERTa, and the label mismatch must be handled explicitly.

### 8. Loughran & McDonald (2011), `loughran2011liability`
The Journal of Finance 66(1): 35-65. DOI 10.1111/j.1540-6261.2010.01625.x.
The paper asks whether general-purpose sentiment dictionaries suit financial text. Using 10-K filings from 1994-2008, it finds that almost three-fourths of the words the Harvard dictionary labels negative are not negative in a financial context. It constructs finance-specific word lists and links them to filing returns, trading volume, volatility, fraud, material weakness and unexpected earnings. For cbtone the Loughran-McDonald list is the standard off-the-shelf dictionary baseline; it was built for corporate filings, not central-bank prose, and Picault and Renault report it is outperformed by a field-specific ECB lexicon. We expect it to be the weakest scorer on stance and to serve as a lower anchor.

### 9. Bennani & Neuenkirch (2017), `bennani2017home`
Applied Economics 49(11): 1114-1131. DOI 10.1080/00036846.2016.1210782.
The paper asks whether ECB Governing Council members' speeches reflect national or regional bias. It builds a hawkishness (tone) indicator from 1,618 speeches given in 1999-2014 and relates it to macroeconomic forecasts and speaker characteristics. Inflation and growth expectations raise hawkishness; regional growth expectations and speaker preferences explain much of the cross-speaker variation, and national-president preferences track central-bank independence at the time of the Maastricht Treaty. For cbtone it provides a speech-level ECB tone measure, supports speech-level analysis beyond press conferences, and shows that speaker identity is a covariate worth keeping. I did not extract the scoring method details or fit statistics.

### 10. Lucca & Trebbi (2009), `lucca2009measuring`
NBER Working Paper 15367. DOI 10.3386/w15367 (working paper; no journal version found).
The paper asks how much FOMC statements reveal about future rates. It scores statements with an automated technique that draws on Internet and news sources, applied to statements from 1999. Intraday data show short-term Treasury yields reacting to policy-rate changes while longer-dated yields react mainly to changes in communication, and changes in statement content lead rate decisions by more than a year in forecasting and VAR models (a 2008 SED version reported about six months). For cbtone it is the earliest automated, event-study-linked scorer and supports market-reaction and lead-lag evaluation designs. It does not report classification accuracy.

## Gaps

This cluster leaves the following combinations untested. Supervised scorers (FOMC-RoBERTa, CentralBankRoBERTa) have been validated almost only on English Fed text; the ECB, BoE, BoJ and Riksbank are covered mainly by dictionaries, and only the ECB has a field-specific lexicon (Picault and Renault). Nothing here measures non-English central-bank text, so any cbtone work on translated or native-language text has no benchmark, and cross-language scorer transfer is untested. No source compares dictionary, transformer, and LLM scorers on the same bank and the same labelled sample outside the Fed; Shah et al. include ChatGPT-3.5 only, with no newer LLMs. The scorers are rarely tested on the same evaluation: stance F1 (Shah), sentiment F1 (Pfeifer and Marohl), Taylor-rule fit (Picault and Renault), volatility response (Picault and Renault), and yield response (Lucca and Trebbi) are not comparable across studies. The labelled hawk/dove ground truth exists only for the Fed, so ECB and other-bank agreement with human labels is unmeasured. Press-conference Q&A and audio are covered by one Fed study each, and none for other banks.
